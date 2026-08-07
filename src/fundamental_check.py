"""
基本面验证模块 — 配置驱动
从 portfolio.json 读取 verify_with 字段 → CSI指数成分股 → 抓财报 → 汇总判断
月度运行（每月1日），换仓无需改代码。
"""
import logging
import os
from datetime import date
from typing import Any

from src.common import CONFIG_DIR, DATA_DIR, disable_proxy, ensure_data_dir, load_json, save_json

disable_proxy()

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

CACHE_FILE = "fundamental_check_cache.json"

# 用于分析财报的关键列索引（避免编码问题）
# stock_financial_abstract_ths 列: 报告期, 净利润, 净利润同比增长率, 扣非净利润, 扣非净利润同比增长率,
#                                    营业收入, 营业收入同比增长率, ...
COL_PERIOD = 0       # 报告期
COL_PROFIT = 1       # 净利润
COL_PROFIT_YOY = 2   # 净利润同比增长率
COL_REVENUE = 5      # 营业收入
COL_REVENUE_YOY = 6  # 营业收入同比增长率

# 取成分股数量：50只全取保证龙头股被包含
# index_stock_cons_csindex 按代码排序非权重排序，只取前N会漏掉宁德时代等大票
TOP_N_STOCKS = 50


def _get_verifiable_holdings() -> list[dict[str, Any]]:
    """读取portfolio，返回所有有 verify_with 的持仓"""
    portfolio = load_json(os.path.join(CONFIG_DIR, "portfolio.json"))
    result = []
    for h in portfolio.get("holdings", []):
        if h.get("planned"):
            continue
        verify_code = (h.get("verify_with") or "").strip()
        if verify_code:
            h["_verify_code"] = verify_code
            result.append(h)
    return result


def fetch_index_constituents(index_code: str) -> pd.DataFrame:
    """获取CSI指数成分股及权重"""
    try:
        df = ak.index_stock_cons_csindex(symbol=index_code)
        if df is not None and not df.empty:
            # 列: 日期, 指数代码, 指数名称, 指数英文名称, 成分券代码, 成分券名称, 成分券英文名称, 交易所, 交易所英文名称
            return df
    except Exception as e:
        logger.warning(f"指数{index_code}成分股获取失败: {e}")
    return pd.DataFrame()


def fetch_stock_financials(stock_code: str) -> dict[str, Any] | None:
    """获取单只股票最新季度财务数据，返回核心指标"""
    try:
        df = ak.stock_financial_abstract_ths(symbol=stock_code, indicator='按报告期')
        if df is None or df.empty or len(df) < 2:
            return None

        # 最新两个报告期
        latest = df.iloc[-1]
        prev_year = df.iloc[-5] if len(df) >= 5 else df.iloc[0]  # 去年同期（4个季度前）

        def _num(val: Any) -> float | None:
            """解析数字，处理'490.34亿', '41.98%'等格式"""
            import re
            try:
                if isinstance(val, (int, float)):
                    return float(val) if not pd.isna(float(val)) else None
                s = str(val).replace(',', '').replace(' ', '').strip()
                if s == 'False' or s == '' or s == '--':
                    return None
                # 去掉百分号
                is_pct = s.endswith('%')
                s = s.rstrip('%')
                # 匹配数字部分：可能以中文单位结尾
                m = re.match(r'^(-?[\d.]+)(.*)$', s)
                if not m:
                    return None
                num = float(m.group(1))
                unit = m.group(2)
                # 中文单位转换
                if '亿' in unit:
                    pass  # already in 亿
                elif '万' in unit:
                    num = num / 10000
                elif unit and unit != '':
                    # 未知后缀，可能是编码问题导致的，忽略
                    pass
                if is_pct:
                    return round(num, 2)  # 百分比直接返回数值
                return round(num, 2)
            except (ValueError, TypeError):
                return None

        profit = _num(latest.iloc[COL_PROFIT])
        profit_yoy = _num(latest.iloc[COL_PROFIT_YOY])
        revenue = _num(latest.iloc[COL_REVENUE])
        revenue_yoy = _num(latest.iloc[COL_REVENUE_YOY])

        return {
            "period": str(latest.iloc[COL_PERIOD]),
            "profit": profit,
            "profit_yoy": profit_yoy,
            "revenue": revenue,
            "revenue_yoy": revenue_yoy,
        }
    except Exception as e:
        logger.warning(f"{stock_code} 财报获取失败: {e}")
        return None


