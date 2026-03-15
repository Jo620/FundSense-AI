"""
LLM 分析模块 - DeepSeek API
含技术指标 + 实时新闻的增强分析 Prompt
"""

import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# ════════════════════════════════════════════
#  DeepSeek 客户端
# ════════════════════════════════════════════
def get_client(api_key: str = None) -> OpenAI:
    return OpenAI(
        api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )


# ════════════════════════════════════════════
#  基金类型判断
# ════════════════════════════════════════════
def detect_fund_type(basic_info: dict) -> str:
    fund_type = basic_info.get("基金类型", "") or basic_info.get("type", "")
    name = basic_info.get("基金简称", "") or basic_info.get("name", "")
    combined = (fund_type + name).upper()

    if any(k in combined for k in ["货币", "理财", "余额", "现金"]):
        return "货币型"
    if any(k in combined for k in ["债券", "债", "BOND"]):
        return "债券型"
    if any(k in combined for k in ["ETF", "LOF", "指数", "沪深", "中证", "上证"]):
        return "指数/ETF"
    if any(k in combined for k in ["股票", "成长", "价值", "混合"]):
        return "股票型"
    return "混合/其他"


# ════════════════════════════════════════════
#  分类型策略 Prompt
# ════════════════════════════════════════════
FUND_TYPE_PROMPTS = {
    "货币型": """
【货币型基金分析要点】
- 重点：7日年化收益率趋势、DR007/逆回购利率环境
- 买入：利率下行末期、流动性宽松预期
- 卖出：加息周期启动、有更高收益替代品出现
- 技术指标意义有限，重点看利率环境和新闻政策信号
""",
    "债券型": """
【债券型基金分析要点】
- 重点：10年期国债收益率走势、信用利差、久期风险
- 买入：降息预期、经济下行周期；MA均线向上+RSI<50
- 卖出：通胀升温、加息预期；MACD死叉+乖离率>5%
- 技术面：关注MA趋势和乖离率，超买时减仓
""",
    "指数/ETF": """
【指数/ETF基金分析要点】
- 重点：跟踪指数估值PE/PB历史分位、北向资金
- 买入：估值历史低位 + MA多头排列 + MACD金叉
- 卖出：估值历史高位 + 乖离率>5% + RSI>70 超买
- 严禁追高：乖离率>5%时自动标记危险，等回调至MA5附近
""",
    "股票型": """
【股票型基金分析要点】
- 重点：基金经理动态、重仓股走势、行业配置
- 买入：业绩稳健 + MA多头排列 + MACD金叉 + RSI 40-60
- 卖出：基金经理离职 + MACD死叉 + 乖离率>7%
- 技术面与基本面结合，以基本面为主
""",
    "混合/其他": """
【混合型基金分析要点】
- 综合考量股债配置比例、仓位变化趋势
- 结合MA趋势、MACD信号和乖离率综合判断
""",
}


# ════════════════════════════════════════════
#  构建分析 Prompt（含技术指标）
# ════════════════════════════════════════════
def build_analysis_prompt(data: dict) -> str:
    fund_type = detect_fund_type(data["basic_info"])
    type_guide = FUND_TYPE_PROMPTS.get(fund_type, FUND_TYPE_PROMPTS["混合/其他"])

    basic   = data["basic_info"]
    tech    = data["nav_summary"]
    market  = data["market"]
    manager = data["manager"]
    news    = data["news"]

    # 技术指标文本
    tech_lines = []
    for k, v in tech.items():
        if k not in ("最新净值",):
            tech_lines.append(f"- {k}: {v}")
    tech_text = "\n".join(tech_lines) if tech_lines else "技术数据不足"

    # 新闻文本（标注来源：实时 vs 历史）
    news_text = ""
    for i, n in enumerate(news[:8], 1):
        tag = "🔴实时" if n.get("from") == "tavily" else "📁历史"
        news_text += f"{i}. [{tag}] [{n.get('time','')}] {n.get('title','')}\n"
        if n.get("summary"):
            news_text += f"   {n['summary'][:200]}\n"

    market_text = "\n".join(f"- {k}: {v}" for k, v in market.items())
    manager_text = (
        f"基金经理：{manager.get('姓名','未知')}，任职回报：{manager.get('任期回报','未知')}"
        if manager else "基金经理信息不可用"
    )

    prompt = f"""你是资深中国公募基金分析师，请综合以下数据给出专业投资建议。

════════════════════════════════════
【基金信息】
- 代码：{data['fund_code']}
- 名称：{basic.get('基金简称', '未知')}
- 类型：{basic.get('基金类型', fund_type)}
- {manager_text}
- 数据时间：{data.get('fetch_time', '')}

【技术指标（核心）】
- 最新净值：{tech.get('最新净值', 'N/A')}
{tech_text}

【市场环境】
{market_text}

【近期新闻/公告（含实时）】
{news_text if news_text else "暂无相关新闻"}
════════════════════════════════════

{type_guide}

【技术分析参考规则】
- 多头排列（MA5>MA10>MA20）：趋势看多
- 空头排列（MA5<MA10<MA20）：趋势看空
- 乖离率>5%：超买，严禁追高，等待回调
- 乖离率<-5%：超卖，可关注买入机会
- RSI>70：超买；RSI<30：超卖
- MACD金叉：多头信号；死叉：空头信号

请输出合法 JSON（不要有其他文字）：

{{
  "verdict": "买入" | "持有" | "减仓" | "卖出" | "观望",
  "confidence": 整数0-100,
  "fund_type": "{fund_type}",
  "trend": "上升" | "震荡" | "下降",
  "risk_level": "低" | "中低" | "中" | "中高" | "高",
  "summary": "一句话核心结论（30字以内）",
  "tech_signal": "技术面综合信号描述（50字以内）",
  "bull_points": ["多头理由1", "多头理由2", "多头理由3"],
  "bear_points": ["空头/风险理由1", "空头/风险理由2"],
  "key_risks": ["风险1", "风险2"],
  "news_sentiment": "正面" | "中性" | "负面",
  "news_analysis": "新闻整体解读（100字以内）",
  "action_advice": "具体操作建议含仓位（100字以内）",
  "buy_point": "建议买入区间或条件",
  "stop_loss": "止损参考位",
  "time_horizon": "短期（1个月内）" | "中期（1-3个月）" | "长期（3个月以上）"
}}
"""
    return prompt


