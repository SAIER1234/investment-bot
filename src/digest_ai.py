"""
晨间晨报 — AI 摘要模块
将 Dan Koe 的博客和推文通过 DeepSeek 翻译+提炼为中文晨报。
"""

import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

MORNING_SYSTEM_PROMPT = """你是 Dan Koe 的中文内容编辑。用户每天早上读你的推送来获取 Dan Koe 最新的思想精华。

格式要求（非常重要）：
- 推文和博客分开，推文在前，博客在后
- 每条翻译要保留 Dan Koe 的直接、有冲击力的语调，不要软化成鸡汤
- 每条内容后面用小字标注来源类型
- 最后选一条"今日必读"，用 > 引用块突出
- 整篇控制在手机两屏以内

排版规则：
- 用 --- 分隔不同板块
- 每条用 • 开头
- 英文人名、书名、专业术语保留原文并括号翻译
- 不要用过多emoji，保持干净"""


def build_digest_prompt(items: list[dict[str, Any]], timestamp: str) -> str:
    """把抓取到的内容组装成 prompt"""
    if not items:
        return "今天 Dan Koe 没有发布新内容。昨天没发不代表明天不发 —— consistency beats intensity."

    blogs = [i for i in items if i.get("source_type") == "blog"]
    tweets = [i for i in items if i.get("source_type") == "twitter"]

    lines = [f"Dan Koe 最近内容 ({timestamp}):\n"]

    if tweets:
        lines.append("## 推文")
        for i, t in enumerate(tweets, 1):
            lines.append(f"{i}. {t['title']}")
        lines.append("")

    if blogs:
        lines.append("## 博客")
        for i, b in enumerate(blogs, 1):
            lines.append(f"{i}. 标题: {b['title']}")
            lines.append(f"   链接: {b['url']}")
            summary = b.get("summary", "")[:800]
            if summary:
                lines.append(f"   摘要: {summary}")
        lines.append("")

    return "\n".join(lines)


def generate_digest(items: list[dict[str, Any]], api_key: str | None = None) -> dict[str, str]:
    """调用 DeepSeek 生成晨间摘要"""
    if api_key is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")

    if not api_key:
        return {"error": "未设置 DEEPSEEK_API_KEY"}

    if not items:
        return {"report": (
            "**今天 Dan Koe 还没发新内容。**\n\n"
            "> Consistency beats intensity.\n"
            "> 他没发，不等于你不该做你的事。"
        )}

    from datetime import datetime
    now = datetime.now()
    weekday = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][now.weekday()]
    timestamp = now.strftime("%Y.%m.%d") + " " + weekday

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        user_prompt = build_digest_prompt(items, timestamp)

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": MORNING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=2048,
        )

        report = response.choices[0].message.content or ""
        return {"report": report}
    except Exception as e:
        logger.error(f"DeepSeek 摘要生成失败: {e}")
        return {"error": str(e)}
