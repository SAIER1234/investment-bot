"""
基金发现引擎
每周扫描全市场场外基金，按用户偏好筛选候选，交给DeepSeek做最终推荐。
"""

import logging
import os
from datetime import datetime, date
from typing import Any

from src.common import CONFIG_DIR, DATA_DIR, disable_proxy, ensure_data_dir, load_json, save_json

disable_proxy()

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

# ── 扫描配置 ──
# 每类最多取排名前N
TOP_PER_CATEGORY = 30
# 扫描的基金类型
SCAN_CATEGORIES = ["股票型", "混合型", "指数型", "QDII"]
# 最少需要的业绩数据列（用来推断基金年龄）
# 近1月、近3月、近6月、近1年、近2年、近3年
PERF_COLS = ["近1月", "近3月", "近6月", "近1年", "近2年", "近3年"]
# 防御型类别（估值太高时推）
DEFENSE_CATEGORIES = ["债券型"]

# 热门赛道关键词（用于标记基金属于哪个赛道）
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "半导体/AI": ["半导体", "芯片", "人工智能", "AI", "集成电路", "科创"],
    "新能源": ["新能源", "电池", "光伏", "锂电", "储能", "碳中和", "绿色"],
    "消费": ["消费", "白酒", "食品", "饮料", "家电"],
    "医药": ["医药", "医疗", "生物", "创新药", "中药"],
    "军工": ["军工", "国防", "航天"],
    "红利/价值": ["红利", "股息", "价值", "低波"],
    "机器人/高端制造": ["机器人", "高端制造", "智能制造", "工业母机"],
    "低空经济": ["低空", "飞行汽车", "无人机"],
    "量子/前沿": ["量子", "核聚变", "超导"],
    "海外": ["纳斯达克", "标普", "全球", "海外", "港股通"],
    "债券/固收": ["债券", "转债", "纯债", "信用"],
}

# 用户已持仓的基金代码（避免重复推荐）
EXCLUDED_CODES: set[str] = set()


def load_portfolio_codes() -> set[str]:
    """从 portfolio.json 加载已持仓/计划中的基金代码"""
    try:
        pf = load_json(os.path.join(CONFIG_DIR, "portfolio.json"))
        codes = {str(h["code"]) for h in pf.get("holdings", [])}
        return codes
    except Exception:
        return set()


def fetch_category_rank(symbol: str) -> pd.DataFrame:
    """获取某一类基金的排名数据"""
    try:
        df = ak.fund_open_fund_rank_em(symbol=symbol)
        if df is None or df.empty:
            logger.warning(f"基金排行 {symbol} 返回空")
            return pd.DataFrame()
        logger.info(f"  {symbol}: {len(df)} 只基金")
        return df
    except Exception as e:
        logger.error(f"基金排行 {symbol} 失败: {e}")
        return pd.DataFrame()


def _safe_f(val: Any) -> float:
    """安全转float"""
    try:
        return float(val)
    except (ValueError, TypeError):
        return float("nan")


def classify_sector(name: str) -> str:
    """根据基金名称归类赛道"""
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return sector
    return "其他"


def _estimate_mgmt_fee(category: str) -> float:
    """根据基金类型估算年管理费率"""
    fee_map = {
        "股票型": 1.2,
        "混合型": 1.2,
        "指数型": 0.4,
        "QDII": 1.5,
        "债券型": 0.5,
    }
    return fee_map.get(category, 1.2)


def _strip_class_suffix(name: str) -> str:
    """去掉基金名称末尾的A/C/E类后缀，用于去重"""
    import re
    # 去掉末尾的 A/B/C/E 类标记（可能跟着数字）
    return re.sub(r'[ABCE]$', '', name.strip())


