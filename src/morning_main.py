"""
晨间晨报机器人 — 主入口
每天早上8点运行：抓取博客/Twitter内容 → DeepSeek翻译摘要 → 推送到微信
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from src.morning_digest import fetch_all
from src.digest_ai import generate_digest
from src.push_wechat import push_report as _push


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("morning_main")

    # ── Step 1: 抓取内容 ──
    logger.info("=" * 50)
    logger.info("Step 1/3: 抓取博客和推文...")
    try:
        items = fetch_all()
        logger.info(f"共抓取 {len(items)} 条内容")
    except Exception as e:
        logger.error(f"内容抓取失败: {e}")
        return 1

    # ── Step 2: AI 摘要 ──
    logger.info("Step 2/3: DeepSeek 生成晨报...")
    result = generate_digest(items)
    if "error" in result:
        logger.error(f"AI 摘要失败: {result['error']}")
        return 1

    report = result["report"]
    logger.info(f"晨报生成完成 ({len(report)} 字符)")

    # ── Step 3: 推送到微信 ──
    logger.info("Step 3/3: 推送到微信...")
    from datetime import datetime
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]

    content = (
        f"{report}"
        f"\n\n*Dan Koe · 每日自动聚合 · {date_str}*"
    )

    push_result = _push(
        title=f"🌅 晨报 | {date_str} {weekday}",
        content=content,
        topic="",  # 不用 topic，默认推送通道
        template="markdown",
    )

    code = push_result.get("code", -1)
    if code == 200:
        logger.info("✅ 晨报推送完成!")
    else:
        logger.error(f"推送失败: {push_result}")

    logger.info("=" * 50)
    return 0 if code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
