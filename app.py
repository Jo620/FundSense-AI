"""
支付宝基金趋势分析 Agent - Streamlit Web UI
新增：技术指标面板 / 实时新闻标注 / 推送通知配置
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os
from dotenv import load_dotenv

from data_fetcher import collect_all_data
from analyzer import analyze_fund, format_report, detect_fund_type
from notifier import push_report

load_dotenv()

# ─── 页面配置 ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="基金趋势分析 Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header {
        font-size:2rem; font-weight:700;
        background:linear-gradient(90deg,#1a73e8,#0d47a1);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    }
    .verdict-box { padding:1.2rem 1.5rem; border-radius:12px; text-align:center; margin:0.8rem 0; }
    .verdict-buy    { background:#e8f5e9; border:2px solid #43a047; }
    .verdict-hold   { background:#e3f2fd; border:2px solid #1e88e5; }
    .verdict-reduce { background:#fff8e1; border:2px solid #ffb300; }
    .verdict-sell   { background:#ffebee; border:2px solid #e53935; }
    .verdict-watch  { background:#f5f5f5; border:2px solid #9e9e9e; }
    .tech-card { background:#f8f9fa; border-radius:10px; padding:0.8rem 1rem; margin-bottom:0.5rem; }
    .news-item { padding:0.6rem 0.8rem; border-left:3px solid #1a73e8; margin-bottom:0.5rem;
                 background:#f8f9fa; border-radius:0 8px 8px 0; }
    .news-realtime { border-left-color:#e53935; }
    .tag { display:inline-block; padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:600; margin:2px; }
    .tag-green  { background:#e8f5e9; color:#2e7d32; }
    .tag-red    { background:#ffebee; color:#c62828; }
    .tag-blue   { background:#e3f2fd; color:#1565c0; }
    .tag-orange { background:#fff3e0; color:#e65100; }
    .tag-live   { background:#ffebee; color:#c62828; }
    .tag-hist   { background:#f3e5f5; color:#6a1b9a; }
    .disclaimer { font-size:0.75rem; color:#9e9e9e; border-top:1px solid #eee;
                  padding-top:0.5rem; margin-top:1rem; }
    [data-testid="stSidebar"] { background:#0d1117; }
    [data-testid="stSidebar"] * { color:#e6edf3 !important; }
</style>
""", unsafe_allow_html=True)


# ─── 辅助函数 ─────────────────────────────────────────────────────────────────
def verdict_css(v):
    return {"买入":"verdict-buy","持有":"verdict-hold",
            "减仓":"verdict-reduce","卖出":"verdict-sell"}.get(v,"verdict-watch")

def verdict_emoji(v):
    return {"买入":"🟢","持有":"🔵","减仓":"🟡","卖出":"🔴"}.get(v,"⚪")

def plot_nav(nav_df, fund_name, tech):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=nav_df["date"], y=nav_df["nav"], mode="lines", name="净值",
        line=dict(color="#1a73e8", width=2.5),
        fill="tozeroy", fillcolor="rgba(26,115,232,0.07)",
    ))
    # MA 均线
    colors = {"MA5":"#ff7043","MA10":"#ab47bc","MA20":"#26a69a","MA60":"#ffa726"}
    for ma, color in colors.items():
        val = tech.get(ma)
        if val:
            nav_df_sorted = nav_df.sort_values("date")
            window = int(ma[2:])
            ma_series = pd.to_numeric(nav_df_sorted["nav"], errors="coerce").rolling(window).mean()
            fig.add_trace(go.Scatter(
                x=nav_df_sorted["date"], y=ma_series,
                mode="lines", name=ma,
                line=dict(color=color, width=1.2, dash="dot"),
            ))
    # 最高最低点
    max_idx = nav_df["nav"].idxmax()
    min_idx = nav_df["nav"].idxmin()
    fig.add_trace(go.Scatter(
        x=[nav_df.loc[max_idx,"date"]], y=[nav_df.loc[max_idx,"nav"]],
        mode="markers+text", name="区间最高",
        marker=dict(color="#43a047",size=10,symbol="triangle-up"),
        text=[f"最高 {nav_df.loc[max_idx,'nav']:.4f}"], textposition="top center",
    ))
    fig.add_trace(go.Scatter(
        x=[nav_df.loc[min_idx,"date"]], y=[nav_df.loc[min_idx,"nav"]],
        mode="markers+text", name="区间最低",
        marker=dict(color="#e53935",size=10,symbol="triangle-down"),
        text=[f"最低 {nav_df.loc[min_idx,'nav']:.4f}"], textposition="bottom center",
    ))
    fig.update_layout(
        title=f"{fund_name} - 净值走势 + 均线",
        xaxis_title="日期", yaxis_title="单位净值",
        legend=dict(orientation="h", y=1.1),
        plot_bgcolor="white", paper_bgcolor="white",
        height=360, margin=dict(l=40,r=20,t=50,b=40),
    )
    fig.update_xaxes(gridcolor="#f0f0f0")
    fig.update_yaxes(gridcolor="#f0f0f0")
    return fig

