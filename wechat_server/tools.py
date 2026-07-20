"""
工具函数 — 为AI对话提供实时基金数据上下文
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("tools")

FUND_CODES = ["159516", "003579", "011613", "025766", "018927"]
FUND_NAMES = {
    "159516": "半导体设备ETF国泰",
    "003579": "沪深300",
    "011613": "科创50",
    "025766": "港股通互联网",
    "018927": "电池",
}


def get_fund_context() -> str:
    """获取当前基金数据的文本摘要，注入 AI 上下文"""
    try:
        from src.fetch_data import (
            fetch_etf_spot,
            fetch_otc_fund_nav,
            calc_period_return,
            fetch_etf_hist,
        )

        lines = []
        today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")

        # ETF
        etf_codes = ["159516"]
        etf = fetch_etf_spot(etf_codes)
        for code, info in etf.items():
            lines.append(
                f"{code} {info['name']}: 价格{info['price']} "
                f"涨跌{info.get('change_pct',0):+.2f}%"
            )
            # 近期表现
            hist = fetch_etf_hist(code)
            if not hist.empty:
                nav_col = "单位净值" if "单位净值" in hist.columns else "收盘"
                w1 = calc_period_return(hist, col=nav_col, period_days=5)
                m1 = calc_period_return(hist, col=nav_col, period_days=22)
                lines.append(f"  近一周{w1}% 近一月{m1}%")

        # OTC
        for code in ["003579", "011613", "025766", "018927"]:
            nav = fetch_otc_fund_nav(code)
            if nav:
                stale = " ⚠️非今日" if str(nav.get("date","")) != today else ""
                lines.append(
                    f"{code} {FUND_NAMES.get(code,'')}: "
                    f"净值{nav['nav']} ({nav.get('date','')}){stale} "
                    f"变动{nav.get('daily_change',0):+.2f}%"
                )

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"获取基金上下文失败: {e}")
        return "基金数据暂时不可用"


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print(get_fund_context())
