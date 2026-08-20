"""
产业链景气跟踪 — 第二问(行业在扩张吗)的量化证据
抓取关键商品价格趋势，在利润财报披露前提供行业景气变化的早期信号。

覆盖:
  - 碳酸锂期货(LC0) → 电池行业景气 (018927)
  - 沪铜期货(CU0)   → 有色行业景气 (004433)

原理: 商品价格是行业利润的先行指标。锂价跌→电池材料商利润
在财报披露前1-2个季度就开始变坏。价格趋势能提前预警。
频率: 每天运行(数据日频), 缓存1天。
"""
import logging
import os
from datetime import date
from typing import Any

import pandas as pd

from src.common import DATA_DIR, disable_proxy, ensure_data_dir, load_json, save_json

disable_proxy()

import akshare as ak

logger = logging.getLogger(__name__)

CACHE_FILE = "industry_chain_cache.json"

# 商品 → (akshare symbol, 关联持仓代码, 关联指数)
CHAIN_ITEMS = {
    'LC0': {'name': '碳酸锂', 'holding': '018927', 'index': '931719', 'note': '电池上游材料价格'},
    'CU0': {'name': '沪铜', 'holding': '004433', 'index': '930708', 'note': '有色金属核心品种价格'},
}


def _price_trend(symbol: str) -> dict[str, Any] | None:
    """抓取期货日线，计算最新价+30日/90日/180日涨跌"""
    try:
        df = ak.futures_main_sina(symbol=symbol)
        if df is None or df.empty or len(df) < 30:
            return None
        close = pd.to_numeric(df['收盘价'], errors='coerce').dropna()
        if len(close) < 30:
            return None
        latest = float(close.iloc[-1])
        latest_date = str(df['日期'].iloc[-1])[:10]

        def chg(n: int):
            if len(close) < n:
                return None
            return round((latest / float(close.iloc[-n]) - 1) * 100, 1)

        return {
            'symbol': symbol,
            'latest': latest,
            'date': latest_date,
            'chg_30d': chg(30),
            'chg_90d': chg(90),
            'chg_180d': chg(180),
        }
    except Exception as e:
        logger.warning(f"{symbol} 价格抓取失败: {e}")
        return None


def fetch_chain_prices(force: bool = False) -> dict[str, Any]:
    """主入口。缓存1天。"""
    ensure_data_dir()
    cache_path = os.path.join(DATA_DIR, CACHE_FILE)
    today = date.today().isoformat()

    if not force and os.path.exists(cache_path):
        try:
            cache = load_json(cache_path)
            if cache.get('fetch_date') == today:
                logger.info("复用产业链景气缓存(今日)")
                return cache
        except Exception:
            pass

    result = {'fetch_date': today, 'items': {}}
    for symbol, meta in CHAIN_ITEMS.items():
        trend = _price_trend(symbol)
        if trend:
            trend.update(meta)
            result['items'][symbol] = trend
            logger.info(f"{meta['name']}: {trend['latest']} (30日{trend['chg_30d']:+.1f}%)")
    save_json(cache_path, result)
    return result


def format_chain_prompt(chain: dict[str, Any]) -> str:
    """格式化为给DeepSeek的prompt片段。只给数据不给判断。"""
    items = chain.get('items', {})
    if not items:
        return ""

    lines = ["## 产业链景气跟踪（第二问的量化证据）\n"]
    for symbol, it in items.items():
        lines.append(f"- **{it['name']}**({it['holding']}相关): 现价{it['latest']} "
                     f"| 30日{_fmt(it['chg_30d'])} | 90日{_fmt(it['chg_90d'])} "
                     f"| 180日{_fmt(it['chg_180d'])} | {it['note']}")
    lines.append("")
    lines.append("**规则:** 商品价格趋势是行业利润的先行指标(提前1-2个季度)。")
    lines.append("价格趋势明显走弱(90日<-10%)→在报告中提示'行业景气转弱，下季度利润可能变坏，下个月财报验证时重点看'。")
    lines.append("价格趋势走强(90日>+10%)→提示'行业景气走强，利润有支撑'。")
    lines.append("但商品价格≠利润，最终以每月财报验证为准。不要因价格波动单独触发W信号。")
    return "\n".join(lines)


def _fmt(v) -> str:
    return f"{v:+.1f}%" if v is not None else "暂无"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = fetch_chain_prices(force=True)
    print(format_chain_prompt(r))
