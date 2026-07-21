"""
投资顾问机器人 — 主入口
每天21:00运行：抓取数据 → (周五)全网扫描 → AI分析 → 推送到微信
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
from src.fund_scanner import scan_if_needed


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("main")

    token = os.getenv("PUSHPLUS_TOKEN", "")

    # ── Step 1: 抓取数据 ──
    logger.info("=" * 50)
    logger.info("Step 1/4: 抓取基金和市场数据...")
    try:
        data = fetch_all()
        save_cache(data)
        logger.info("数据抓取完成，已缓存到 data/latest_data.json")
    except Exception as e:
        logger.error(f"数据抓取失败: {e}")
        if token:
            push_error_notification(f"数据抓取失败: {e}", "investment-bot", token)
        return 1

    # ── Step 2: 全网基金扫描（仅周五或超过7天） ──
    logger.info("Step 2/4: 检查是否需要全网基金扫描...")
    scanner_data = None
    try:
        scanner_data = scan_if_needed()
        if scanner_data and scanner_data.get("candidates"):
            logger.info(f"基金扫描完成: {len(scanner_data['candidates'])} 支候选")
        else:
            logger.info("今日无需扫描（复用缓存）")
    except Exception as e:
        logger.warning(f"基金扫描失败（非致命）: {e}")

    # ── Step 3: AI 分析 ──
    logger.info("Step 3/4: DeepSeek 生成投资建议...")
    result = analyze(data, scanner_data=scanner_data)
    if "error" in result:
        logger.error(f"AI 分析失败: {result['error']}")
        if token:
            push_error_notification(f"AI分析失败: {result['error']}", "investment-bot", token)
        return 1

    report = result["report"]
    logger.info(f"AI 报告生成完成 ({len(report)} 字符)")

    # ── Step 4: 推送到微信 ──
    logger.info("Step 4/4: 推送到微信...")
    push_result = push_investment_report(report)
    if "error" in push_result:
        logger.error(f"推送失败: {push_result['error']}")
        return 1

    logger.info("✅ 投资报告推送完成!")
    logger.info("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
