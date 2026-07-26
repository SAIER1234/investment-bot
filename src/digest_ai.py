"""
晨间晨报 — AI 摘要模块
有 Dan Koe 新内容时翻译+提炼，没有时生成投资大师+斯多葛每日智慧。
"""

import logging
import os
from datetime import datetime
from typing import Any

from src.llm import create_deepseek_client, DEEPSEEK_MODEL, DEFAULT_DIGEST_TEMP, DEFAULT_DIGEST_TOKENS

logger = logging.getLogger(__name__)

DAN_KOE_PROMPT = """你是 Dan Koe 的中文内容编辑。用户每天早上读你的推送获取 Dan Koe 的最新思想。

格式要求：
- 推文和博客分开，推文在前博客在后
- 每条翻译保留 Dan Koe 直接有冲击力的语调，不软化成鸡汤
- 最后选一条"今日必读"，用 > 引用块突出
- 整篇手机两屏以内

排版：用 --- 分隔板块，每条用 • 开头。不要过多emoji。"""

WISDOM_PROMPT = """你是用户的晨间智慧导师。今天没有Dan Koe新内容，请生成一段投资哲学+斯多葛智慧的晨间推送。

内容来源（轮换使用，每天选一个方向）：
- 投资大师语录：巴菲特、芒格、霍华德·马克斯、彼得·林奇、查理·芒格
- 斯多葛哲学：马可·奥勒留《沉思录》、塞涅卡、爱比克泰德
- 投资经典金句：《投资最重要的事》《穷查理宝典》《聪明的投资者》《股票作手回忆录》
- 市场心理学：恐惧与贪婪、耐心、纪律、逆向思维

格式：
1. 用 > 引用块放一句今日核心语录（注明出处）
2. 用3-5句话解读这句话——和投资有什么关系，和当下的市场有什么联系
3. 最后给一个"今日思考"——一个开放性问题让用户今天想一想
4. 整篇控制在手机一屏以内

语调：像聪明朋友在早餐桌上聊天。不说教，不鸡汤化。保持智识的锋利感。"""


def has_fresh_content(items: list[dict[str, Any]]) -> bool:
    """判断是否有新内容（非回退往期）"""
    if not items:
        return False
    for item in items:
        if "[往期]" not in item.get("title", ""):
            return True
    return False


def build_digest_prompt(items: list[dict[str, Any]], timestamp: str) -> str:
    """把抓取到的内容组装成 prompt"""
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

    fresh = has_fresh_content(items)
    now = datetime.now()
    weekday_list = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
    weekday = weekday_list[now.weekday()]
    timestamp = now.strftime("%Y.%m.%d") + " " + weekday

    try:
        client = create_deepseek_client(api_key)

        if fresh:
            system_prompt = DAN_KOE_PROMPT
            user_prompt = build_digest_prompt(items, timestamp)
            temp = DEFAULT_DIGEST_TEMP
            max_tok = DEFAULT_DIGEST_TOKENS
        else:
            # 用日期作为随机种子，让每天选的语录方向不同
            day_seed = now.day
            system_prompt = WISDOM_PROMPT
            user_prompt = (
                f"今天是{timestamp}。请生成今日晨间智慧推送。\n"
                f"今天的日期数字是{day_seed}，可以用它来选一个主题方向"
                f"（{day_seed}%4==0→巴菲特/芒格, ==1→斯多葛, ==2→投资经典, ==3→市场心理学）。"
            )
            temp = 0.9  # 更高温度让鸡汤每天不一样
            max_tok = 1024

        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temp,
            max_tokens=max_tok,
        )

        report = response.choices[0].message.content or ""
        return {"report": report}
    except Exception as e:
        logger.error(f"DeepSeek 摘要生成失败: {e}")
        return {"error": str(e)}