def score_fund(row: pd.Series, category: str) -> float:
    """
    综合打分（0-100）。
    权重：近1年30% + 近6月20% + 近3月15% + 今年15% + 费率20%
    在同类基金内相对打分，避免因类别差异导致偏差。
    """
    score = 0.0

    y1 = _safe_f(row.iloc[11]) if len(row) > 11 else 0  # 近1年
    m6 = _safe_f(row.iloc[10]) if len(row) > 10 else 0  # 近6月
    m3 = _safe_f(row.iloc[9]) if len(row) > 9 else 0    # 近3月
    ytd = _safe_f(row.iloc[14]) if len(row) > 14 else 0  # 今年来

    # 业绩得分（0-80，温和截断避免极端值主导）
    score += min(max(y1 / 10, 0), 8) * 3.75   # 近1年: 0-30分
    score += min(max(m6 / 10, 0), 8) * 2.5    # 近6月: 0-20分
    score += min(max(m3 / 10, 0), 8) * 1.875  # 近3月: 0-15分
    score += min(max(ytd / 10, 0), 8) * 1.875 # 今年来: 0-15分

    # 费率得分（0-20）— 管理费越低分越高
    mgmt_fee = _estimate_mgmt_fee(category)
    fee_score = max(0, (2.0 - mgmt_fee) / 2.0 * 20)
    score += fee_score

    return round(score, 1)


