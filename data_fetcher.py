"""
基金数据采集模块
数据源：akshare + Tavily 实时新闻 + 技术指标计算
"""

import os
import requests
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
import warnings
warnings.filterwarnings("ignore")

load_dotenv()


# ════════════════════════════════════════════
#  基金基本信息
# ════════════════════════════════════════════
def get_fund_basic_info(fund_code: str) -> dict:
    try:
        df = ak.fund_individual_basic_info_xq(symbol=fund_code)
        info = dict(zip(df["item"], df["value"]))
        if info:
            return info
    except Exception:
        pass

    try:
        df = ak.fund_name_em()
        row = df[df["基金代码"] == fund_code]
        if not row.empty:
            return {
                "基金代码": fund_code,
                "基金简称": row.iloc[0].get("基金简称", ""),
                "基金类型": row.iloc[0].get("基金类型", ""),
                "基金经理": row.iloc[0].get("基金经理人", ""),
            }
    except Exception:
        pass

    return {"基金代码": fund_code, "基金简称": "未知", "基金类型": "未知"}


# ════════════════════════════════════════════
#  净值历史
# ════════════════════════════════════════════
def get_fund_nav_history(fund_code: str, days: int = 90) -> pd.DataFrame:
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    # 方法1：开放式基金净值（参数是 symbol= 而非旧版 fund=）
    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        if df is not None and not df.empty:
            df.columns = ["date", "nav", "daily_return"]
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            df = df[df["date"] >= pd.Timestamp(start_date)]
            if not df.empty:
                return df.tail(90)
    except Exception:
        pass

    # 方法2：ETF 场内历史行情
    try:
        df = ak.fund_etf_hist_em(
            symbol=fund_code, period="daily",
            start_date=start_date, end_date=end_date, adjust="qfq"
        )
        if df is not None and not df.empty:
            df = df.rename(columns={"日期": "date", "收盘": "nav", "涨跌幅": "daily_return"})
            df["date"] = pd.to_datetime(df["date"])
            return df[["date", "nav", "daily_return"]].tail(90)
    except Exception:
        pass

    # 方法3：LOF 基金历史行情
    try:
        df = ak.fund_lof_hist_em(
            symbol=fund_code, period="daily",
            start_date=start_date, end_date=end_date, adjust="qfq"
        )
        if df is not None and not df.empty:
            df = df.rename(columns={"日期": "date", "收盘": "nav", "涨跌幅": "daily_return"})
            df["date"] = pd.to_datetime(df["date"])
            return df[["date", "nav", "daily_return"]].tail(90)
    except Exception:
        pass

    # 方法4：新浪 ETF 历史（备用）
    try:
        df = ak.fund_etf_hist_sina(symbol=fund_code)
        if df is not None and not df.empty:
            df = df.rename(columns={"close": "nav"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            df = df[df["date"] >= pd.Timestamp(start_date)]
            df["daily_return"] = df["nav"].pct_change() * 100
            if not df.empty:
                return df[["date", "nav", "daily_return"]].tail(90)
    except Exception:
        pass

    return pd.DataFrame(columns=["date", "nav", "daily_return"])


# ════════════════════════════════════════════
#  技术指标计算
# ════════════════════════════════════════════
def calc_technical_indicators(nav_df: pd.DataFrame) -> dict:
    """计算 MA / RSI / MACD / 乖离率 / 波动率"""
    if nav_df.empty or len(nav_df) < 5:
        return {}

    df = nav_df.copy()
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna(subset=["nav"]).sort_values("date").reset_index(drop=True)
    result = {}

    latest_nav = df["nav"].iloc[-1]
    result["最新净值"] = round(latest_nav, 4)

    # 均线 MA
    for n in [5, 10, 20, 60]:
        if len(df) >= n:
            result[f"MA{n}"] = round(df["nav"].rolling(n).mean().iloc[-1], 4)

    # 多头/空头排列
    ma5, ma10, ma20 = result.get("MA5"), result.get("MA10"), result.get("MA20")
    if ma5 and ma10 and ma20:
        result["多头排列"] = bool(ma5 > ma10 > ma20)
        result["空头排列"] = bool(ma5 < ma10 < ma20)

    # 乖离率（相对MA20）
    if ma20:
        bias = (latest_nav - ma20) / ma20 * 100
        result["乖离率_MA20"] = round(bias, 2)
        result["乖离率_风险"] = (
            "⚠️ 超买，谨慎追高" if bias > 5 else
            "✅ 低估区间，可关注" if bias < -5 else "正常区间"
        )

    # RSI 14日
    if len(df) >= 15:
        delta = df["nav"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = (100 - 100 / (1 + rs)).iloc[-1]
        result["RSI_14"] = round(float(rsi), 1)
        result["RSI_信号"] = (
            "超买（>70）" if rsi > 70 else
            "超卖（<30）" if rsi < 30 else "中性"
        )

    # MACD 12/26/9
    if len(df) >= 30:
        ema12 = df["nav"].ewm(span=12, adjust=False).mean()
        ema26 = df["nav"].ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        result["MACD_DIF"] = round(float(dif.iloc[-1]), 4)
        result["MACD_DEA"] = round(float(dea.iloc[-1]), 4)
        result["MACD_柱"]  = round(float((dif - dea).iloc[-1] * 2), 4)
        result["MACD_信号"] = "金叉↑" if dif.iloc[-1] > dea.iloc[-1] else "死叉↓"

    # 年化波动率（20日）
    if len(df) >= 20:
        vol = df["nav"].pct_change().tail(20).std() * np.sqrt(252) * 100
        result["年化波动率"] = round(float(vol), 1)

    # 区间统计
    result["60日最高"] = round(float(df["nav"].tail(60).max()), 4)
    result["60日最低"] = round(float(df["nav"].tail(60).min()), 4)
    result["60日涨跌幅"] = round(
        (df["nav"].iloc[-1] / df["nav"].iloc[0] - 1) * 100, 2
    ) if len(df) >= 2 else 0

    dr_col = pd.to_numeric(
        df.get("daily_return", df["nav"].pct_change() * 100),
        errors="coerce"
    )
    result["近5日均涨跌"] = round(float(dr_col.tail(5).mean()), 3)

    return result


# ════════════════════════════════════════════
#  Tavily 实时新闻搜索
# ════════════════════════════════════════════
def search_news_tavily(query: str, api_key: str, max_results: int = 6) -> list:
    if not api_key:
        return []
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=12,
        )
        resp.raise_for_status()
        results = []
        for item in resp.json().get("results", []):
            results.append({
                "title": item.get("title", ""),
                "time": item.get("published_date", datetime.now().strftime("%Y-%m-%d")),
                "source": item.get("url", ""),
                "summary": item.get("content", "")[:300],
                "from": "tavily",
            })
        return results
    except Exception:
        return []


def get_fund_news(fund_code: str, fund_name: str = "",
                  tavily_key: str = None, limit: int = 10) -> list:
    """优先 Tavily 实时搜索，失败则 fallback akshare"""
    tavily_key = tavily_key or os.getenv("TAVILY_API_KEY", "")
    news_list = []

    # 1. Tavily 实时搜索
    if tavily_key and fund_name and fund_name not in ("未知", ""):
        for q in [
            f"{fund_name} 基金 最新动态 市场分析",
            f"{fund_name} 公告 净值 {datetime.now().strftime('%Y年%m月')}",
        ]:
            news_list.extend(search_news_tavily(q, tavily_key, max_results=5))

        # 去重
        seen, deduped = set(), []
        for n in news_list:
            if n["title"] not in seen:
                seen.add(n["title"])
                deduped.append(n)
        news_list = deduped

    # 2. akshare 兜底
    if len(news_list) < 3:
        try:
            df = ak.fund_news_em(symbol=fund_code)
            for _, row in df.head(limit).iterrows():
                news_list.append({
                    "title": row.get("新闻标题", ""),
                    "time": str(row.get("发布时间", "")),
                    "source": "东方财富",
                    "summary": (row.get("新闻内容") or "")[:200],
                    "from": "akshare",
                })
        except Exception:
            pass

    # 3. 宏观新闻补充
    if tavily_key and len(news_list) < 5:
        macro = search_news_tavily("A股 基金 宏观政策 最新", tavily_key, max_results=3)
        news_list.extend(macro)

    return news_list[:limit]


# ════════════════════════════════════════════
#  市场宏观指标
# ════════════════════════════════════════════
def get_market_sentiment() -> dict:
    sentiment = {}

    for symbol, name in [
        ("sh000001", "上证指数"),
        ("sz399300", "沪深300"),
        ("sz399006", "创业板指"),
    ]:
        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            tail = df.tail(6)
            latest = float(tail.iloc[-1]["close"])
            prev5  = float(tail.iloc[0]["close"])
            sentiment[f"{name}_最新"] = round(latest, 2)
            sentiment[f"{name}_5日涨跌%"] = round((latest / prev5 - 1) * 100, 2)
        except Exception:
            pass

    try:
        df = ak.bond_zh_us_rate(start_date="20240101")
        sentiment["10年国债收益率"] = round(
            float(df.tail(1).iloc[0]["中国国债收益率10年"]), 3
        )
    except Exception:
        pass

    return sentiment


# ════════════════════════════════════════════
#  基金经理
# ════════════════════════════════════════════
def get_fund_manager_info(fund_code: str) -> dict:
    try:
        df = ak.fund_manager_em(fund_code)
        if not df.empty:
            mgr = df.iloc[0]
            return {
                "姓名": mgr.get("基金经理", ""),
                "任职时间": str(mgr.get("现任基金经理", "")),
                "任期回报": str(mgr.get("任职回报", "")),
            }
    except Exception:
        pass
    return {}


# ════════════════════════════════════════════
#  一键采集入口
# ════════════════════════════════════════════
def collect_all_data(fund_code: str, tavily_key: str = None) -> dict:
    print("  → 采集基本信息...")
    basic = get_fund_basic_info(fund_code)

    print("  → 采集净值历史...")
    nav_df = get_fund_nav_history(fund_code, days=90)

    print("  → 计算技术指标...")
    tech = calc_technical_indicators(nav_df)

    print("  → 搜索实时新闻（Tavily）...")
    news = get_fund_news(
        fund_code,
        fund_name=basic.get("基金简称", ""),
        tavily_key=tavily_key,
        limit=10,
    )

    print("  → 采集市场指标...")
    market = get_market_sentiment()

    print("  → 采集基金经理信息...")
    manager = get_fund_manager_info(fund_code)

    return {
        "fund_code": fund_code,
        "basic_info": basic,
        "nav_summary": tech,
        "nav_history": nav_df,
        "news": news,
        "market": market,
        "manager": manager,
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }