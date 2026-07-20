"""
投资顾问机器人 — 主入口
每天收盘后运行：抓取数据 → AI分析 → 推送到微信
"""

import logging
import os
import sys

# ── 禁用代理 ────────────────────────────────────────────
for _key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
             "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
    os.environ.pop(_key, None)
os.environ["no_proxy"] = "*"
try:
    import urllib.request
    urllib.request.getproxies = lambda: {}
except Exception:
    pass

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

from src.fetch_data import fetch_all, save_cache
from src.analyze import analyze
from src.push_wechat import push_investment_report


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("main")

    # ── Step 1: 抓取数据 ──
    logger.info("=" * 50)
    logger.info("Step 1/3: 抓取基金和市场数据...")
    try:
        data = fetch_all()
        save_cache(data)
        logger.info("数据抓取完成，已缓存到 data/latest_data.json")
    except Exception as e:
        logger.error(f"数据抓取失败: {e}")
        return 1

    # ── Step 2: AI 分析 ──
    logger.info("Step 2/3: DeepSeek 生成投资建议...")
    result = analyze(data)
    if "error" in result:
        logger.error(f"AI 分析失败: {result['error']}")
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
