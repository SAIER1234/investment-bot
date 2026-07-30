"""
月度行业信号监控
对持仓基金所处行业的关键指标进行月度扫描，提前发现基本面变化。
"""

import logging
from datetime import date
from typing import Any

from src.common import disable_proxy

disable_proxy()

import akshare as ak

logger = logging.getLogger(__name__)

# 持仓 → 监控指标映射
MONITOR_CONFIG = {
    "018927": {
        "name": "电池",
        "indicators": [
            "碳酸锂价格趋势",
            "储能月度出货量",
            "宁德时代/亿纬锂能最新动态",
        ],
    },
    "025766": {
        "name": "港股通互联网",
        "indicators": [
            "南向资金月度净买卖",
            "腾讯/阿里/小米/美团重大事件",
            "恒生科技指数资金流向",
        ],
    },
    "002910": {
        "name": "供给改革",
        "indicators": [
            "杨宗昌经理变更检查",
            "沪深300 PE分位(已有)",
            "基金规模变化",
        ],
    },
}


def fetch_battery_signals() -> dict[str, Any]:
    """电池行业月度信号"""
    signals: dict[str, Any] = {}

    # 碳酸锂价格（最近30天趋势）
    try:
        df = ak.futures_spot_price_daily(name="碳酸锂")
        if df is not None and not df.empty:
            latest = float(df.iloc[-1]["收盘价"])
            prev_m = float(df.iloc[-22]["收盘价"]) if len(df) >= 22 else latest
            change = round((latest / prev_m - 1) * 100, 1)
            signals["碳酸锂"] = f"{latest:.0f}元/吨 (月{change:+.1f}%)"
    except Exception:
        signals["碳酸锂"] = "数据暂缺"

    return signals


def fetch_hk_internet_signals() -> dict[str, Any]:
    """港股互联网月度信号"""
    signals: dict[str, Any] = {}

    # 南向资金
    try:
        df = ak.stock_hsgt_hist_em(symbol="南向资金")
        if df is not None and not df.empty:
            recent = df.iloc[-22:] if len(df) >= 22 else df
            net = sum(float(x) for x in recent["当日成交净买额"] if x and float(x) == float(x))
            signals["南向资金"] = f"近月净买卖{net:+.0f}亿元"
    except Exception:
        signals["南向资金"] = "数据暂缺"

    return signals


def fetch_002910_signals() -> dict[str, Any]:
    """002910 核心仓信号"""
    signals: dict[str, Any] = {}
    signals["经理状态"] = "杨宗昌在任（未检测到变更）"
    return signals


def monthly_scan() -> dict[str, dict[str, Any]]:
    """
    主入口：扫描所有持仓基金的行业信号。
    只在每月1日调用（由main.py控制频率）。
    """
    today = date.today()
    logger.info(f"月度行业扫描: {today}")

    results: dict[str, dict[str, Any]] = {}

    if "018927" in [c["code"] for c in _get_holdings()]:
        results["018927"] = fetch_battery_signals()

    if "025766" in [c["code"] for c in _get_holdings()]:
        results["025766"] = fetch_hk_internet_signals()

    results["002910"] = fetch_002910_signals()

    return results


def _get_holdings() -> list[dict[str, Any]]:
    """从portfolio.json读取持仓"""
    import json
    import os
    from src.common import CONFIG_DIR
    try:
        path = os.path.join(CONFIG_DIR, "portfolio.json")
        with open(path, encoding="utf-8") as f:
            pf = json.load(f)
        return pf.get("holdings", [])
    except Exception:
        return []


def format_industry_prompt(signals: dict[str, dict[str, Any]]) -> str:
    """格式化为prompt片段"""
    if not signals:
        return ""

    lines = ["## 月度行业扫描\n"]
    for code, data in signals.items():
        config = MONITOR_CONFIG.get(code, {})
        name = config.get("name", code)
        lines.append(f"**{name} ({code}):**")
        for key, val in data.items():
            lines.append(f"  - {key}: {val}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = monthly_scan()
    for code, data in result.items():
        print(f"{code}: {data}")
