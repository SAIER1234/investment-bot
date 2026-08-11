"""
全球轮动数据模块
获取美股PE分位、FED模型、实际利率，判断全球季节，检查S2/S3信号。
每周五刷新，与基金扫描同频。缓存7天。
"""
import json
import logging
import os
from datetime import date, datetime
from typing import Any

from src.common import DATA_DIR, ensure_data_dir, load_json, save_json

logger = logging.getLogger(__name__)

CACHE_FILE = "global_rotation_cache.json"

# ── 季节阈值（与系统提示词保持一致） ──
SEASON_THRESHOLDS = {
    "春": (0, 30),   # PE分位 < 30%
    "夏": (30, 60),  # PE分位 30-60%
    "秋": (60, 80),  # PE分位 60-80%
    "冬": (80, 100), # PE分位 > 80%
}

# S2信号阈值
S2_A_SHARE_MIN = 65   # A股PE分位必须 > 65%
S2_US_MAX = 35        # 美股PE分位必须 < 35%

# S3信号阈值
S3_CSI300_MIN = 80
S3_SP500_MIN = 80
S3_NDX_MIN = 70


def _get_season(pct: float | None) -> str:
    """PE分位 → 季节"""
    if pct is None:
        return "?"
    for season, (lo, hi) in SEASON_THRESHOLDS.items():
        if lo <= pct < hi:
            return season
    return "冬" if pct >= 100 else "?"


def fetch_us_pe(ticker: str) -> dict[str, Any]:
    """
    用 yfinance 获取美股ETF PE和价格历史分位。
    ticker: "SPY" 或 "QQQ"
    返回 {pe, price_pct, price_latest, data_points, season, ok, error}
    """
    result = {"ticker": ticker, "pe": None, "price_pct": None,
              "price_latest": None, "data_points": 0, "season": "?", "ok": False}

    try:
        import yfinance as yf
    except ImportError:
        result["error"] = "yfinance未安装"
        return result

    t = yf.Ticker(ticker)

    # 当前PE
    try:
        info = t.info
        result["pe"] = info.get("trailingPE")
        result["forwardPE"] = info.get("forwardPE")
    except Exception as e:
        logger.warning(f"{ticker} info获取失败: {e}")

    # 10年价格历史 + 分位
    try:
        hist = t.history(period="10y")
        if not hist.empty:
            closes = hist["Close"]
            latest = float(closes.iloc[-1])
            pct = round((closes < latest).sum() / len(closes) * 100, 1)
            result["price_latest"] = round(latest, 2)
            result["price_pct"] = pct
            result["data_points"] = len(hist)
            result["price_history_start"] = str(hist.index[0].date())
            result["price_history_end"] = str(hist.index[-1].date())

            # MA200
            if len(closes) >= 200:
                ma200 = float(closes.iloc[-200:].mean())
                result["ma200"] = round(ma200, 2)
                result["vs_ma200_pct"] = round((latest / ma200 - 1) * 100, 2)
    except Exception as e:
        logger.warning(f"{ticker} 价格历史获取失败: {e}")

    # 用价格分位作为PE分位近似
    if result["price_pct"] is not None:
        result["pe_percentile_est"] = result["price_pct"]  # 价格分位法
        result["season"] = _get_season(result["price_pct"])

    result["ok"] = result["pe"] is not None and result["data_points"] > 0
    return result


def fetch_real_yield() -> dict[str, Any]:
    """
    获取美国实际利率（10Y名义收益率 − 2%通胀目标）。
    返回 {nominal_yield, real_yield_est, ok}
    """
    result = {"nominal_yield": None, "real_yield_est": None, "ok": False}

    try:
        import yfinance as yf
        tnx = yf.Ticker("^TNX")
        info = tnx.info
        nominal = info.get("regularMarketPrice") or info.get("previousClose")
        if nominal:
            result["nominal_yield"] = round(float(nominal), 2)
            result["real_yield_est"] = round(result["nominal_yield"] - 2.0, 2)
            result["ok"] = True
    except Exception as e:
        logger.warning(f"实际利率获取失败: {e}")

    return result


def fetch_fed_model(csi_pe: float | None, cn_10y: float | None) -> dict[str, Any]:
    """
    FED股债性价比模型。
    FED利差 = 1/沪深300PE（盈利收益率） − 中国10Y国债收益率
    返回 {earnings_yield, cn_10y, fed_spread, signal}
    """
    result = {"earnings_yield": None, "cn_10y": cn_10y, "fed_spread": None, "signal": "?"}

    if csi_pe and csi_pe > 0:
        result["earnings_yield"] = round(1 / csi_pe * 100, 2)

    if result["earnings_yield"] is not None and cn_10y is not None:
        result["fed_spread"] = round(result["earnings_yield"] - cn_10y, 2)
        # FED模型信号
        if result["fed_spread"] > 2:
            result["signal"] = "股票明显便宜"
        elif result["fed_spread"] > 0:
            result["signal"] = "股票略优"
        elif result["fed_spread"] > -1:
            result["signal"] = "中性"
        else:
            result["signal"] = "债券更有吸引力"

    return result


