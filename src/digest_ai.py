"""
晨间晨报 — AI 摘要模块
将抓取到的内容通过 DeepSeek 翻译+总结为中文晨报格式。
"""

import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

MORNING_SYSTEM_PROMPT = """你是一个晨间阅读摘要助手。用户是一位中国学生，希望每天早上读到来自海外优质创作者的精华内容。

你的任务：
1. 把每条英文内容翻译成流畅的中文
2. 按创作者分组，每条1-3句话概括核心观点
3. 在每条后面标注来源（创作者名字 + 链接）
4. 最后选一条"今日最佳"（最值得深思的一条）

格式要求：
- 用 markdown 排版
- 每条不要太长，适合手机屏幕阅读
- 语调：温暖激励但不鸡汤，像是聪明朋友在和你聊天
- 最后加一句今日"心灵鸡汤"式的总结（但要基于实际内容，不要空洞）"""


def build_digest_prompt(items: list[dict[str, Any]], timestamp: str) -> str:
    """把抓取到的内容组装成 prompt"""
    if not items:
        return "今天没有抓到新内容，请生成一条简短的说明。"

    lines = [f"以下是{timestamp}抓取的海外创作者内容，请生成晨间摘要。\n"]

    # 按来源分组
    from collections import defaultdict
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[item["source"]].append(item)

    for source, source_items in grouped.items():
        lines.append(f"## {source}")
        for item in source_items:
            stype = "🐦推文" if item.get("source_type") == "twitter" else "📝博客"
            lines.append(f"- [{stype}] {item['title']}")
            if item.get("url"):
                lines.append(f"  链接: {item['url']}")
            if item.get("summary") and item["summary"] != item["title"]:
                summary = item["summary"][:500]
                lines.append(f"  摘要: {summary}")
        lines.append("")

    return "\n".join(lines)


def generate_digest(items: list[dict[str, Any]], api_key: str | None = None) -> dict[str, str]:
    """调用 DeepSeek 生成晨间摘要"""
    if api_key is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")

    if not api_key:
        return {"error": "未设置 DEEPSEEK_API_KEY"}

    if not items:
        return {"report": "🌅 **今日晨报**\n\n今天没有新的内容更新。\n\n> 没有新闻就是最好的新闻 —— 去创造属于你自己的内容吧 ✨"}

    from datetime import datetime
    now = datetime.now()
    timestamp = now.strftime("%Y年%m月%d日") + ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][
        now.weekday()
    ]

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


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dotenv import load_dotenv
    load_dotenv()

    from src.morning_digest import fetch_all
    logging.basicConfig(level=logging.INFO)

    print("抓取内容...")
    items = fetch_all()
    print(f"共 {len(items)} 条")
    print("\n生成摘要...")
    result = generate_digest(items)
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        print(result["report"])
