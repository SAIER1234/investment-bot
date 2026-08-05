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
from src.industry_monitor import monthly_scan, format_industry_prompt
from src.logic_verifier import take_snapshot, verify, format_verification
from src.global_rotation import fetch_global_rotation_data
from src.fundamental_check import check_all_holdings, format_fundamental_prompt
from datetime import date


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

    # ── Step 2.5: 逻辑验证 + 月度行业扫描 ──
    logic_check = None
    industry_signals = None

    # PE快照（每次运行都拍，积累历史数据）
    try:
        take_snapshot()
    except Exception as e:
        logger.warning(f"PE快照失败（非致命）: {e}")

    # 逻辑验证（每次运行都做）
    try:
        check_result = verify()
        if "error" not in check_result:
            logic_check = format_verification(check_result)
            logger.info("逻辑验证完成")
    except Exception as e:
        logger.warning(f"逻辑验证失败（非致命）: {e}")

    # 月度行业扫描 + 基本面验证（仅每月第一天）
    if date.today().day == 1:
        logger.info("月度行业信号扫描...")
        try:
            signals = monthly_scan()
            industry_signals = format_industry_prompt(signals)
            logger.info("月度行业扫描完成")
        except Exception as e:
            logger.warning(f"月度行业扫描失败（非致命）: {e}")

        logger.info("月度基本面验证（成分股财报）...")
        try:
            fundamental = check_all_holdings()
            fundamental_prompt = format_fundamental_prompt(fundamental)
            # 追加到 logic_check 后面
            if logic_check:
                logic_check = logic_check + "\n" + fundamental_prompt
            else:
                logic_check = fundamental_prompt
            logger.info(f"基本面验证完成: {fundamental.get('verdicts', [])}")
        except Exception as e:
            logger.warning(f"基本面验证失败（非致命）: {e}")

    # ── Step 2.6: 全球轮动数据（每周五刷新） ──
    logger.info("Step 2.6/4: 全球轮动数据...")
    global_rotation = None
    try:
        # 从已有数据提取沪深300 PE和中国10Y国债（避免重复请求）
        from src.analyze import _get_season as get_a_season
        season_data = get_a_season()
        csi_pe = season_data.get("pe")
        # 中国10Y从已缓存的global_indicators取
        cn_10y = None
        global_ind = data.get("global_indicators", {})
        yield_spread = global_ind.get("yield_spread", {})
        if yield_spread:
            cn_10y = yield_spread.get("cn_10y")
        global_rotation = fetch_global_rotation_data(csi_pe=csi_pe, cn_10y=cn_10y)
        logger.info("全球轮动数据获取完成")
    except Exception as e:
        logger.warning(f"全球轮动数据获取失败（非致命）: {e}")

    # ── Step 3: AI 分析 ──
    logger.info("Step 3/4: DeepSeek 生成投资建议...")
    result = analyze(data, scanner_data=scanner_data, industry_signals=industry_signals,
                     logic_check=logic_check, global_rotation=global_rotation)
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