# ════════════════════════════════════════════
#  调用 DeepSeek
# ════════════════════════════════════════════
def analyze_fund(data: dict, api_key: str = None) -> dict:
    client = get_client(api_key)
    prompt = build_analysis_prompt(data)

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是专业中国公募基金分析师，擅长结合技术指标、新闻舆情和宏观环境综合研判基金买卖时机。"
                        "请严格按照要求的JSON格式输出，不添加任何额外说明。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1800,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        result = json.loads(raw)
        result["_tokens"] = {
            "prompt": resp.usage.prompt_tokens,
            "completion": resp.usage.completion_tokens,
        }
        return result

    except json.JSONDecodeError as e:
        return {"error": f"JSON解析失败: {e}"}
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════
#  格式化文字报告（用于推送）
# ════════════════════════════════════════════
def format_report(data: dict, analysis: dict) -> str:
    if "error" in analysis:
        return f"❌ 分析失败：{analysis['error']}"

    emoji_map = {"买入": "🟢", "持有": "🔵", "减仓": "🟡", "卖出": "🔴", "观望": "⚪"}
    trend_map = {"上升": "📈", "震荡": "↔️", "下降": "📉"}

    v     = analysis.get("verdict", "观望")
    trend = analysis.get("trend", "震荡")
    tech  = data.get("nav_summary", {})

    return f"""
╔══════════════════════════════════════════╗
║  基金分析报告  {data.get('fetch_time', '')}
╚══════════════════════════════════════════╝

{data['basic_info'].get('基金简称', data['fund_code'])}（{data['fund_code']}）
类型：{analysis.get('fund_type','未知')} | 趋势：{trend_map.get(trend,'')} {trend} | 风险：{analysis.get('risk_level','未知')}

┌──────────────────────────────────────────┐
│  {emoji_map.get(v,'⚪')} 结论：{v}  （置信度 {analysis.get('confidence',0)}%）
│  {analysis.get('summary','')}
└──────────────────────────────────────────┘

📊 技术信号：{analysis.get('tech_signal','')}
   MA状态：{'多头排列✅' if tech.get('多头排列') else '空头排列⚠️' if tech.get('空头排列') else '中性'}
   乖离率：{tech.get('乖离率_MA20','N/A')}%  {tech.get('乖离率_风险','')}
   RSI：{tech.get('RSI_14','N/A')} ({tech.get('RSI_信号','')})
   MACD：{tech.get('MACD_信号','')}

📰 新闻情绪：{analysis.get('news_sentiment','中性')}
{analysis.get('news_analysis','')}

✅ 多头理由：
{chr(10).join(f'  • {p}' for p in analysis.get('bull_points',[]))}

⚠️  谨慎因素：
{chr(10).join(f'  • {p}' for p in analysis.get('bear_points',[]))}

💡 操作建议（{analysis.get('time_horizon','')}）：
  {analysis.get('action_advice','')}
  买入参考：{analysis.get('buy_point','—')}
  止损参考：{analysis.get('stop_loss','—')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 本报告由AI生成，仅供参考，不构成投资建议。
"""