def check_fund(fund_code: str, fund_name: str, index_code: str) -> dict[str, Any]:
    """
    检查单只基金的基本面。
    流程：CSI指数成分股 → Top N权重股 → 抓财报 → 汇总判断
    """
    result = {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "index_code": index_code,
        "stocks_checked": 0,
        "profit_growing": 0,
        "revenue_growing": 0,
        "total_stocks": 0,
        "median_profit_yoy": None,
        "median_revenue_yoy": None,
        "verdict": "数据不足",
        "ok": False,
    }

    # 1. 获取成分股
    constituents = fetch_index_constituents(index_code)
    if constituents.empty:
        result["verdict"] = "无法获取指数成分股"
        return result

    # 2. 取前N只（按权重排序，取前TOP_N_STOCKS）
    # index_stock_cons_csindex 返回顺序通常就是权重顺序
    top_stocks = []
    for _, row in constituents.head(TOP_N_STOCKS).iterrows():
        stock_code = str(row.iloc[4]) if len(row) > 4 else ""  # 成分券代码
        stock_name = str(row.iloc[5]) if len(row) > 5 else ""  # 成分券名称
        if stock_code:
            top_stocks.append((stock_code, stock_name))

    if not top_stocks:
        result["verdict"] = "未找到成分股代码"
        return result

    result["total_stocks"] = len(top_stocks)

    # 3. 抓财报
    profit_yoys = []
    revenue_yoys = []
    stock_details = []

    for code, name in top_stocks:
        fin = fetch_stock_financials(code)
        if fin is None:
            continue

        result["stocks_checked"] += 1

        if fin["profit_yoy"] is not None:
            profit_yoys.append(fin["profit_yoy"])
            if fin["profit_yoy"] > 0:
                result["profit_growing"] += 1

        if fin["revenue_yoy"] is not None:
            revenue_yoys.append(fin["revenue_yoy"])
            if fin["revenue_yoy"] > 0:
                result["revenue_growing"] += 1

        stock_details.append({
            "name": name,
            "code": code,
            "period": fin["period"],
            "profit_yoy": fin["profit_yoy"],
            "revenue_yoy": fin["revenue_yoy"],
        })

    # 4. 汇总判断
    checked = result["stocks_checked"]
    if checked == 0:
        result["verdict"] = "无有效财务数据"
        return result

    if profit_yoys:
        result["median_profit_yoy"] = round(float(pd.Series(profit_yoys).median()), 1)
    if revenue_yoys:
        result["median_revenue_yoy"] = round(float(pd.Series(revenue_yoys).median()), 1)

    profit_ratio = result["profit_growing"] / checked * 100
    rev_ratio = result["revenue_growing"] / checked * 100
    med_profit = result["median_profit_yoy"]
    med_rev = result["median_revenue_yoy"]

    # ── 数据质量检查 ──
    # 1. 样本数不足 → 降级为不可靠
    if checked < 30:
        logger.warning(f"{fund_name}: 仅有{checked}只有效数据，样本不足（需>=30）")
        result["detail"] = f"有效样本仅{checked}/{result['total_stocks']}，数据可能不可靠"
        # 仍然给结论但标注
    # 2. 记录龙头股数据用于调试
    for sd in stock_details:
        if sd["code"] in ("300750", "300014"):  # 宁德时代, 亿纬锂能
            logger.info(f"  {sd['name']}({sd['code']}): 利润YoY={sd['profit_yoy']}, 营收YoY={sd['revenue_yoy']}")
    # 3. 对比上次缓存，变化超过30个百分点则警告
    if checked >= 30 and profit_yoys:
        from src.common import DATA_DIR
        cache_path = os.path.join(DATA_DIR, "fundamental_check_cache.json")
        if os.path.exists(cache_path):
            try:
                cache = load_json(cache_path)
                for v in cache.get("verdicts", []):
                    if fund_code in str(v):
                        import re
                        old_match = re.search(r'[-+]?\d+\.?\d*%', v)
                        if old_match:
                            old_median = float(old_match.group().rstrip('%'))
                            new_median = float(med_profit) if med_profit else 0
                            if abs(new_median - old_median) > 30:
                                logger.warning(f"{fund_name}: 利润中位数大幅变化 {old_median:+.1f}% → {new_median:+.1f}%，请核实")
            except Exception:
                pass

    # 三问法自动判断
    # Q1: 利润在涨吗？ → 中位数>0 且 过半公司利润正增长
    profit_ok = med_profit is not None and med_profit > 0 and profit_ratio >= 50
    # Q2: 行业在扩张吗？ → 中位数营收增速>0 且 过半公司营收正增长
    revenue_ok = med_rev is not None and med_rev > 0 and rev_ratio >= 50

    if profit_ok and revenue_ok:
        result["verdict"] = "✅ 逻辑成立"
        mp = f"{med_profit:+.1f}%" if med_profit is not None else "?"
        mr = f"{med_rev:+.1f}%" if med_rev is not None else "?"
        result["detail"] = (f"Top{checked}成分股: 利润中位数{mp}({profit_ratio:.0f}%公司正增长), "
                           f"营收中位数{mr}({rev_ratio:.0f}%公司正增长)")
        result["ok"] = True
    elif not profit_ok and not revenue_ok:
        mp = f"{med_profit:+.1f}%" if med_profit is not None else "?"
        mr = f"{med_rev:+.1f}%" if med_rev is not None else "?"
        result["verdict"] = "❌ 逻辑破裂"
        result["detail"] = (f"Top{checked}成分股: 利润中位数{mp}({profit_ratio:.0f}%公司正增长), "
                           f"营收中位数{mr}({rev_ratio:.0f}%公司正增长)")
    elif not profit_ok:
        mp = f"{med_profit:+.1f}%" if med_profit is not None else "?"
        mr = f"{med_rev:+.1f}%" if med_rev is not None else "?"
        result["verdict"] = "⚠️ 利润恶化"
        result["detail"] = (f"Top{checked}成分股: 利润中位数{mp}({profit_ratio:.0f}%公司正增长), "
                           f"但营收中位数{mr}({rev_ratio:.0f}%公司正增长) — 利润跟不上营收，需关注")
    else:
        mp = f"{med_profit:+.1f}%" if med_profit is not None else "?"
        mr = f"{med_rev:+.1f}%" if med_rev is not None else "?"
        result["verdict"] = "🟡 营收放缓"
        result["detail"] = (f"Top{checked}成分股: 利润中位数{mp}({profit_ratio:.0f}%公司正增长), "
                           f"但营收中位数{mr}({rev_ratio:.0f}%公司正增长) — 营收放缓但利润还在，暂时可接受")

    result["stock_details"] = stock_details
    return result