def plot_macd(nav_df):
    df = nav_df.copy().sort_values("date")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    if len(df) < 30:
        return None
    ema12 = df["nav"].ewm(span=12,adjust=False).mean()
    ema26 = df["nav"].ewm(span=26,adjust=False).mean()
    dif   = ema12 - ema26
    dea   = dif.ewm(span=9,adjust=False).mean()
    bar   = (dif - dea) * 2
    colors = ["#43a047" if v >= 0 else "#e53935" for v in bar]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["date"], y=bar, marker_color=colors, name="MACD柱"))
    fig.add_trace(go.Scatter(x=df["date"], y=dif, mode="lines",
                             line=dict(color="#1a73e8",width=1.5), name="DIF"))
    fig.add_trace(go.Scatter(x=df["date"], y=dea, mode="lines",
                             line=dict(color="#ff7043",width=1.5), name="DEA"))
    fig.add_hline(y=0, line_color="#ccc", line_width=1)
    fig.update_layout(title="MACD 指标", height=220,
                      plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=40,r=20,t=40,b=30))
    return fig

def plot_rsi(nav_df):
    import numpy as np
    df = nav_df.copy().sort_values("date")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    if len(df) < 15:
        return None
    delta = df["nav"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=rsi, mode="lines",
                             line=dict(color="#ab47bc",width=2), name="RSI(14)"))
    fig.add_hline(y=70, line_dash="dash", line_color="#e53935",
                  annotation_text="超买70", annotation_position="right")
    fig.add_hline(y=30, line_dash="dash", line_color="#43a047",
                  annotation_text="超卖30", annotation_position="right")
    fig.update_layout(title="RSI(14) 指标", height=200,
                      plot_bgcolor="white", paper_bgcolor="white",
                      yaxis=dict(range=[0,100]),
                      margin=dict(l=40,r=60,t=40,b=30))
    return fig

def plot_daily_return(nav_df):
    if "daily_return" not in nav_df.columns:
        return None
    df = nav_df.copy().tail(30)
    df["daily_return"] = pd.to_numeric(df["daily_return"], errors="coerce")
    df = df.dropna(subset=["daily_return"])
    colors = ["#43a047" if r >= 0 else "#e53935" for r in df["daily_return"]]
    fig = go.Figure(go.Bar(x=df["date"], y=df["daily_return"],
                           marker_color=colors, name="日涨跌%"))
    fig.add_hline(y=0, line_color="#ccc", line_width=1)
    fig.update_layout(title="近30日日涨跌幅(%)", height=220,
                      plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=40,r=20,t=40,b=30))
    return fig


