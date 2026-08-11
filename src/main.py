"""
投资顾问机器人 — 主入口
每天21:00运行：抓取数据 → (周五)全网扫描 → AI分析 → 推送到微信
"""

import logging
import os
import sys

from src.common import DATA_DIR, disable_proxy, ensure_data_dir, load_json, save_json

disable_proxy()

from dotenv import load_dotenv

load_dotenv()

from src.fetch_data import fetch_all, save_cache
from src.analyze import analyze
from src.push_wechat import push_investment_report, push_error_notification
from src.fund_scanner import scan_if_needed
from src.sector_spring_scanner import scan_if_needed as spring_scan
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

    # ── Step 1.5: 沪深300 PE（一次抓取，analyze和global_rotation共用） ──
    try:
        from src.analyze import _get_season as get_a_season
        data["csi_season"] = get_a_season()
        logger.info(f"沪深300 PE: {data['csi_season']['pe']} 分位={data['csi_season']['pe_pct']}%")
    except Exception as e:
        logger.warning(f"沪深300 PE抓取失败（非致命）: {e}")
        data["csi_season"] = {'season': '?', 'pe': None, 'pe_pct': None, 'guidance': '?', 'date': None}

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

    # ── Step 2.1: 全市场春扫（每周五） ──
    logger.info("Step 2.1/4: 全市场春扫...")
    spring_scan_data = None
    try:
        spring_scan_data = spring_scan()
        if spring_scan_data:
            logger.info(f"春扫完成: {spring_scan_data.get('spring_count',0)}个春行业")
    except Exception as e:
        logger.warning(f"春扫失败（非致命）: {e}")

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

    # 月度行业扫描（仅每月第一天）
    if date.today().day == 1:
        logger.info("月度行业信号扫描...")
        try:
            signals = monthly_scan()
            industry_signals = format_industry_prompt(signals)
            logger.info("月度行业扫描完成")
        except Exception as e:
            logger.warning(f"月度行业扫描失败（非致命）: {e}")

    # 基本面验证（每月1日刷新，或缓存超过30天刷新，或首次运行）
    fundamental_cache = os.path.join(DATA_DIR, "fundamental_check_cache.json")
    fundamental_prompt = ""
    need_fundamental = False
    if date.today().day == 1:
        need_fundamental = True
        logger.info("每月1日，刷新基本面验证...")
    elif not os.path.exists(fundamental_cache):
        need_fundamental = True
        logger.info("首次运行，执行基本面验证...")
    else:
        try:
            cache = load_json(fundamental_cache)
            last_check = cache.get("check_date", "")[:10]
            if last_check:
                days_since = (date.today() - date.fromisoformat(last_check)).days
                if days_since > 30:
                    need_fundamental = True
                    logger.info(f"基本面缓存{days_since}天未刷新，重新验证...")
                else:
                    fundamental_prompt = cache.get("prompt", "")
                    logger.info(f"复用基本面缓存 ({days_since}天前, {last_check})")
        except Exception:
            need_fundamental = True

    if need_fundamental:
        try:
            fundamental = check_all_holdings()
            fundamental_prompt = format_fundamental_prompt(fundamental)
            # 缓存结果
            ensure_data_dir()
            save_json(fundamental_cache, {
                "check_date": date.today().isoformat(),
                "verdicts": fundamental.get("verdicts", []),
                "prompt": fundamental_prompt,
            })
            logger.info(f"基本面验证完成: {fundamental.get('verdicts', [])}")
        except Exception as e:
            logger.warning(f"基本面验证失败（非致命）: {e}")
            # 尝试复用旧缓存
            if os.path.exists(fundamental_cache):
                try:
                    fundamental_prompt = load_json(fundamental_cache).get("prompt", "")
                except Exception:
                    pass

    # 追加基本面验证到逻辑验证
    if fundamental_prompt:
        if logic_check:
            logic_check = logic_check + "\n" + fundamental_prompt
        else:
            logic_check = fundamental_prompt

    # ── Step 2.6: 全球轮动数据（每周五刷新） ──
    logger.info("Step 2.6/4: 全球轮动数据...")
    global_rotation = None
    try:
        csi_season = data.get("csi_season", {})
        csi_pe = csi_season.get("pe")
        cn_10y = None
        global_ind = data.get("global_indicators", {})
        yield_spread = global_ind.get("yield_spread", {})
        if yield_spread:
            cn_10y = yield_spread.get("cn_10y")
        a_pct_val = csi_season.get("pe_pct")
        global_rotation = fetch_global_rotation_data(csi_pe=csi_pe, cn_10y=cn_10y, a_pct=a_pct_val)
        logger.info("全球轮动数据获取完成")
    except Exception as e:
        logger.warning(f"全球轮动数据获取失败（非致命）: {e}")

    # ── Step 3: AI 分析 ──
    logger.info("Step 3/4: DeepSeek 生成投资建议...")
    result = analyze(data, scanner_data=scanner_data, industry_signals=industry_signals,
                     logic_check=logic_check, global_rotation=global_rotation,
                     spring_scan=spring_scan_data)
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
