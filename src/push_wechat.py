"""
微信推送模块
通过 PushPlus 将报告推送到用户微信。
注册: https://www.pushplus.plus/ → 微信扫码 → 获取 token
不同 topic 对应不同"对话窗口"（在微信里显示为不同发送者）。
"""

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

PUSHPLUS_URL = "http://www.pushplus.plus/send"


def push_report(
    title: str,
    content: str,
    token: str | None = None,
    topic: str = "investment",
    template: str = "markdown",
) -> dict[str, Any]:
    """
    推送一条消息到微信。

    参数:
        title: 消息标题
        content: 消息正文（支持 markdown/html）
        token: PushPlus token，默认读环境变量
        topic: 推送主题（不同 topic = 不同群组/对话）
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
    # topic 可选：需先在 PushPlus 后台创建群组，否则传了反而报错
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


def format_report_for_wechat(ai_report: str, timestamp: str) -> str:
    """
    将 AI 生成的报告格式化为适合微信阅读的版本。
    """
    header = f"**📊 投资报告**  {timestamp}\n\n"
    footer = "\n\n*⚠️ AI生成 · 仅供参考 · 不构成投资指令*"
    return header + ai_report + footer


def push_investment_report(ai_report: str, token: str | None = None) -> dict[str, Any]:
    """
    便捷方法：推送投资报告。
    """
    from datetime import datetime
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]

    title = f"📊 投资报告 | {date_str} {weekday}"
    # topic 留空：不在 PushPlus 创建群组则无需 topic
    topic = os.getenv("PUSHPLUS_TOPIC_INVEST", "")
    content = format_report_for_wechat(ai_report, f"{date_str} {weekday}")

    return push_report(
        title=title,
        content=content,
        token=token,
        topic=topic,
        template="markdown",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 简单测试
    result = push_report(
        title="测试推送",
        content="## 这是一条测试消息\n\n如果你在微信里看到这条消息，说明 **PushPlus 配置成功** ✅",
        topic="test",
        template="markdown",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
