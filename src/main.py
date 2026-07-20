"""
投资顾问机器人 — 主入口
每天21:00运行：抓取数据 → AI分析 → 推送到微信
"""

import logging
import os
import sys

from src.common import disable_proxy

disable_proxy()

from dotenv import load_dotenv

load_dotenv()

from src.fetch_data import fetch_all, save_cache
from src.analyze import analyze
from src.push_wechat import push_investment_report, push_error_notification


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("main")

    token = os.getenv("PUSHPLUS_TOKEN", "")

    # ── Step 1: 抓取数据 ──
    logger.info("=" * 50)
    logger.info("Step 1/3: 抓取基金和市场数据...")
    try:
        data = fetch_all()
        save_cache(data)
        logger.info("数据抓取完成，已缓存到 data/latest_data.json")
    except Exception as e:
        logger.error(f"数据抓取失败: {e}")
        if token:
            push_error_notification(f"数据抓取失败: {e}", "investment-bot", token)
        return 1

    # ── Step 2: AI 分析 ──
    logger.info("Step 2/3: DeepSeek 生成投资建议...")
    result = analyze(data)
    if "error" in result:
        logger.error(f"AI 分析失败: {result['error']}")
        if token:
            push_error_notification(f"AI分析失败: {result['error']}", "investment-bot", token)
        return 1

    report = result["report"]
    logger.info(f"AI 报告生成完成 ({len(report)} 字符)")

    # ── Step 3: 推送到微信 ──
    logger.info("Step 3/3: 推送到微信...")
    push_result = push_investment_report(report)
    if "error" in push_result:
        logger.error(f"推送失败: {push_result['error']}")
        return 1

    logger.info("✅ 投资报告推送完成!")
    logger.info("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