# ─── 侧边栏 ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 基金分析 Agent")
    st.markdown("---")
    # API Key —— 优先读 .env，填了就不用再手动输入
    env_deepseek = os.getenv("DEEPSEEK_API_KEY", "")
    env_tavily   = os.getenv("TAVILY_API_KEY", "")

    if env_deepseek:
        st.success("✅ DeepSeek Key 已从 .env 加载")
        _input_key = st.text_input(
            "🔑 覆盖 DeepSeek Key（可选）",
            type="password", placeholder="留空则使用 .env 中的值",
        )
        api_key = _input_key if _input_key else env_deepseek
    else:
        api_key = st.text_input(
            "🔑 DeepSeek API Key",
            type="password", placeholder="sk-...",
        )

    if env_tavily:
        st.success("✅ Tavily Key 已从 .env 加载")
        _input_tavily = st.text_input(
            "🌐 覆盖 Tavily Key（可选）",
            type="password", placeholder="留空则使用 .env 中的值",
        )
        tavily_key = _input_tavily if _input_tavily else env_tavily
    else:
        tavily_key = st.text_input(
            "🌐 Tavily API Key（实时新闻，可选）",
            type="password", placeholder="tvly-...",
            help="免费注册：https://tavily.com，1000次/月",
        )

    st.markdown("### 输入基金代码")
    fund_input = st.text_input(
        "基金代码",
        placeholder="如：000001 / 510300 / 110022",
    )

    st.markdown("**快捷示例：**")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("沪深300ETF\n510300", use_container_width=True):
            st.session_state["fund_code"] = "510300"
        if st.button("易方达债券\n110022", use_container_width=True):
            st.session_state["fund_code"] = "110022"
    with c2:
        if st.button("天弘余额宝\n000198", use_container_width=True):
            st.session_state["fund_code"] = "000198"
        if st.button("富国天惠\n161005", use_container_width=True):
            st.session_state["fund_code"] = "161005"

    if "fund_code" in st.session_state and not fund_input:
        fund_input = st.session_state["fund_code"]

    st.markdown("---")
    analyze_btn = st.button(
        "🚀 一键分析",
        type="primary",
        use_container_width=True,
        disabled=not (api_key and fund_input),
    )

    # ── 推送配置（折叠）────────────────────────
    st.markdown("---")
    with st.expander("📤 推送通知配置"):
        st.markdown("填入后分析完自动推送，留空跳过")
        push_wechat   = st.text_input("企业微信 Webhook", value=os.getenv("WECHAT_WEBHOOK_URL",""), type="password")
        push_feishu   = st.text_input("飞书 Webhook",     value=os.getenv("FEISHU_WEBHOOK_URL",""), type="password")
        push_tg_token = st.text_input("Telegram Token",   value=os.getenv("TELEGRAM_BOT_TOKEN",""), type="password")
        push_tg_chat  = st.text_input("Telegram Chat ID", value=os.getenv("TELEGRAM_CHAT_ID",""))
        push_email    = st.text_input("发件邮箱",          value=os.getenv("EMAIL_SENDER",""))
        push_email_pw = st.text_input("邮箱授权码",        value=os.getenv("EMAIL_PASSWORD",""), type="password")
        push_email_to = st.text_input("收件人邮箱",        value=os.getenv("EMAIL_RECEIVERS",""))

    st.markdown("---")
    st.markdown("""
**数据来源**
- 🌐 Tavily 实时新闻搜索
- 📊 天天基金 / 东方财富
- 📈 A股市场指数
""")


# ─── 主界面 ───────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">📊 支付宝基金趋势分析 Agent</p>', unsafe_allow_html=True)
st.markdown("净值走势 + **实时新闻** + **技术指标** + 宏观环境，由 DeepSeek AI 综合研判买卖时机")
st.markdown("---")

if not analyze_btn:
    c1, c2, c3, c4 = st.columns(4)
    c1.info("**📥 输入基金代码**\n\n6位基金代码")
    c2.info("**🌐 实时新闻**\n\nTavily 搜索最新动态")
    c3.info("**📊 技术指标**\n\nMA/RSI/MACD/乖离率")
    c4.info("**📤 自动推送**\n\n微信/飞书/邮件")
    st.stop()


# ─── 执行分析 ─────────────────────────────────────────────────────────────────
fund_code = fund_input.strip().zfill(6)

with st.spinner(f"正在分析基金 {fund_code}..."):
    prog = st.progress(0, text="采集数据中...")
    try:
        prog.progress(15, text="获取净值与基本信息...")
        data = collect_all_data(fund_code, tavily_key=tavily_key or None)
        prog.progress(65, text="DeepSeek 分析中...")
        analysis = analyze_fund(data, api_key)
        prog.progress(100, text="完成！")
        prog.empty()
    except Exception as e:
        st.error(f"分析出错：{e}")
        st.stop()

