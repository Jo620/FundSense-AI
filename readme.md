# 🧠 FundSense AI — 支付宝基金智能分析 Agent

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red?logo=streamlit)
![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-purple)
![License](https://img.shields.io/badge/License-MIT-green)

**基于 DeepSeek AI + 实时新闻 + 技术指标，一键研判基金买卖时机**

[快速开始](#-快速开始) · [功能介绍](#-功能介绍) · [获取 API Key](#-获取-api-key) · [本地部署](#-本地部署)

</div>

---

## ✨ 功能介绍

| 功能 | 说明 |
|------|------|
| 🌐 **实时新闻搜索** | 接入 Tavily API，自动搜索基金最新动态，标注实时/历史来源 |
| 📊 **技术指标分析** | MA均线、MACD金叉死叉、RSI超买超卖、乖离率超买预警 |
| 🤖 **AI 综合研判** | DeepSeek 结合新闻 + 技术面 + 宏观环境给出买卖结论 |
| 📈 **净值走势图** | 可视化近90日净值 + 均线叠加 + MACD/RSI 图表 |
| 📤 **多渠道推送** | 分析完自动推送到企业微信 / 飞书 / Telegram / 邮件 |
| 🏦 **全类型基金** | 支持股票型、指数ETF、债券型、货币型（余额宝类） |

### 分析结论说明

| 结论 | 含义 |
|------|------|
| 🟢 买入 | 估值低位 + 多头排列 + 新闻正面，建议积极买入 |
| 🔵 持有 | 趋势中性，无明显买卖信号，继续持有 |
| 🟡 减仓 | 出现风险信号，建议逐步降低仓位 |
| 🔴 卖出 | 空头排列 + 超买 + 新闻负面，建议清仓 |
| ⚪ 观望 | 信号矛盾或数据不足，等待明朗 |

---

## 🔑 获取 API Key

### 1. DeepSeek API Key（必填）

1. 访问 [platform.deepseek.com](https://platform.deepseek.com) 注册账号
2. 进入顶部导航「API Keys」→ 点击「创建 API Key」
3. 复制生成的 `sk-` 开头的密钥保存好

> 💡 新用户赠送免费额度，分析基金完全够用

### 2. Tavily API Key（推荐，实时新闻）

1. 访问 [tavily.com](https://tavily.com) 免费注册
2. 登录后在 Dashboard 的「API Keys」区域找到 `tvly-dev-` 开头的密钥
3. 免费额度：**1000 次/月**

> 不填此 Key 也可以运行，但新闻数据时效性较差

### 3. 推送通知 Key（可选）

<details>
<summary>📱 企业微信机器人</summary>

1. 打开企业微信群 → 右上角「...」→「添加群机器人」→「新建机器人」
2. 复制 Webhook URL（格式：`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx`）

</details>

<details>
<summary>🪐 飞书机器人</summary>

1. 飞书群右上角「设置」→「机器人」→「添加机器人」→「自定义机器人」
2. 复制生成的 Webhook URL

</details>

<details>
<summary>✈️ Telegram Bot</summary>

1. Telegram 搜索 `@BotFather`，发送 `/newbot` 创建机器人，获取 `Bot Token`
2. 给机器人发一条消息，访问以下地址获取 Chat ID：
   ```
   https://api.telegram.org/bot<你的Token>/getUpdates
   ```
   返回 JSON 中找 `"chat":{"id": 这里的数字}`

</details>

<details>
<summary>📧 邮件（QQ / 163 / Gmail）</summary>

以 QQ 邮箱为例：
1. 登录 QQ 邮箱 → 设置 → 账户 → POP3/SMTP 服务 → 开启
2. 按提示获取**授权码**（注意不是登录密码）
3. `EMAIL_SENDER` 填你的邮箱，`EMAIL_PASSWORD` 填授权码

</details>

---

## 🚀 本地部署

### 环境要求

- Python 3.10+

### 部署步骤

**第一步：克隆项目**

```bash
git clone https://github.com/your-username/FundSense-AI.git
cd FundSense-AI
```

**第二步：安装依赖**

```bash
pip install -r requirements.txt
```

**第三步：配置 API Key**

```bash
cp .env.example .env
```

用任意编辑器打开 `.env`，填入你的 Key：

```env
# ✅ 必填
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥

# 📰 推荐填写（实时新闻）
TAVILY_API_KEY=tvly-dev-你的Tavily密钥

# 📤 推送通知（可选，填哪个推哪个）
WECHAT_WEBHOOK_URL=
FEISHU_WEBHOOK_URL=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
EMAIL_SENDER=your@qq.com
EMAIL_PASSWORD=邮箱授权码
EMAIL_RECEIVERS=收件人@example.com
```

**第四步：启动**

```bash
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`，左侧显示 `✅ Key 已从 .env 加载` 即配置成功。

**第五步：输入基金代码，点「🚀 一键分析」**

---

## 📦 项目结构

```
FundSense-AI/
├── app.py              # Streamlit Web UI
├── data_fetcher.py     # 数据采集 + 技术指标计算
├── analyzer.py         # DeepSeek LLM 分析
├── notifier.py         # 多渠道推送通知
├── requirements.txt    # 依赖列表
├── .env.example        # 环境变量示例（不含真实密钥）
└── README.md
```

---

## 🏦 常用基金代码

| 基金名称 | 代码 | 类型 |
|---------|------|------|
| 华泰柏瑞沪深300ETF | 510300 | 指数ETF |
| 天弘余额宝 | 000198 | 货币型 |
| 易方达蓝筹精选 | 005827 | 股票型 |
| 富国天惠成长混合 | 161005 | 混合型 |
| 易方达裕丰回报债券 | 110022 | 债券型 |

---

## 🛠 技术栈

- **Web UI**：Streamlit
- **数据采集**：akshare + Tavily Search API
- **技术指标**：pandas + numpy（MA / RSI / MACD / 乖离率）
- **AI 分析**：DeepSeek API（兼容 OpenAI 格式）
- **可视化**：Plotly
- **推送**：企业微信 / 飞书 / Telegram / SMTP 邮件

---

## ⚠️ 免责声明

本项目仅供学习研究使用，**不构成任何投资建议**。投资有风险，请结合自身情况理性决策，作者不对任何投资损失负责。

---

<div align="center">
如果觉得有帮助，欢迎给个 ⭐ Star！<br>
Made with ❤️ · Powered by DeepSeek AI
</div>