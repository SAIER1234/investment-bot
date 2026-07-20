"""
基金数据抓取模块
使用 akshare / 东方财富开放API 获取基金净值、ETF行情、板块数据
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

# ── 禁用代理（Windows系统代理 + 环境变量） ───────────────
# akshare 底层走 requests → urllib → Windows 注册表代理。
# 东方财富等国内数据源直连更快，经过代理（如 Clash 7897）反而超时。
for _key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
             "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
    os.environ.pop(_key, None)
os.environ["no_proxy"] = "*"

# 阻止 urllib 读取 Windows 系统代理设置（注册表）
try:
    import urllib.request
    urllib.request.getproxies = lambda: {}
except Exception:
    pass

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
CONFIG_DIR = os.path.join(ROOT_DIR, "config")


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def load_portfolio() -> dict[str, Any]:
    """加载持仓配置文件"""
    path = os.path.join(CONFIG_DIR, "portfolio.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── ETF 行情 ────────────────────────────────────────────

def fetch_etf_spot(codes: list[str]) -> dict[str, dict[str, Any]]:
    """
    获取 ETF 实时行情（收盘后为当日收盘数据）。
    返回 { code: { name, price, change_pct, volume, amount, discount_pct } }
    """
    try:
        df: pd.DataFrame = ak.fund_etf_spot_em()
        df = df[df["代码"].isin(codes)]
        result: dict[str, dict[str, Any]] = {}
        for _, row in df.iterrows():
            code = str(row["代码"])
            result[code] = {
                "name": str(row.get("名称", "")),
                "price": _safe_float(row.get("最新价")),
                "change_pct": _safe_float(row.get("涨跌幅")),
                "volume": _safe_float(row.get("成交量")),
                "amount": _safe_float(row.get("成交额")),
                "discount_pct": _safe_float(row.get("折价率", 0)),
                "nav": _safe_float(row.get("IOPV", row.get("单位净值"))),
            }
        return result
    except Exception as e:
        logger.error(f"ETF 行情抓取失败: {e}")
        return {}


def fetch_etf_hist(symbol: str, days: int | None = None) -> pd.DataFrame:
    """
    获取 ETF 历史净值（单位净值，已复权），用于计算近期涨跌幅。
    使用 fund_open_fund_info_em 获取拆分调整后的净值，避免拆分导致的计算偏差。
    days=None 表示获取全部可用历史数据。
    返回 DataFrame，包含 净值日期 / 单位净值 / 日增长率 等列。
    """
    try:
        df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
        if df is not None and not df.empty:
            df = df.sort_values("净值日期")
            if days is not None:
                cutoff = datetime.now().date() - timedelta(days=days + 5)
                df = df[df["净值日期"] >= cutoff]
            return df
        return pd.DataFrame()
    except Exception as e:
        # 回退：如果上面接口不支持这个ETF，尝试用 fund_etf_hist_em
        logger.warning(f"ETF {symbol} NAV 接口失败，回退到行情价格: {e}")
        try:
            start = (datetime.now() - timedelta(days=days + 5)).strftime("%Y%m%d") if days else "20200101"
            end = datetime.now().strftime("%Y%m%d")
            df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start, end_date=end)
            if df is not None and not df.empty:
                df = df.sort_values("日期")
                return df
        except Exception as e2:
            logger.error(f"ETF {symbol} 历史数据双重失败: {e2}")
        return pd.DataFrame()


# ── 场外基金 (OTC Fund) 净值 ─────────────────────────────

def fetch_otc_fund_nav(symbol: str) -> dict[str, Any] | None:
    """
    获取场外基金最新净值和近期表现。
    使用 akshare 基金信息接口，返回最新一条净值记录。
    """
    try:
        # 尝试用 akshare 获取基金净值走势
        df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
        if df is None or df.empty:
            logger.warning(f"场外基金 {symbol} 无数据返回")
            return None
        df = df.sort_values("净值日期") if "净值日期" in df.columns else df
        latest = df.iloc[-1]
        return {
            "code": symbol,
            "date": str(latest.get("净值日期", "")),
            "nav": _safe_float(latest.get("单位净值", latest.get("累计净值"))),
            "daily_change": _safe_float(
                latest.get("日增长率", latest.get("日增长值"))
            ),
        }
    except Exception as e:
        logger.error(f"场外基金 {symbol} 数据抓取失败: {e}")
        return None


def calc_period_return(df: pd.DataFrame, col: str = "单位净值", period_days: int = 7,
                       daily_change_col: str = "日增长率") -> float | None:
    """
    计算区间收益率。
    优先使用日增长率复合（避免拆分导致的净值跳变问题）；
    如果日增长率不可用，回退到净值直接比较。
    """
    if df is None or df.empty or len(df) < 2:
        return None
    try:
        # 优先：用日增长率逐日复合，天然处理拆分复权
        if daily_change_col in df.columns:
            # 取最后 period_days 个交易日的日增长率
            recent = df.iloc[-(period_days):]
            cumulative = 1.0
            valid_days = 0
            for _, row in recent.iterrows():
                chg = row[daily_change_col]
                if chg is not None and not pd.isna(float(chg)):
                    cumulative *= (1 + float(chg) / 100)
                    valid_days += 1
            if valid_days > 0:
                return round((cumulative - 1) * 100, 2)

        # 回退：净值直接比较（仅在无拆分的干净数据上准确）
        latest = float(df[col].iloc[-1])
        past_idx = max(0, len(df) - period_days - 1)
        past = float(df[col].iloc[past_idx])
        if past == 0 or pd.isna(past):
            return None
        return round((latest - past) / past * 100, 2)
    except (ValueError, IndexError, KeyError):
        return None


# ── 板块/指数数据 ─────────────────────────────────────────

def fetch_semiconductor_index() -> dict[str, Any]:
    """
    获取中证半导体材料设备主题指数 (931743) 近况。
    如 931743 不可用，回退到 '半导体' 行业板块。
    """
    try:
        df = ak.stock_board_industry_hist_em(symbol="半导体", period="日k", start_date="20260101", end_date="20500101")
        if df is None or df.empty:
            return {"name": "半导体板块", "latest": None, "change_pct": None}
        df = df.sort_values("日期")
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        return {
            "name": "半导体板块",
            "date": str(latest.get("日期", "")),
            "close": _safe_float(latest.get("收盘")),
            "change_pct": round(
                float(latest.get("涨跌幅", 0)), 2
            ),
            "prev_close": _safe_float(prev.get("收盘")),
        }
    except Exception as e:
        logger.error(f"半导体板块数据抓取失败: {e}")
        return {"name": "半导体板块", "latest": None, "change_pct": None}


def fetch_market_overview() -> dict[str, Any]:
    """获取今日大盘概况：上证、深证、创业板涨跌"""
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
        logger.error(f"大盘数据抓取失败: {e}")
        return {}


# ── 重仓股行情 ───────────────────────────────────────────

HEAVY_HOLDINGS = [
    ("688012", "中微公司"),
    ("002371", "北方华创"),
    ("688072", "拓荆科技"),
    ("300604", "长川科技"),
    ("688981", "中芯国际"),
]


def fetch_heavy_holdings() -> list[dict[str, Any]]:
    """获取关键重仓股今日行情"""
    try:
        df = ak.stock_zh_a_spot_em()
        # 过滤出重仓股
        codes = [h[0] for h in HEAVY_HOLDINGS]
        df = df[df["代码"].isin(codes)]
        results = []
        for _, row in df.iterrows():
            results.append({
                "code": str(row["代码"]),
                "name": str(row["名称"]),
                "price": _safe_float(row["最新价"]),
                "change_pct": _safe_float(row["涨跌幅"]),
                "volume": _safe_float(row["成交量"]),
                "amount": _safe_float(row["成交额"]),
            })
        return results
    except Exception as e:
        logger.error(f"重仓股行情抓取失败: {e}")
        return []


# ── 组装导出 ─────────────────────────────────────────────

def fetch_all() -> dict[str, Any]:
    """
    主入口：抓取全部所需数据，返回结构化 dict。
    """
    ensure_data_dir()
    portfolio = load_portfolio()

    # 分类基金代码
    etf_codes = []
    otc_codes = []
    for h in portfolio.get("holdings", []):
        code = str(h["code"])
        if h.get("type") == "ETF":
            etf_codes.append(code)
        else:
            otc_codes.append(code)

    # 加入 watchlist 中的 ETF
    for w in portfolio.get("watchlist", []):
        code = str(w["code"])
        if code not in etf_codes:
            etf_codes.append(code)

    # 抓取
    etf_data = fetch_etf_spot(etf_codes) if etf_codes else {}
    otc_data = {code: fetch_otc_fund_nav(code) for code in otc_codes}
    market = fetch_market_overview()
    semiconductor = fetch_semiconductor_index()
    heavy = fetch_heavy_holdings()

    # ETF 计算近期涨跌幅（基于净值，已处理拆分复权）
    etf_perf: dict[str, dict[str, Any]] = {}
    for code in etf_codes:
        hist = fetch_etf_hist(code)  # 获取全部历史数据，用于准确计算YTD等
        if not hist.empty:
            # 自动检测净值列名：优先用"单位净值"（来自 NAV 接口），回退到"收盘"
            if "单位净值" in hist.columns:
                nav_col = "单位净值"
            elif "收盘" in hist.columns:
                nav_col = "收盘"
            else:
                nav_col = hist.columns[1]  # 盲猜第二列是净值
            etf_perf[code] = {
                "w1": calc_period_return(hist, col=nav_col, period_days=5),
                "m1": calc_period_return(hist, col=nav_col, period_days=22),
                "m3": calc_period_return(hist, col=nav_col, period_days=66),
                "ytd": calc_period_return(hist, col=nav_col, period_days=140),
            }
        else:
            etf_perf[code] = {"w1": None, "m1": None, "m3": None, "ytd": None}

    return {
        "timestamp": datetime.now().isoformat(),
        "portfolio": portfolio,
        "etf_data": etf_data,
        "otc_data": otc_data,
        "etf_performance": etf_perf,
        "market_overview": market,
        "semiconductor": semiconductor,
        "heavy_holdings": heavy,
    }


# ── 工具函数 ─────────────────────────────────────────────

def _safe_float(val: Any) -> float | None:
    """安全转型 float，失败返回 None"""
    if val is None:
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else round(f, 4)
    except (ValueError, TypeError):
        return None


def save_cache(data: dict[str, Any], filename: str = "latest_data.json") -> None:
    """将抓取结果缓存到 data/ 目录"""
    ensure_data_dir()
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def load_cache(filename: str = "latest_data.json") -> dict[str, Any] | None:
    """读取缓存数据"""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_all()
    save_cache(data)
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