if "error" in analysis:
    st.error(f"AI 分析失败：{analysis['error']}")
    st.stop()

# ─── 自动推送 ─────────────────────────────────────────────────────────────────
fund_name = data["basic_info"].get("基金简称", fund_code)
push_config = {
    "wechat_webhook": push_wechat,
    "feishu_webhook": push_feishu,
    "telegram_token": push_tg_token,
    "telegram_chat_id": push_tg_chat,
    "email_sender": push_email,
    "email_password": push_email_pw,
    "email_receivers": push_email_to,
}
has_push = any(v for v in push_config.values())
if has_push:
    report_text = format_report(data, analysis)
    push_results = push_report(report_text, fund_name=fund_name, config=push_config)
    if push_results:
        cols = st.columns(len(push_results))
        for i, (ch, status) in enumerate(push_results.items()):
            cols[i].markdown(f"**{ch}** {status}")


# ─── 展示结果 ─────────────────────────────────────────────────────────────────
st.markdown(f"## {fund_name}（{fund_code}）")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📋 分析结论", "📊 技术指标", "📈 净值走势", "📰 实时新闻", "🌍 市场环境"]
)

# ── Tab1: 结论 ────────────────────────────────────────────────────────────────
with tab1:
    verdict    = analysis.get("verdict", "观望")
    confidence = analysis.get("confidence", 0)
    tech       = data.get("nav_summary", {})

    cv, cc, cr = st.columns([2, 1, 1])
    with cv:
        vc = verdict_css(verdict)
        ve = verdict_emoji(verdict)
        st.markdown(f"""
        <div class="verdict-box {vc}">
            <div style="font-size:2.5rem">{ve}</div>
            <div style="font-size:1.8rem;font-weight:700">{verdict}</div>
            <div style="font-size:0.95rem;margin-top:4px">{analysis.get('summary','')}</div>
        </div>""", unsafe_allow_html=True)
    with cc:
        st.metric("置信度", f"{confidence}%")
        bar_c = "#43a047" if confidence>=75 else "#ffb300" if confidence>=50 else "#e53935"
        st.markdown(f"""<div style="background:#eee;border-radius:6px;height:8px;margin-top:-10px">
          <div style="background:{bar_c};width:{confidence}%;height:8px;border-radius:6px"></div></div>""",
                    unsafe_allow_html=True)
    with cr:
        st.metric("参考时限", analysis.get("time_horizon","中期"))
        st.metric("风险等级", analysis.get("risk_level","中"))

    st.markdown("---")

    # 净值 + 关键技术指标速览
    m1,m2,m3,m4,m5,m6 = st.columns(6)
    m1.metric("最新净值",  tech.get("最新净值","N/A"))
    delta = tech.get("60日涨跌幅", 0)
    m2.metric("60日涨跌",  f"{delta}%", delta=f"{delta}%")
    m3.metric("MA多头排列", "✅ 是" if tech.get("多头排列") else "❌ 否")
    m4.metric("乖离率MA20", f"{tech.get('乖离率_MA20','N/A')}%")
    m5.metric("RSI(14)",   tech.get("RSI_14","N/A"))
    m6.metric("MACD信号",  tech.get("MACD_信号","N/A"))

    # 技术信号提示
    ts = analysis.get("tech_signal","")
    if ts:
        st.info(f"📊 **技术信号：** {ts}")

    bias_risk = tech.get("乖离率_风险","")
    if "超买" in bias_risk:
        st.warning(f"⚠️ {bias_risk}  |  乖离率 {tech.get('乖离率_MA20')}%，当前不宜追高")
    elif "低估" in bias_risk:
        st.success(f"✅ {bias_risk}  |  乖离率 {tech.get('乖离率_MA20')}%，可关注买入机会")

    st.markdown("---")
    cl, cr2 = st.columns(2)
    with cl:
        st.markdown("#### ✅ 买入理由")
        for p in analysis.get("bull_points",[]):
            st.markdown(f'<span class="tag tag-green">+</span> {p}', unsafe_allow_html=True)
            st.write("")
        st.markdown("#### ⚠️ 谨慎因素")
        for p in analysis.get("bear_points",[]):
            st.markdown(f'<span class="tag tag-red">−</span> {p}', unsafe_allow_html=True)
            st.write("")
    with cr2:
        st.markdown("#### 🚨 主要风险")
        for r in analysis.get("key_risks",[]):
            st.warning(r)
        st.markdown("#### 💡 操作建议")
        st.info(analysis.get("action_advice",""))
        bp = analysis.get("buy_point")
        sl = analysis.get("stop_loss")
        if bp: st.markdown(f"📍 **买入参考：** {bp}")
        if sl: st.markdown(f"🛑 **止损参考：** {sl}")

    st.markdown('<p class="disclaimer">⚠️ 本报告由AI生成，仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。</p>',
                unsafe_allow_html=True)


