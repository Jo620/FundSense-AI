"""
推送通知模块
支持：企业微信 / 飞书 / Telegram / 邮件（SMTP）
"""

import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


# ════════════════════════════════════════════
#  企业微信 Webhook
# ════════════════════════════════════════════
def send_wechat(text: str, webhook_url: str = None) -> bool:
    url = webhook_url or os.getenv("WECHAT_WEBHOOK_URL", "")
    if not url:
        return False
    try:
        resp = requests.post(
            url,
            json={"msgtype": "text", "text": {"content": text}},
            timeout=10,
        )
        return resp.json().get("errcode", -1) == 0
    except Exception as e:
        print(f"  企业微信推送失败: {e}")
        return False


# ════════════════════════════════════════════
#  飞书 Webhook
# ════════════════════════════════════════════
def send_feishu(text: str, webhook_url: str = None) -> bool:
    url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL", "")
    if not url:
        return False
    try:
        resp = requests.post(
            url,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"  飞书推送失败: {e}")
        return False


# ════════════════════════════════════════════
#  Telegram Bot
# ════════════════════════════════════════════
def send_telegram(text: str, token: str = None, chat_id: str = None) -> bool:
    token   = token   or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text[:4000],   # Telegram 限制 4096 字符
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        return resp.json().get("ok", False)
    except Exception as e:
        print(f"  Telegram推送失败: {e}")
        return False


# ════════════════════════════════════════════
#  邮件 SMTP
# ════════════════════════════════════════════
def send_email(subject: str, body: str,
               sender: str = None, password: str = None,
               receivers: str = None) -> bool:
    sender    = sender    or os.getenv("EMAIL_SENDER", "")
    password  = password  or os.getenv("EMAIL_PASSWORD", "")
    receivers = receivers or os.getenv("EMAIL_RECEIVERS", sender)

    if not sender or not password:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender
        msg["To"]      = receivers

        # 纯文本版本
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # HTML 版本（简单格式化）
        html_body = f"""
        <html><body>
        <pre style="font-family:monospace;font-size:14px;line-height:1.6">
{body}
        </pre>
        </body></html>
        """
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # 自动识别 SMTP 服务器（QQ/163/Gmail）
        smtp_map = {
            "qq.com":    ("smtp.qq.com", 587),
            "163.com":   ("smtp.163.com", 465),
            "126.com":   ("smtp.126.com", 465),
            "gmail.com": ("smtp.gmail.com", 587),
            "outlook.com": ("smtp-mail.outlook.com", 587),
        }
        domain = sender.split("@")[-1].lower()
        host, port = smtp_map.get(domain, ("smtp." + domain, 587))

        if port == 465:
            import ssl
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=ctx) as server:
                server.login(sender, password)
                server.sendmail(sender, receivers.split(","), msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, receivers.split(","), msg.as_string())

        return True
    except Exception as e:
        print(f"  邮件推送失败: {e}")
        return False


# ════════════════════════════════════════════
#  一键推送（自动识别已配置渠道）
# ════════════════════════════════════════════
def push_report(report_text: str, fund_name: str = "",
                config: dict = None) -> dict:
    """
    一键推送分析报告到所有已配置渠道
    config 可覆盖 .env 中的配置，格式：
    {
        "wechat_webhook": "...",
        "feishu_webhook": "...",
        "telegram_token": "...",
        "telegram_chat_id": "...",
        "email_sender": "...",
        "email_password": "...",
        "email_receivers": "...",
    }
    """
    config = config or {}
    results = {}
    subject = f"📊 基金分析报告 - {fund_name}" if fund_name else "📊 基金分析报告"

    # 企业微信
    wechat_url = config.get("wechat_webhook") or os.getenv("WECHAT_WEBHOOK_URL", "")
    if wechat_url:
        ok = send_wechat(report_text, wechat_url)
        results["企业微信"] = "✅ 成功" if ok else "❌ 失败"

    # 飞书
    feishu_url = config.get("feishu_webhook") or os.getenv("FEISHU_WEBHOOK_URL", "")
    if feishu_url:
        ok = send_feishu(report_text, feishu_url)
        results["飞书"] = "✅ 成功" if ok else "❌ 失败"

    # Telegram
    tg_token   = config.get("telegram_token")   or os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat_id = config.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID", "")
    if tg_token and tg_chat_id:
        ok = send_telegram(report_text, tg_token, tg_chat_id)
        results["Telegram"] = "✅ 成功" if ok else "❌ 失败"

    # 邮件
    email_sender   = config.get("email_sender")    or os.getenv("EMAIL_SENDER", "")
    email_password = config.get("email_password")  or os.getenv("EMAIL_PASSWORD", "")
    if email_sender and email_password:
        ok = send_email(
            subject, report_text,
            sender=email_sender,
            password=email_password,
            receivers=config.get("email_receivers") or os.getenv("EMAIL_RECEIVERS", email_sender),
        )
        results["邮件"] = "✅ 成功" if ok else "❌ 失败"

    if not results:
        results["提示"] = "未配置任何推送渠道，请在 .env 中配置"

    return results
