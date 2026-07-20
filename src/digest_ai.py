"""
晨间晨报 — AI 摘要模块
将 Dan Koe 的博客和推文通过 DeepSeek 翻译+提炼为中文晨报。
"""

import logging
import os
from typing import Any

from src.llm import create_deepseek_client, DEEPSEEK_MODEL, DEFAULT_DIGEST_TEMP, DEFAULT_DIGEST_TOKENS

logger = logging.getLogger(__name__)

MORNING_SYSTEM_PROMPT = """你是 Dan Koe 的中文内容编辑。用户每天早上读你的推送来获取 Dan Koe 最新的思想精华。

格式要求（非常重要）：
- 推文和博客分开，推文在前，博客在后
- 每条翻译要保留 Dan Koe 的直接、有冲击力的语调，不要软化成鸡汤
- 每条内容后面用小字标注来源类型
- 最后选一条"今日必读"，用 > 引用块突出
- 整篇控制在手机两屏以内

如果没有新内容（只有[往期]标记的文章）：
- 回顾那篇往期文章的精华，标注"今日回顾"
- 简短即可，不用硬凑长度

排版规则：
- 用 --- 分隔不同板块
- 每条用 • 开头
- 英文人名、书名、专业术语保留原文并括号翻译
- 不要用过多emoji，保持干净"""


def build_digest_prompt(items: list[dict[str, Any]], timestamp: str) -> str:
    """把抓取到的内容组装成 prompt"""
    if not items:
        return "今天 Dan Koe 没有发布新内容。请生成一条简短的'今日无更新'晨报，回顾一句Dan Koe的经典理念，鼓励读者保持 consistency。"

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

    # 标记哪些是回退的往期内容
    fallback = [i for i in items if "[往期]" in i.get("title", "")]
    if fallback:
        lines.append("注意：以上有[往期]标记的不是新内容，是今天没新内容做的回退。")

    return "\n".join(lines)


def generate_digest(items: list[dict[str, Any]], api_key: str | None = None) -> dict[str, str]:
    """调用 DeepSeek 生成晨间摘要"""
    if api_key is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")

    if not api_key:
        return {"error": "未设置 DEEPSEEK_API_KEY"}

    if not items:
        # 完全没内容时给一个 fallback
        return {"report": (
            "**今天 Dan Koe 还没发新内容。**\n\n"
            "> Consistency beats intensity.\n"
            "> 他没发，不等于你不该做你的事。"
        )}

    from datetime import datetime
    now = datetime.now()
    weekday_list = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
    weekday = weekday_list[now.weekday()]
    timestamp = now.strftime("%Y.%m.%d") + " " + weekday

    try:
        client = create_deepseek_client(api_key)
        user_prompt = build_digest_prompt(items, timestamp)

        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": MORNING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=DEFAULT_DIGEST_TEMP,
            max_tokens=DEFAULT_DIGEST_TOKENS,
        )

        report = response.choices[0].message.content or ""
        return {"report": report}
    except Exception as e:
        logger.error(f"DeepSeek 摘要生成失败: {e}")
        return {"error": str(e)}
