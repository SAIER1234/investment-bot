"""
逻辑验证器 — 配置驱动，自动检查持仓"买入逻辑是否仍然成立"
每只基金在portfolio.json中可配置 verify_with 字段指定验证方式。
"""

import json
import logging
import os
from datetime import date, timedelta
from typing import Any

from src.common import CONFIG_DIR, DATA_DIR, disable_proxy, load_json, save_json, ensure_data_dir

disable_proxy()

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

SNAPSHOT_FILE = "pe_snapshot.json"

# ── 验证方式解析 ──────────────────────────────────────

# verify_with 字段格式：
#   "931719" → 直接用该CSI指数PE
#   "" 或 null → 跳过验证（该基金无可验证PE数据）
#   不存在该字段 → 跳过验证

def _get_verifiable_holdings() -> list[dict[str, Any]]:
    """读取portfolio，返回所有可验证的持仓（有 verify_with 字段且非空）"""
    portfolio = load_json(os.path.join(CONFIG_DIR, "portfolio.json"))
    result = []
    for h in portfolio.get("holdings", []):
        if h.get("planned"):
            continue
        verify_code = h.get("verify_with", "").strip()
        if verify_code:
            h["_verify_code"] = verify_code
            result.append(h)
    return result


# ── 快照 ──────────────────────────────────────────────

def take_snapshot() -> dict[str, dict[str, Any]]:
    """
    对所有可验证持仓拍照：日期、PE、PE分位、净值。
    每天运行积累历史数据。
    """
    verifiable = _get_verifiable_holdings()
    if not verifiable:
        logger.info("无可验证持仓，跳过快照")
        return {}

    today = date.today().isoformat()
    snapshot: dict[str, dict[str, Any]] = {}

    from src.fetch_data import fetch_index_valuation, fetch_otc_fund_nav

    for h in verifiable:
        code = h["code"]
        verify_code = h["_verify_code"]

        # 用 verify_with 指定的指数获取PE
        val = fetch_index_valuation_direct(verify_code)
        nav = fetch_otc_fund_nav(code)

        entry = {
            "date": today,
            "fund_code": code,
            "verify_index": verify_code,
            "pe": val.get("pe") if val else None,
            "pe_pct": val.get("pe_percentile") if val else None,
            "nav": nav.get("nav") if nav else None,
        }
        snapshot[code] = entry
        logger.info(f"快照: {code} PE={entry['pe']} PE分位={entry['pe_pct']}%")

    # 存储
    ensure_data_dir()
    path = os.path.join(DATA_DIR, SNAPSHOT_FILE)
    history = load_json(path) if os.path.exists(path) else {}
    if today not in history:
        history[today] = {}
    for code, entry in snapshot.items():
        history[today][code] = entry
    save_json(path, history)

    logger.info(f"快照已保存: {today}, {len(snapshot)}只")
    return snapshot


def fetch_index_valuation_direct(index_code: str) -> dict[str, Any] | None:
    """用CSI指数代码直接获取PE和分位"""
    try:
        df = ak.stock_zh_index_hist_csindex(symbol=index_code, start_date="20050101", end_date=f"{date.today().year+5}0101")
        pe_col = "滚动市盈率"
        df_c = df.dropna(subset=[pe_col])
        if df_c.empty:
            return None
        pe_series = df_c[pe_col]
        latest = df_c.iloc[-1]
        cur_pe = float(latest[pe_col])
        cur_pct = round((pe_series < cur_pe).sum() / len(pe_series) * 100, 1)
        return {
            "index_name": str(index_code),
            "pe": round(cur_pe, 1),
            "pe_percentile": cur_pct,
            "update_time": str(latest.get("日期", "")),
            "source": "csindex direct",
        }
    except Exception as e:
        logger.warning(f"指数{index_code} PE获取失败: {e}")
        return None