def check_all_holdings() -> dict[str, Any]:
    """主入口：检查所有可验证持仓的基本面。返回给main.py的结果。"""
    verifiable = _get_verifiable_holdings()
    if not verifiable:
        return {"checked": 0, "results": [], "summary": "无可验证持仓"}

    ensure_data_dir()
    results = []

    for h in verifiable:
        code = h["code"]
        name = h["name"]
        index_code = h["_verify_code"]

        logger.info(f"基本面检查: {name} ({code}) → CSI {index_code}")
        check = check_fund(code, name, index_code)
        results.append(check)
        logger.info(f"  结论: {check['verdict']}")

    # 构建总结
    all_ok = all(r["ok"] for r in results)
    verdicts = [f"{r['fund_name']}: {r['verdict']}" for r in results]

    return {
        "checked": len(results),
        "results": results,
        "all_ok": all_ok,
        "verdicts": verdicts,
        "check_date": date.today().isoformat(),
    }


def format_fundamental_prompt(check_result: dict[str, Any]) -> str:
    """
    格式化为给DeepSeek的prompt片段。
    只给结论，不给原始数据。
    """
    if not check_result or check_result.get("checked", 0) == 0:
        return ""

    lines = ["## 月度基本面验证（代码自动检查）\n"]

    for r in check_result.get("results", []):
        lines.append(f"**{r['fund_name']}** `{r['fund_code']}` [CSI {r['index_code']}]")
        lines.append(f"> 结论: {r['verdict']}")
        if r.get("detail"):
            lines.append(f"> {r['detail']}")
        lines.append("")

    # 整体判断
    if check_result.get("all_ok"):
        lines.append("**三问法状态:** 全部通过。买入逻辑完整。")
    else:
        lines.append("**三问法状态:** 部分基金逻辑待验证或破裂。请按恶化警报规则判断是否需要操作。")

    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("基本面验证 — 独立测试")
    print("=" * 60)

    result = check_all_holdings()
    print()
    print(format_fundamental_prompt(result))
