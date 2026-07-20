"""
微信推送模块
通过 PushPlus 将报告推送到用户微信。
"""

import logging
import os
from datetime import datetime
from typing import Any

import requests

from src.common import format_date_cn

logger = logging.getLogger(__name__)

PUSHPLUS_URL = "https://www.pushplus.plus/send"


def push_report(
    title: str,
    content: str,
    token: str | None = None,
    topic: str = "",
    template: str = "markdown",
) -> dict[str, Any]:
    """
    推送一条消息到微信。

    参数:
        title: 消息标题
        content: 消息正文（支持 markdown/html）
        token: PushPlus token，默认读环境变量
        topic: 推送主题（不同 topic = 不同群组/对话），留空=默认通道
        template: 消息格式 html/markdown/txt
    """
    if token is None:
        token = os.getenv("PUSHPLUS_TOKEN", "")

    if not token:
        logger.error("未设置 PUSHPLUS_TOKEN")
        return {"error": "未设置 PUSHPLUS_TOKEN"}

    payload: dict[str, str] = {
        "token": token,
        "title": title,
        "content": content,
        "template": template,
    }
    if topic:
        payload["topic"] = topic

    try:
        resp = requests.post(PUSHPLUS_URL, json=payload, timeout=15)
        result = resp.json()
        if result.get("code") == 200:
            logger.info(f"推送成功: {title}")
        else:
            logger.error(f"推送失败: {result}")
        return result
    except requests.RequestException as e:
        logger.error(f"PushPlus 请求异常: {e}")
        return {"error": str(e)}


def format_report_for_wechat(ai_report: str, header_info: str = "") -> str:
    """
    将 AI 生成的报告格式化为适合微信阅读的版本。
    """
    header = f"**📊 投资报告**  {header_info}\n\n" if header_info else ""
    footer = "\n\n*⚠️ AI生成 · 仅供参考 · 不构成投资指令*"
    return header + ai_report + footer


def push_investment_report(ai_report: str, token: str | None = None) -> dict[str, Any]:
    """
    便捷方法：推送投资报告。
    """
    date_str, weekday = format_date_cn()
    header = f"{date_str} {weekday}"

    title = f"📊 投资报告 | {header}"
    topic = os.getenv("PUSHPLUS_TOPIC_INVEST", "")
    content = format_report_for_wechat(ai_report, header)

    return push_report(
        title=title,
        content=content,
        token=token,
        topic=topic,
        template="markdown",
    )


def push_morning_report(report: str, token: str | None = None) -> dict[str, Any]:
    """
    便捷方法：推送晨报。
    """
    date_str, weekday = format_date_cn()
    title = f"🌅 晨报 | {date_str} {weekday}"
    content = f"{report}\n\n*Dan Koe · 每日自动聚合 · {date_str}*"

    return push_report(
        title=title,
        content=content,
        token=token,
        topic="",
        template="markdown",
    )


def push_error_notification(error_msg: str, source: str = "investment-bot",
                            token: str | None = None) -> dict[str, Any]:
    """
    推送运行失败通知。
    """
    date_str, weekday = format_date_cn()
    title = f"⚠️ Bot异常 | {source} | {date_str} {weekday}"
    content = f"**{source}** 运行异常\n\n```\n{error_msg}\n```\n\n请检查 GitHub Actions 日志。"

    return push_report(
        title=title,
        content=content,
        token=token,
        topic="",
        template="markdown",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = push_report(
        title="测试推送",
        content="## 这是一条测试消息\n\n如果你在微信里看到这条消息，说明 **PushPlus 配置成功** ✅",
        template="markdown",
    )
    print(result)