def check_s2_signal(a_pct: float | None, spy_pct: float | None, qqq_pct: float | None) -> dict[str, Any] | None:
    """
    S2: A股PE分位 > 65% AND (标普500 < 35% OR 纳指100 < 35%)
    两端极端同时出现才触发。返回 None 表示未触发。
    """
    if a_pct is None:
        return None

    if a_pct <= S2_A_SHARE_MIN:
        return None

    us_cheap = []
    if spy_pct is not None and spy_pct < S2_US_MAX:
        us_cheap.append(f"标普500({spy_pct}%)")
    if qqq_pct is not None and qqq_pct < S2_US_MAX:
        us_cheap.append(f"纳指100({qqq_pct}%)")

    if not us_cheap:
        return None

    return {
        "signal": "S2",
        "title": "跨市场轮动窗口打开",
        "a_share_pct": a_pct,
        "cheap_markets": us_cheap,
        "action": f"A股PE分位{a_pct}%→减A股仓位，转入{'/'.join(us_cheap)}市场QDII基金",
        "severity": "🚨 S级",
    }


def check_s3_signal(a_pct: float | None, spy_pct: float | None, qqq_pct: float | None) -> dict[str, Any] | None:
    """
    S3: 沪深300 > 80% AND 标普500 > 80% AND 纳指100 > 70%
    全球全贵。返回 None 表示未触发。
    """
    if a_pct is None or spy_pct is None or qqq_pct is None:
        return None
    if a_pct > S3_CSI300_MIN and spy_pct > S3_SP500_MIN and qqq_pct > S3_NDX_MIN:
        return {
            "signal": "S3",
            "title": "全球全贵 — 无处可去",
            "a_share_pct": a_pct,
            "sp500_pct": spy_pct,
            "ndx100_pct": qqq_pct,
            "action": "机会仓全部清仓，转防御（比较实际利率方向：黄金vs债券vs现金）",
            "severity": "⚠️ S级",
        }
    return None


def get_global_seasons(a_pct: float | None, spy_pct: float | None, qqq_pct: float | None) -> dict[str, Any]:
    """所有市场季节汇总"""
    return {
        "a_share": {"pct": a_pct, "season": _get_season(a_pct)},
        "sp500": {"pct": spy_pct, "season": _get_season(spy_pct)},
        "nasdaq100": {"pct": qqq_pct, "season": _get_season(qqq_pct)},
    }


def is_friday() -> bool:
    """今天是不是周五"""
    return date.today().weekday() == 4


def fetch_global_rotation_data(csi_pe: float | None = None,
                                cn_10y: float | None = None,
                                a_pct: float | None = None,
                                force: bool = False) -> dict[str, Any]:
    """
    主入口：获取全球轮动数据。
    缓存7天，周五自动刷新。force=True强制刷新。

    参数:
        csi_pe: 沪深300 PE（来自已有数据，避免重复请求）
        cn_10y: 中国10Y国债收益率（来自已有数据）
    """
    ensure_data_dir()
    cache_path = os.path.join(DATA_DIR, CACHE_FILE)

    today = date.today()

    # 检查缓存
    if not force and os.path.exists(cache_path):
        try:
            cache = load_json(cache_path)
            cache_date = cache.get("fetch_date", "")[:10]
            if cache_date:
                last_fetch = date.fromisoformat(cache_date)
                days_since = (today - last_fetch).days
                # 非周五 + 7天内 → 复用
                if not is_friday() and days_since < 7:
                    logger.info(f"复用全球轮动缓存 ({days_since}天前, {cache_date})")
                    return cache
                # 周五 → 刷新
                if is_friday():
                    logger.info("周五，刷新全球轮动数据")
        except Exception:
            pass

    # ── 抓取新数据 ──
    logger.info("抓取全球轮动数据...")

    # 美股PE（yfinance — GitHub Actions美国IP可用，中国本地会限流）
    spy_data = fetch_us_pe("SPY")
    qqq_data = fetch_us_pe("QQQ")

    # 实际利率
    real_yield = fetch_real_yield()

    # FED模型
    fed = fetch_fed_model(csi_pe, cn_10y)

    # 季节 (a_pct由调用方main.py传入)
    spy_pct = spy_data.get("price_pct")  # 价格分位 ≈ PE分位
    qqq_pct = qqq_data.get("price_pct")

    seasons = get_global_seasons(a_pct, spy_pct, qqq_pct)
    s2 = check_s2_signal(a_pct, spy_pct, qqq_pct)
    s3 = check_s3_signal(a_pct, spy_pct, qqq_pct)

    result = {
        "fetch_date": today.isoformat(),
        "sp500": spy_data,
        "nasdaq100": qqq_data,
        "real_yield": real_yield,
        "fed": fed,
        "seasons": seasons,
        "s2_triggered": s2 is not None,
        "s2_data": s2,
        "s3_triggered": s3 is not None,
        "s3_data": s3,
    }

    # 保存缓存
    save_json(cache_path, result)
    logger.info(f"全球轮动数据已缓存: SPY PE={spy_data.get('pe')}, "
                f"价格分位={spy_pct}%, QQQ PE={qqq_data.get('pe')}, "
                f"价格分位={qqq_pct}%")

    return result