def scan_all(global_pe_high: bool = False) -> dict[str, Any]:
    """
    主入口：扫描全市场基金，返回候选列表。
    如果 global_pe_high=True（市场整体估值偏高），加入防御型候选。
    """
    global EXCLUDED_CODES
    EXCLUDED_CODES = load_portfolio_codes()
    logger.info(f"已持仓/计划代码: {EXCLUDED_CODES}")

    categories = SCAN_CATEGORIES.copy()
    if global_pe_high:
        categories += DEFENSE_CATEGORIES
        logger.info("市场估值偏高，加入防御型扫描")

    all_candidates: list[dict[str, Any]] = []
    seen_base_names: set[str] = set()  # A/C类去重

    for cat in categories:
        df = fetch_category_rank(cat)
        if df.empty:
            continue

        for _, row in df.iterrows():
            code = str(row.iloc[1]) if len(row) > 1 else ""   # 基金代码
            name = str(row.iloc[2]) if len(row) > 2 else ""   # 基金简称

            # 跳过已持仓
            if code in EXCLUDED_CODES:
                continue

            # 跳过没有近2年数据的（可能成立不足2年）
            y2 = _safe_f(row.iloc[12]) if len(row) > 12 else float("nan")
            if pd.isna(y2):
                continue

            # A/C类去重：同一基金只保留A类（或C类如果A不存在）
            base_name = _strip_class_suffix(name)
            if base_name in seen_base_names:
                continue
            seen_base_names.add(base_name)

            sector = classify_sector(name)
            score = score_fund(row, cat)

            all_candidates.append({
                "code": code,
                "name": name,
                "category": cat,
                "sector": sector,
                "nav": _safe_f(row.iloc[4]) if len(row) > 4 else None,
                "nav_date": str(row.iloc[3])[:10] if len(row) > 3 else "",
                "daily_change": _safe_f(row.iloc[6]) if len(row) > 6 else None,
                "perf_1w": _safe_f(row.iloc[7]) if len(row) > 7 else None,
                "perf_1m": _safe_f(row.iloc[8]) if len(row) > 8 else None,
                "perf_3m": _safe_f(row.iloc[9]) if len(row) > 9 else None,
                "perf_6m": _safe_f(row.iloc[10]) if len(row) > 10 else None,
                "perf_1y": _safe_f(row.iloc[11]) if len(row) > 11 else None,
                "perf_2y": _safe_f(row.iloc[12]) if len(row) > 12 else None,
                "perf_3y": _safe_f(row.iloc[13]) if len(row) > 13 else None,
                "perf_ytd": _safe_f(row.iloc[14]) if len(row) > 14 else None,
                "perf_since_inception": _safe_f(row.iloc[15]) if len(row) > 15 else None,
                "mgmt_fee_est": _estimate_mgmt_fee(cat),
                "score": score,
            })

    # 去重 + 按分数排序
    df_all = pd.DataFrame(all_candidates)
    if df_all.empty:
        return {"candidates": [], "scan_date": datetime.now().isoformat()}

    df_all = df_all.drop_duplicates(subset=["code"])
    df_all = df_all.sort_values("score", ascending=False)

    # 每个赛道最多取3支（保证多样性），总共不超过15支
    final_candidates: list[dict[str, Any]] = []
    sector_counts: dict[str, int] = {}
    for _, row in df_all.iterrows():
        sector = row["sector"]
        if sector_counts.get(sector, 0) >= 3:
            continue
        final_candidates.append(row.to_dict())
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(final_candidates) >= 15:
            break

    logger.info(f"扫描完成: 候选 {len(final_candidates)} 支，覆盖 {len(sector_counts)} 个赛道")
    for s, c in sorted(sector_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {s}: {c} 支")

    return {
        "candidates": final_candidates,
        "scan_date": datetime.now().isoformat(),
        "scan_categories": categories,
        "sectors_covered": list(sector_counts.keys()),
    }


def scan_if_needed(data_dir: str | None = None) -> dict[str, Any] | None:
    """
    判断今天是否需要扫描（仅周五扫描，或7天未扫描）。
    返回扫描结果或 None（今天不扫）。
    """
    if data_dir is None:
        data_dir = DATA_DIR

    ensure_data_dir()
    cache_path = os.path.join(data_dir, "fund_scan_cache.json")

    today = date.today()
    is_friday = today.weekday() == 4

    # 检查缓存
    if os.path.exists(cache_path):
        try:
            cache = load_json(cache_path)
            scan_date = cache.get("scan_date", "")[:10]
            if scan_date:
                last_scan = date.fromisoformat(scan_date)
                days_since = (today - last_scan).days
                # 7天内扫过 → 复用
                if days_since < 7:
                    logger.info(f"复用 {days_since} 天前的扫描结果 ({scan_date})")
                    return cache
        except Exception:
            pass

    # 周五或超过7天 → 重新扫描
    if is_friday or not os.path.exists(cache_path):
        logger.info(f"{'周五' if is_friday else '超过7天'}，触发全网扫描")
        result = scan_all()
        save_json(cache_path, result)
        return result

    # 非周五但有缓存 → 复用
    if os.path.exists(cache_path):
        try:
            return load_json(cache_path)
        except Exception:
            pass

    return None


def format_scanner_prompt(candidates: list[dict[str, Any]]) -> str:
    """
    把扫描候选列表格式化为给DeepSeek的prompt片段。
    """
    if not candidates:
        return "本周未触发全网扫描（非周五且7天内有缓存），暂无新的基金推荐。\n"

    lines = [
        "## 基金雷达（全网扫描候选）\n",
        f"以下是从全市场筛选出的 **{len(candidates)} 支** 候选基金，覆盖多个赛道：\n",
    ]

    for i, f in enumerate(candidates, 1):
        lines.append(
            f"{i}. **{f['name']}** `{f['code']}` [{f['sector']}] [{f['category']}]\n"
            f"   - 净值: {f['nav']} ({f['nav_date']})\n"
            f"   - 表现: 1月{f.get('perf_1m', 0) or 0:+.1f}% | "
            f"3月{f.get('perf_3m', 0) or 0:+.1f}% | "
            f"6月{f.get('perf_6m', 0) or 0:+.1f}% | "
            f"1年{f.get('perf_1y', 0) or 0:+.1f}% | "
            f"YTD{f.get('perf_ytd', 0) or 0:+.1f}%\n"
            f"   - 管理费: ~{f['mgmt_fee_est']}%/年 | 综合评分: {f['score']}/100\n"
        )

    lines.append("")
    lines.append("请从以上候选中，选出 **1-3支** 最适合用户的基金作为本周推荐。")
    lines.append("选择标准：前景好 + 估值合理 + 费率合理 + 与用户现有持仓形成互补（不要和已持有的高度重复）。")
    lines.append("对每支推荐基金，给出：推荐理由（2-3条）、建议仓位、适合什么时机买入。")

    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = scan_all()
    print(f"\n=== 扫描结果: {len(result['candidates'])} 支候选 ===")
    for c in result["candidates"]:
        print(f"  [{c['sector']}] {c['name']} {c['code']} score={c['score']} "
              f"1y={c.get('perf_1y',0) or 0:+.1f}% fee~{c['mgmt_fee_est']}%/yr")