# ── Tab2: 技术指标 ────────────────────────────────────────────────────────────
with tab2:
    tech = data.get("nav_summary", {})
    if not tech:
        st.warning("技术指标数据不足")
    else:
        st.markdown("#### 均线系统")
        ma_cols = st.columns(4)
        latest  = tech.get("最新净值", 0)
        for i, n in enumerate([5, 10, 20, 60]):
            val = tech.get(f"MA{n}")
            if val:
                diff = round((latest - val) / val * 100, 2) if latest else 0
                sign = "📈" if diff > 0 else "📉"
                ma_cols[i].metric(f"MA{n}", val, delta=f"{diff}%")

        st.markdown("---")
        st.markdown("#### 趋势判断")
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            st.markdown("**均线排列**")
            if tech.get("多头排列"):
                st.success("✅ 多头排列（MA5>MA10>MA20）\n\n趋势偏多，可考虑持有或买入")
            elif tech.get("空头排列"):
                st.error("❌ 空头排列（MA5<MA10<MA20）\n\n趋势偏空，注意控制仓位")
            else:
                st.info("⬜ 均线交织，震荡行情")
        with tc2:
            st.markdown("**乖离率**")
            bias = tech.get("乖离率_MA20", 0)
            bias_risk = tech.get("乖离率_风险", "")
            if bias and abs(bias) > 5:
                st.warning(f"乖离率：**{bias}%**\n\n{bias_risk}")
            else:
                st.info(f"乖离率：**{bias}%**\n\n{bias_risk}")
        with tc3:
            st.markdown("**MACD**")
            macd_sig = tech.get("MACD_信号","")
            dif = tech.get("MACD_DIF", 0)
            dea = tech.get("MACD_DEA", 0)
            if "金叉" in macd_sig:
                st.success(f"**{macd_sig}**\n\nDIF:{dif}  DEA:{dea}")
            else:
                st.error(f"**{macd_sig}**\n\nDIF:{dif}  DEA:{dea}")

        st.markdown("---")
        st.markdown("#### RSI 超买超卖")
        rsi = tech.get("RSI_14")
        rsi_sig = tech.get("RSI_信号","")
        if rsi:
            rc1, rc2 = st.columns([1,3])
            with rc1:
                color = "🔴" if rsi>70 else "🟢" if rsi<30 else "🔵"
                st.metric("RSI(14)", f"{color} {rsi}")
                st.write(rsi_sig)
            with rc2:
                import plotly.graph_objects as go2
                fig_gauge = go2.Figure(go2.Indicator(
                    mode="gauge+number",
                    value=rsi,
                    domain={"x":[0,1],"y":[0,1]},
                    gauge={
                        "axis":{"range":[0,100]},
                        "bar":{"color":"#1a73e8"},
                        "steps":[
                            {"range":[0,30],"color":"#e8f5e9"},
                            {"range":[30,70],"color":"#f5f5f5"},
                            {"range":[70,100],"color":"#ffebee"},
                        ],
                        "threshold":{"line":{"color":"red","width":2},"thickness":0.75,"value":70},
                    }
                ))
                fig_gauge.update_layout(height=180, margin=dict(l=20,r=20,t=20,b=20))
                st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 全部指标")
        rows = [(k, v) for k, v in tech.items()]
        half = len(rows) // 2
        ic1, ic2 = st.columns(2)
        with ic1:
            for k, v in rows[:half]:
                st.markdown(f"**{k}：** `{v}`")
        with ic2:
            for k, v in rows[half:]:
                st.markdown(f"**{k}：** `{v}`")

        nav_df = data.get("nav_history", pd.DataFrame())
        if not nav_df.empty:
            st.markdown("---")
            macd_fig = plot_macd(nav_df)
            if macd_fig:
                st.plotly_chart(macd_fig, use_container_width=True)
            rsi_fig = plot_rsi(nav_df)
            if rsi_fig:
                st.plotly_chart(rsi_fig, use_container_width=True)


