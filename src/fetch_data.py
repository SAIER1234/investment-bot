"""
基金数据抓取模块（场外基金only）
使用 akshare 获取基金净值、指数估值、市场情绪、技术指标。
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from src.common import (
    ROOT_DIR, CONFIG_DIR, DATA_DIR,
    disable_proxy, ensure_data_dir, load_json, save_json,
)

disable_proxy()

import akshare as ak
import pandas as pd
import requests

logger = logging.getLogger(__name__)


def load_portfolio() -> dict[str, Any]:
    return load_json(os.path.join(CONFIG_DIR, "portfolio.json"))


# ═══════════════════════════════════════════════════════════════
# 场外基金净值
# ═══════════════════════════════════════════════════════════════

def fetch_otc_fund_nav(symbol: str) -> dict[str, Any] | None:
    """
    获取场外基金最新净值和近期历史（用于计算表现和技术指标）。
    返回 { code, date, nav, daily_change, history: [{date, nav, daily_change}] }
    """
    try:
        df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
        if df is None or df.empty:
            logger.warning(f"场外基金 {symbol} 无数据")
            return None

        df = df.sort_values("净值日期") if "净值日期" in df.columns else df
        latest = df.iloc[-1]

        # 近期历史（最近120个交易日，足够计算季线+技术指标）
        recent = df.iloc[-120:] if len(df) > 120 else df
        history = []
        for _, row in recent.iterrows():
            history.append({
                "date": str(row.get("净值日期", "")),
                "nav": _safe_float(row.get("单位净值")),
                "daily_change": _safe_float(row.get("日增长率", row.get("equityReturn", 0))),
            })

        return {
            "code": symbol,
            "date": str(latest.get("净值日期", "")),
            "nav": _safe_float(latest.get("单位净值")),
            "daily_change": _safe_float(
                latest.get("日增长率", latest.get("equityReturn", 0))
            ),
            "history": history,
        }
    except Exception as e:
        logger.error(f"场外基金 {symbol} 数据抓取失败: {e}")
        return None


def fetch_otc_fund_performance(history: list[dict[str, Any]]) -> dict[str, float | None]:
    """
    基于日增长率计算多周期表现（复合，天然处理拆分复权）。
    输入 history 列表每项含 daily_change，返回 {w1, m1, m3, ytd}。
    """
    if not history:
        return {"w1": None, "m1": None, "m3": None, "ytd": None}

    def _compound(days: int) -> float | None:
        chunk = history[-days:] if len(history) >= days else history
        cumulative = 1.0
        valid = 0
        for item in chunk:
            chg = item.get("daily_change")
            if chg is not None and not (isinstance(chg, float) and pd.isna(chg)):
                cumulative *= (1 + float(chg) / 100)
                valid += 1
        return round((cumulative - 1) * 100, 2) if valid > 0 else None

    return {
        "w1": _compound(5),
        "m1": _compound(22),
        "m3": _compound(66),
        "ytd": _compound(140),
    }


def calc_period_return(df: pd.DataFrame, col: str = "单位净值", period_days: int = 7,
                       daily_change_col: str = "日增长率") -> float | None:
    """
    区间收益率（保留兼容旧接口）。
    优先使用日增长率复合，回退到净值直接比较。
    """
    if df is None or df.empty or len(df) < 2:
        return None
    try:
        if daily_change_col in df.columns:
            recent = df.iloc[-period_days:]
            cumulative = 1.0
            valid_days = 0
            for _, row in recent.iterrows():
                chg = row[daily_change_col]
                if chg is not None and not pd.isna(float(chg)):
                    cumulative *= (1 + float(chg) / 100)
                    valid_days += 1
            if valid_days > 0:
                return round((cumulative - 1) * 100, 2)
        latest = float(df[col].iloc[-1])
        past_idx = max(0, len(df) - period_days - 1)
        past = float(df[col].iloc[past_idx])
        if past == 0 or pd.isna(past):
            return None
        return round((latest - past) / past * 100, 2)
    except (ValueError, IndexError, KeyError):
        return None


# ═══════════════════════════════════════════════════════════════
# 指数估值（PE / PB / 分位）
# ═══════════════════════════════════════════════════════════════

# 基金代码 → CSI指数代码（用于 stock_zh_index_value_csindex 和 stock_zh_index_hist_csindex）
# 以及 legulegu 风格名称（用于 stock_index_pe_lg / stock_index_pb_lg）
FUND_INDEX_MAP: dict[str, dict[str, str]] = {
    "019633": {"csi": "931743", "name": "半导体材料设备", "legu": None},
    "017811": {"csi": "931743", "name": "半导体材料设备", "legu": None},  # 主动基金，持仓与019633高度重合
    "003579": {"csi": "000300", "name": "沪深300", "legu": "沪深300"},
    "011613": {"csi": "000688", "name": "科创50", "legu": None},
    "025766": {"csi": None, "name": "港股通互联网", "legu": None,
               "note": "港股指数，akshare无可靠PE分位数据源。勿编造分位。"},
    "018927": {"csi": "931719", "name": "电池", "legu": None},
}


def fetch_index_valuation(fund_code: str) -> dict[str, Any] | None:
    """
    获取基金跟踪指数的PE/PB估值。
    策略：
    1. 如果是沪深300等宽基 → 用 stock_index_pe_lg / stock_index_pb_lg（含分位数据）
    2. 如果有CSI代码 → 用 stock_zh_index_hist_csindex 取滚动PE + 手动算分位
    3. 都没有 → 返回 None
    返回 {index_name, pe, pe_percentile, pb, pb_percentile, update_time}
    """
    if fund_code not in FUND_INDEX_MAP:
        return None

    info = FUND_INDEX_MAP[fund_code]
    index_name = info["name"]

    # ── 路径1: 宽基走 legulegu ──
    if info.get("legu"):
        try:
            df_pe = ak.stock_index_pe_lg(symbol=info["legu"])
            df_pb = ak.stock_index_pb_lg(symbol=info["legu"])
            if df_pe is not None and not df_pe.empty and df_pb is not None and not df_pb.empty:
                latest_pe = df_pe.iloc[-1]
                latest_pb = df_pb.iloc[-1]
                # PE: col[3]=动态市盈率, 手动计算分位（legulegu内置分位不可靠）
                pe_val = _safe_float(latest_pe.iloc[3]) if len(latest_pe) > 3 else None
                pe_series = df_pe.iloc[:, 3].dropna()
                pe_pct = round((pe_series < pe_val).sum() / len(pe_series) * 100, 1) if pe_val is not None and len(pe_series) > 0 else None
                # PB: col[2]=市净率
                pb_val = _safe_float(latest_pb.iloc[2]) if len(latest_pb) > 2 else None
                pb_series = df_pb.iloc[:, 2].dropna()
                pb_pct = round((pb_series < pb_val).sum() / len(pb_series) * 100, 1) if pb_val is not None and len(pb_series) > 0 else None
                return {
                    "index_name": index_name,
                    "pe": pe_val,
                    "pe_percentile": pe_pct,
                    "pb": pb_val,
                    "pb_percentile": pb_pct,
                    "update_time": str(latest_pe.iloc[0]),
                    "source": "legulegu (manual pct)",
                }
        except Exception as e:
            logger.warning(f"legulegu PE/PB 获取失败 [{index_name}]: {e}")

    # ── 路径2: CSI 指数走 csindex（滚动PE，无直接分位） ──
    if info.get("csi"):
        try:
            df = ak.stock_zh_index_hist_csindex(
                symbol=info["csi"], start_date="20190101", end_date="20300101"
            )
            if df is not None and not df.empty and "滚动市盈率" in df.columns:
                df = df.dropna(subset=["滚动市盈率"])
                if not df.empty:
                    latest = df.iloc[-1]
                    current_pe = _safe_float(latest.get("滚动市盈率"))
                    # 手动计算历史分位
                    pe_series = df["滚动市盈率"].dropna()
                    pe_pct = round(
                        (pe_series < current_pe).sum() / len(pe_series) * 100, 1
                    ) if current_pe is not None and len(pe_series) > 0 else None
                    return {
                        "index_name": index_name,
                        "pe": current_pe,
                        "pe_percentile": pe_pct,
                        "pb": None,
                        "pb_percentile": None,
                        "update_time": str(latest.get("日期", "")),
                        "source": "csindex",
                    }
        except Exception as e:
            logger.warning(f"csindex PE 获取失败 [{index_name} {info['csi']}]: {e}")

    logger.warning(f"无法获取估值: {index_name} ({fund_code})")
    return None


# ═══════════════════════════════════════════════════════════════
# 市场情绪
# ═══════════════════════════════════════════════════════════════

def fetch_market_turnover() -> dict[str, Any] | None:
    """获取沪深两市总成交额（亿元）"""
    try:
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return None
        total = df["成交额"].sum() / 1e8  # 转亿元
        return {
            "total_turnover_yi": round(total, 0),
            "stock_count": len(df),
        }
    except Exception as e:
        logger.error(f"两市成交额获取失败: {e}")
        return None


def fetch_northbound_flow() -> dict[str, Any] | None:
    """获取北向资金最近净买卖"""
    try:
        # 使用 stock_hsgt_hist_em 获取北向资金历史
        df = ak.stock_hsgt_hist_em(symbol="北向资金")
        if df is None or df.empty:
            return {"warning": "北向资金数据不可用"}
        # 过滤掉2024-08后的空数据行
        df = df.dropna(subset=["当日成交净买额"])
        if df.empty:
            return {"warning": "北向资金数据不可用（2024-08后交易所不再披露逐笔数据）"}
        latest = df.iloc[-1]
        net_buy_yi = _safe_float(latest.get("当日成交净买额"))  # 亿
        return {
            "date": str(latest.get("日期", "")),
            "net_flow_yi": net_buy_yi,
            "data_note": "2024年8月后交易所不再披露逐笔买卖明细，仅汇总净额",
        }
    except Exception as e:
        logger.error(f"北向资金获取失败: {e}")
        return None


def fetch_sector_fund_flow(sector_name: str = "半导体") -> dict[str, Any] | None:
    """获取指定板块今日资金流向"""
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
        match = df[df["名称"].str.contains(sector_name, case=False, na=False)]
        if match.empty:
            return None
        row = match.iloc[0]
        return {
            "sector": str(row["名称"]),
            "change_pct": _safe_float(row.get("今日涨跌幅")),
            "main_net_inflow_yi": round(_safe_float(row.get("主力净流入-净额", 0)) / 1e8, 2),
            "main_net_ratio": _safe_float(row.get("主力净流入-净占比")),
            "super_large_net_yi": round(_safe_float(row.get("超大单净流入-净额", 0)) / 1e8, 2),
            "large_net_yi": round(_safe_float(row.get("大单净流入-净额", 0)) / 1e8, 2),
        }
    except Exception as e:
        logger.error(f"板块资金流向获取失败 [{sector_name}]: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# 大盘指数
# ═══════════════════════════════════════════════════════════════

def fetch_market_overview() -> dict[str, dict[str, Any]]:
    """获取主要指数涨跌"""
    try:
        df = ak.stock_zh_index_spot_em()
        targets = ["上证指数", "深证成指", "创业板指", "科创50"]
        overview: dict[str, dict[str, Any]] = {}
        for _, row in df.iterrows():
            name = str(row.get("名称", ""))
            if name in targets:
                overview[name] = {
                    "price": _safe_float(row.get("最新价")),
                    "change_pct": _safe_float(row.get("涨跌幅")),
                    "volume": _safe_float(row.get("成交量")),
                    "amount": _safe_float(row.get("成交额")),
                }
        return overview
    except Exception as e:
        logger.error(f"大盘数据获取失败: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════
# 技术指标
# ═══════════════════════════════════════════════════════════════

def calc_technical_indicators(history: list[dict[str, Any]]) -> dict[str, Any]:
    """
    从净值历史序列计算技术指标。
    输入: [{date, nav, daily_change}, ...]
    返回: {ma20, ma60, price_vs_ma20, price_vs_ma60, rsi14, volume_note}
    """
    if not history or len(history) < 60:
        return {"error": "数据不足，需要至少60个交易日"}

    navs = [h["nav"] for h in history if h.get("nav") is not None]
    if len(navs) < 60:
        return {"error": f"有效净值数据不足 ({len(navs)}条)"}

    latest_nav = navs[-1]

    # 均线
    ma20 = round(sum(navs[-20:]) / 20, 4) if len(navs) >= 20 else None
    ma60 = round(sum(navs[-60:]) / 60, 4)
    vs_ma20 = round((latest_nav - ma20) / ma20 * 100, 2) if ma20 else None
    vs_ma60 = round((latest_nav - ma60) / ma60 * 100, 2)

    # RSI(14) — 基于日增长率
    changes = []
    for h in history[-15:]:  # 需要15个数据点计算14个变化
        chg = h.get("daily_change")
        if chg is not None:
            changes.append(float(chg))
    if len(changes) >= 14:
        gains = [c for c in changes[-14:] if c > 0]
        losses = [abs(c) for c in changes[-14:] if c < 0]
        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 0.0001
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = round(100 - (100 / (1 + rs)), 1)
    else:
        rsi = None

    return {
        "latest_nav": latest_nav,
        "ma20": ma20,
        "ma60": ma60,
        "price_vs_ma20_pct": vs_ma20,
        "price_vs_ma60_pct": vs_ma60,
        "rsi14": rsi,
        "data_points": len(navs),
    }


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def fetch_all() -> dict[str, Any]:
    """
    主入口：抓取全部所需数据，返回结构化 dict。
    全流程场外基金驱动。
    """
    ensure_data_dir()
    portfolio = load_portfolio()

    # 所有持仓都是场外基金
    all_codes = [str(h["code"]) for h in portfolio.get("holdings", [])]

    # ── 1. 场外基金净值 + 表现 + 技术面 ──
    otc_data: dict[str, Any] = {}
    otc_performance: dict[str, Any] = {}
    otc_technical: dict[str, Any] = {}

    for code in all_codes:
        nav = fetch_otc_fund_nav(code)
        otc_data[code] = nav
        if nav and nav.get("history"):
            otc_performance[code] = fetch_otc_fund_performance(nav["history"])
            otc_technical[code] = calc_technical_indicators(nav["history"])
        else:
            otc_performance[code] = {"w1": None, "m1": None, "m3": None, "ytd": None}
            otc_technical[code] = {"error": "无历史数据"}

    # ── 2. 指数估值 ──
    index_valuations: dict[str, Any] = {}
    for code in all_codes:
        val = fetch_index_valuation(code)
        if val:
            index_valuations[code] = val

    # ── 3. 市场情绪 ──
    market_turnover = fetch_market_turnover()
    northbound = fetch_northbound_flow()
    semiconductor_flow = fetch_sector_fund_flow("半导体")

    # ── 4. 大盘概况 ──
    market_overview = fetch_market_overview()

    return {
        "timestamp": datetime.now().isoformat(),
        "portfolio": portfolio,
        "otc_data": otc_data,
        "otc_performance": otc_performance,
        "otc_technical": otc_technical,
        "index_valuations": index_valuations,
        "market_turnover": market_turnover,
        "northbound_flow": northbound,
        "semiconductor_flow": semiconductor_flow,
        "market_overview": market_overview,
    }


# ═══════════════════════════════════════════════════════════════
# 缓存
# ═══════════════════════════════════════════════════════════════

def save_cache(data: dict[str, Any], filename: str = "latest_data.json") -> None:
    save_json(os.path.join(DATA_DIR, filename), data)


def load_cache(filename: str = "latest_data.json") -> dict[str, Any] | None:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        return load_json(path)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════════════

def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else round(f, 4)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_all()
    save_cache(data)
    # 只打印摘要，不打印全量数据（太大）
    print(f"Timestamp: {data['timestamp']}")
    print(f"OTC funds: {list(data['otc_data'].keys())}")
    for code, nav in data["otc_data"].items():
        if nav:
            print(f"  {code}: NAV={nav.get('nav')}, date={nav.get('date')}, hist={len(nav.get('history',[]))}点")
    print(f"Index valuations: {list(data['index_valuations'].keys())}")
    print(f"Market turnover: {data['market_turnover']}")
    print(f"Semiconductor flow: {data['semiconductor_flow']}")
    print("Done.")
