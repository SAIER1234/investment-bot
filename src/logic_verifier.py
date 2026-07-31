"""
逻辑验证器 — 每月自动检查持仓"买入逻辑是否仍然成立"
不靠AI判断，直接算数字。输出明确结论。
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

SNAPSHOT_FILE = "pe_snapshot.json"  # 存储历史PE快照


def take_snapshot() -> dict[str, dict[str, Any]]:
    """对当前持仓的每只基金拍照：日期、PE、PE分位"""
    portfolio = load_json(os.path.join(CONFIG_DIR, "portfolio.json"))
    holdings = [h for h in portfolio.get("holdings", []) if not h.get("planned")]

    snapshot: dict[str, dict[str, Any]] = {}
    today = date.today().isoformat()

    from src.fetch_data import fetch_index_valuation
    from src.fetch_data import fetch_otc_fund_nav

    for h in holdings:
        code = h["code"]
        val = fetch_index_valuation(code)
        nav = fetch_otc_fund_nav(code)

        entry = {
            "date": today,
            "pe": val.get("pe") if val else None,
            "pe_pct": val.get("pe_percentile") if val else None,
            "nav": nav.get("nav") if nav else None,
            "daily_change": nav.get("daily_change") if nav else None,
        }
        snapshot[code] = entry

    # 加载旧快照列表
    ensure_data_dir()
    path = os.path.join(DATA_DIR, SNAPSHOT_FILE)
    history = {}
    if os.path.exists(path):
        try:
            history = load_json(path)
        except Exception:
            history = {}

    # 追加新快照（按日期索引）
    if today not in history:
        history[today] = {}

    for code, entry in snapshot.items():
        history[today][code] = entry

    save_json(path, history)
    logger.info(f"PE快照已保存: {today}, {len(snapshot)}只基金")
    return snapshot


def verify() -> dict[str, Any]:
    """
    主入口：验证每只持仓的买入逻辑。
    对比当前PE分位 vs 三个月前PE分位。
    返回 {基金代码: {verdict, reason, action}}
    """
    today = date.today()
    three_months_ago = today - timedelta(days=90)

    # 找最接近三个月前的快照
    path = os.path.join(DATA_DIR, SNAPSHOT_FILE)
    if not os.path.exists(path):
        return {"error": "无PE快照数据。请先运行take_snapshot()积累数据。"}

    history = load_json(path)
    dates = sorted(history.keys())
    if len(dates) < 2:
        return {"error": f"快照数据不足（仅{len(dates)}天）"}

    # 找最接近三个月前的快照
    target = three_months_ago.isoformat()
    past_date = None
    for d in sorted(dates):
        if d < target:
            past_date = d
        else:
            break

    if not past_date:
        # 没有三个月前的数据，用最早的那天
        past_date = dates[0]

    if today.isoformat() not in history:
        # 今天还没拍照，先拍
        take_snapshot()
        history = load_json(path)

    current = history.get(today.isoformat(), {})
    past = history.get(past_date, {})

    results: dict[str, Any] = {}
    for code in current:
        if code not in past:
            continue

        cur = current[code]
        pst = past[code]

        cur_pe_pct = cur.get("pe_pct")
        past_pe_pct = pst.get("pe_pct")

        if cur_pe_pct is None or past_pe_pct is None:
            results[code] = {
                "verdict": "数据不足",
                "reason": "PE分位数据缺失",
                "action": "无法判断",
            }
            continue

        delta_pct = round(cur_pe_pct - past_pe_pct, 1)
        cur_nav = cur.get("nav")
        past_nav = pst.get("nav")
        nav_change = round((cur_nav / past_nav - 1) * 100, 1) if cur_nav and past_nav else None
        cur_pe = cur.get("pe")
        past_pe = pst.get("pe")

        if delta_pct > 5:
            # PE分位上升了超过5个百分点 — 要检查利润
            if nav_change is not None and nav_change < 0:
                # NAV跌了+PE分位升了 = 陷阱信号
                results[code] = {
                    "verdict": "⚠️ 警惕",
                    "reason": f"PE分位+{delta_pct}%（{past_pe_pct}%→{cur_pe_pct}%），但净值{nav_change:+.1f}%。PE分位被动上升=利润可能在恶化",
                    "action": "检查利润数据。如果利润确实下滑→触发W2，减2/3仓",
                }
            else:
                # PE分位升了但NAV在涨 — 可能是利润驱动
                results[code] = {
                    "verdict": "🟡 关注",
                    "reason": f"PE分位+{delta_pct}%（{past_pe_pct}%→{cur_pe_pct}%），净值{nav_change:+.1f}%",
                    "action": "确认利润增速。如果利润增速>PE扩张→正常；否则→W1，减半仓",
                }
        elif delta_pct < -5:
            results[code] = {
                "verdict": "✅ 健康",
                "reason": f"PE分位{delta_pct:+.1f}%（{past_pe_pct}%→{cur_pe_pct}%），估值在改善",
                "action": "继续持有",
            }
        else:
            results[code] = {
                "verdict": "✅ 稳定",
                "reason": f"PE分位变化不大（{delta_pct:+.1f}%），估值未见显著恶化",
                "action": "继续持有",
            }

    return {
        "date": today.isoformat(),
        "past_date": past_date,
        "results": results,
    }


def format_verification(results: dict[str, Any]) -> str:
    """格式化为给DeepSeek的prompt片段"""
    if "error" in results:
        return f"逻辑验证暂不可用: {results['error']}\n"

    lines = [
        "## 月度逻辑验证\n",
        f"对比日期: {results.get('past_date','?')} → {results.get('date','?')}\n"
    ]

    data = results.get("results", {})
    for code, r in data.items():
        lines.append(f"**{code}** | {r['verdict']}")
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