def verify() -> dict[str, Any]:
    """
    主入口：只验证 portfolio.json 中配置了 verify_with 的持仓。
    对比当前PE分位 vs 90天前。自动计算利润变化。
    """
    verifiable = _get_verifiable_holdings()
    if not verifiable:
        return {"error": "portfolio.json中无verify_with配置，无可验证持仓"}

    today = date.today()
    path = os.path.join(DATA_DIR, SNAPSHOT_FILE)

    if not os.path.exists(path):
        return {"error": "无快照数据。take_snapshot()尚未积累足够数据。"}

    history = load_json(path)
    dates = sorted(history.keys())

    # 找最早可用快照（最少2天即可开始验证，首选~90天前）
    if len(dates) < 2:
        return {"error": "快照不足，需至少2天数据"}
    target = (today - timedelta(days=90)).isoformat()
    past_date = dates[0]
    for d in dates:
        if d < target:
            past_date = d
        else:
            break
    days_available = (today - date.fromisoformat(past_date)).days

    if today.isoformat() not in history:
        take_snapshot()
        history = load_json(path)

    current = history.get(today.isoformat(), {})
    past = history.get(past_date, {})

    results: dict[str, Any] = {}
    alert_triggered = False

    for code, cur in current.items():
        if code not in past:
            results[code] = {"verdict": "数据积累中", "reason": "快照<90天，再等等", "action": "无"}
            continue

        pst = past[code]
        cur_pe_pct = cur.get("pe_pct")
        past_pe_pct = pst.get("pe_pct")
        if cur_pe_pct is None or past_pe_pct is None:
            results[code] = {"verdict": "数据不足", "reason": "PE分位缺失", "action": "无"}
            continue

        delta_pct = round(cur_pe_pct - past_pe_pct, 1)
        cur_nav = cur.get("nav")
        past_nav = pst.get("nav")
        cur_pe = cur.get("pe")
        past_pe = pst.get("pe")

        # 利润变化 ≈ 净值变化 - PE变化（PE公式倒推）
        profit_change = None
        if cur_pe and past_pe and cur_pe > 0 and past_pe > 0 and cur_nav and past_nav:
            pe_change = (cur_pe / past_pe - 1) * 100
            nav_change = (cur_nav / past_nav - 1) * 100
            profit_change = round(nav_change - pe_change, 1)

        # 判断逻辑：PE分位变化>5个百分点 + 利润变化
        if abs(delta_pct) <= 5:
            results[code] = {"verdict": "✅ 稳定", "reason": f"PE分位变化{delta_pct:+.1f}%，估值平稳", "action": "继续持有"}
        elif delta_pct > 5:
            if profit_change is not None and profit_change < 0:
                alert_triggered = True
                results[code] = {
                    "verdict": "⚠️ W2触发",
                    "reason": f"PE分位+{delta_pct}%（{past_pe_pct}→{cur_pe_pct}%），利润约{profit_change:+.1f}%。PE被动上升=利润恶化",
                    "action": "减2/3仓。PE涨了但利润在跌，买入逻辑被证伪。",
                }
            elif profit_change is not None and profit_change > 0:
                results[code] = {
                    "verdict": "✅ 健康",
                    "reason": f"PE分位+{delta_pct}%，但利润约{profit_change:+.1f}%，跑赢PE扩张",
                    "action": "继续持有。利润驱动，非情绪。",
                }
            else:
                alert_triggered = True
                results[code] = {
                    "verdict": "🟡 W1触发",
                    "reason": f"PE分位+{delta_pct}%（{past_pe_pct}→{cur_pe_pct}%），利润数据不足无法判断",
                    "action": "减半仓。PE在涨但利润数据缺失，价格可能已超过价值。",
                }
        else:  # delta < -5
            results[code] = {
                "verdict": "✅ 改善",
                "reason": f"PE分位{delta_pct:+.1f}%（{past_pe_pct}→{cur_pe_pct}%），估值在改善",
                "action": "继续持有",
            }

    return {
        "date": today.isoformat(),
        "past_date": past_date,
        "days_available": days_available,
        "warmup": days_available < 30,
        "has_alert": alert_triggered,
        "results": results,
    }


def format_verification(results: dict[str, Any]) -> str:
    """格式化为给DeepSeek的prompt片段"""
    if "error" in results:
        return f"逻辑验证暂不可用: {results['error']}\n"

    lines = [
        "## 月度逻辑验证\n",
        f"对比日期: {results.get('past_date','?')} → {results.get('date','?')}"
    ]
    if results.get("warmup"):
        lines.append(f" (预热中，仅{results.get('days_available','?')}天数据，参考有限)")
    lines.append("\n")

    data = results.get("results", {})
    for code, r in data.items():
        # 用基金名替代裸代码
        from src.common import CONFIG_DIR, load_json
        import os
        fund_name = code
        try:
            pf = load_json(os.path.join(CONFIG_DIR, "portfolio.json"))
            for h in pf.get("holdings", []):
                if h["code"] == code:
                    fund_name = f"{h['name']}({code})"
                    break
        except: pass
        lines.append(f"**{fund_name}** | {r['verdict']}")
        lines.append(f"  {r['reason']}")
        if r['action'] != "继续持有":
            lines.append(f"  → {r['action']}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("拍快照...")
    take_snapshot()
    print("验证逻辑...")
    result = verify()
    print(format_verification(result))