# ── Tab3: 净值走势 ────────────────────────────────────────────────────────────
with tab3:
    nav_df = data.get("nav_history", pd.DataFrame())
    if nav_df.empty:
        st.warning("暂无净值历史数据")
    else:
        tech = data.get("nav_summary", {})
        st.plotly_chart(plot_nav(nav_df, fund_name, tech), use_container_width=True)
        dr_fig = plot_daily_return(nav_df)
        if dr_fig:
            st.plotly_chart(dr_fig, use_container_width=True)
        with st.expander("📄 原始数据"):
            st.dataframe(nav_df.tail(30), use_container_width=True)


# ── Tab4: 实时新闻 ────────────────────────────────────────────────────────────
with tab4:
    news = data.get("news", [])
    sentiment = analysis.get("news_sentiment","中性")
    s_color = {"正面":"tag-green","负面":"tag-red"}.get(sentiment,"tag-blue")

    realtime_count = sum(1 for n in news if n.get("from")=="tavily")
    sc1, sc2 = st.columns([1, 3])
    with sc1:
        st.markdown("**整体情绪**")
        st.markdown(f'<span class="tag {s_color}" style="font-size:1.1rem;padding:6px 14px">{sentiment}</span>',
                    unsafe_allow_html=True)
        st.markdown(f"🌐 实时新闻：**{realtime_count}** 条\n\n📁 历史新闻：**{len(news)-realtime_count}** 条")
    with sc2:
        st.markdown(f"**AI解读：** {analysis.get('news_analysis','')}")

    if not tavily_key:
        st.info("💡 配置 Tavily API Key 后可获取实时新闻，当前显示历史数据")

    st.markdown("---")
    if not news:
        st.info("暂未获取到相关新闻")
    else:
        for n in news:
            is_live = n.get("from") == "tavily"
            tag_html = '<span class="tag tag-live">🔴 实时</span>' if is_live else '<span class="tag tag-hist">📁 历史</span>'
            news_cls = "news-item news-realtime" if is_live else "news-item"
            st.markdown(f"""
            <div class="{news_cls}">
                {tag_html}
                <span style="font-weight:600;margin-left:6px">{n.get('title','')}</span>
                <div style="font-size:0.8rem;color:#666;margin-top:4px">{n.get('time','')} · {n.get('source','')}</div>
                {f"<div style='font-size:0.85rem;margin-top:4px;color:#444'>{n.get('summary','')}</div>" if n.get('summary') else ''}
            </div>""", unsafe_allow_html=True)


# ── Tab5: 市场环境 ────────────────────────────────────────────────────────────
with tab5:
    market = data.get("market", {})
    if not market:
        st.warning("市场数据获取失败")
    else:
        st.markdown("#### 宏观市场指标")
        cols = st.columns(min(len(market), 4))
        for i, (k, v) in enumerate(market.items()):
            cols[i % 4].metric(k, f"{v:.2f}" if isinstance(v, float) else str(v))

    st.markdown("---")
    manager = data.get("manager", {})
    st.markdown("#### 基金经理")
    if manager:
        for k, v in manager.items():
            st.markdown(f"**{k}：** {v}")
    else:
        st.info("基金经理信息暂不可用")

    with st.expander("🔍 查看完整分析 JSON"):
        st.json(analysis)