def format_global_dashboard(gr: dict[str, Any]) -> str:
    """
    将全球轮动数据格式化为给DeepSeek的prompt片段。
    """
    if not gr:
        return "全球轮动数据暂缺\n"

    seasons = gr.get("seasons", {})
    fed = gr.get("fed", {})
    sp500 = gr.get("sp500", {})
    ndx = gr.get("nasdaq100", {})
    ry = gr.get("real_yield", {})

    lines = []

    # ── 全球四季仪表盘 ──
    lines.append("## 全球四季仪表盘\n")

    def _season_line(label: str, data: dict) -> str:
        pct = data.get("pct")
        season = data.get("season", "?")
        if pct is not None:
            return f"- {label}: PE分位≈{pct}% | 季节={season}"
        return f"- {label}: 数据暂缺"

    lines.append(_season_line("A股(沪深300)", seasons.get("a_share", {})))
    lines.append(_season_line("美股(标普500)", seasons.get("sp500", {})))
    lines.append(_season_line("科技(纳指100)", seasons.get("nasdaq100", {})))

    # PE数据细节
    if sp500.get("pe"):
        lines.append(f"  - 标普500当前PE={sp500['pe']}倍（价格分位法估算分位，非精确PE分位）")
    if ndx.get("pe"):
        lines.append(f"  - 纳指100当前PE={ndx['pe']}倍（价格分位法估算分位，非精确PE分位）")

    # FED模型
    fed_spread = fed.get("fed_spread")
    if fed_spread is not None:
        lines.append(f"\n**FED股债性价比:** 利差={fed_spread:+.2f}% (盈利收益率{fed.get('earnings_yield')}% − 国债{fed.get('cn_10y')}%)")
        lines.append(f"  → {fed.get('signal', '?')}")

    # 实际利率
    if ry.get("real_yield_est") is not None:
        lines.append(f"\n**美国实际利率:** ≈{ry['real_yield_est']:+.2f}% (名义{ry['nominal_yield']}% − 2%通胀目标)")

    # ── S2/S3信号状态 ──
    lines.append("")
    if gr.get("s3_triggered"):
        s3 = gr["s3_data"]
        lines.append(f"### ⚠️ S3信号触发: {s3['title']}")
        lines.append(f"> 沪深300={s3['a_share_pct']}% | 标普500={s3['sp500_pct']}% | 纳指100={s3['ndx100_pct']}%")
        lines.append(f"> {s3['action']}")
        if ry.get("real_yield_est") is not None:
            direction = "黄金优于债券" if ry["real_yield_est"] < 1.0 else ("债券/现金优于黄金" if ry["real_yield_est"] > 2.0 else "黄金和债券各有优劣")
            lines.append(f"> 实际利率{ry['real_yield_est']:+.2f}% → {direction}")
    elif gr.get("s2_triggered"):
        s2 = gr["s2_data"]
        lines.append(f"### 🚨 S2信号触发: {s2['title']}")
        lines.append(f"> A股PE分位={s2['a_share_pct']}% | 便宜市场: {', '.join(s2['cheap_markets'])}")
        lines.append(f"> {s2['action']}")
    else:
        lines.append("**S2/S3信号:** 均未触发。全球无明显跨市场轮动机会。")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    logging.basicConfig(level=logging.INFO)

    # 获取A股数据先
    from src.analyze import _get_season as get_a_season
    a = get_a_season()
    print(f"A股: PE={a['pe']}, 分位={a['pe_pct']}%, 季节={a['season']}")

    # 获取全球数据
    from src.common import disable_proxy
    disable_proxy()
    import akshare as ak

    # 获取中国10Y国债
    try:
        df = ak.bond_zh_us_rate()
        cn_10y = float(df.iloc[-1]["中国国债收益率10年"])
    except Exception:
        cn_10y = None

    gr = fetch_global_rotation_data(csi_pe=a["pe"], cn_10y=cn_10y, force=True)
    print(format_global_dashboard(gr))
