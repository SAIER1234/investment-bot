"""
AI 分析模块
将抓取到的数据组装成结构化 prompt，调用 DeepSeek API 生成投资建议。
"""

import logging
import os
from typing import Any

from src.common import CONFIG_DIR
from src.llm import call_deepseek, DEFAULT_INVEST_TEMP, DEFAULT_INVEST_TOKENS

logger = logging.getLogger(__name__)


def load_system_prompt() -> str:
    """加载系统提示词"""
    path = os.path.join(CONFIG_DIR, "system_prompt.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # 跳过可能的 frontmatter 或注释行，从第一个 # 标题开始
        lines = content.split("\n")
        start = 0
        for i, line in enumerate(lines):
            if line.startswith("# "):
                start = i
                break
        return "\n".join(lines[start:])
    return "你是一个机会驱动型基金投资顾问，为中国学生投资者服务。"


def _pct_str(val: float | None) -> str:
    """格式化百分比"""
    if val is None:
        return "N/A"
    return f"{val:+.2f}%"


def _nav_stale_warning(fund_date: str, today: str) -> str:
    """检测净值是否过时，返回警告字符串"""
    if fund_date and fund_date != today:
        return f" ⚠️数据日期={fund_date}，非今日净值！分析时注意数据时滞"
    return ""


def build_report_prompt(data: dict[str, Any], scanner_data: dict[str, Any] | None = None) -> str:
    """
    将数据组装为结构化 prompt：
    估值仪表盘 → 持仓数据 → 市场情绪 → 基金雷达（如有）→ 要求AI按固定框架输出。
    """
    portfolio = data.get("portfolio", {})
    holdings = portfolio.get("holdings", [])
    otc_data = data.get("otc_data", {})
    otc_perf = data.get("otc_performance", {})
    otc_tech = data.get("otc_technical", {})
    index_val = data.get("index_valuations", {})
    turnover = data.get("market_turnover", {})
    northbound = data.get("northbound_flow", {})
    semi_flow = data.get("semiconductor_flow", {})
    market = data.get("market_overview", {})
    today = data.get("timestamp", "")[:10]

    lines = []

    # ── 市场环境 ──
    lines.append("## 市场环境\n")
    if market:
        lines.append("**主要指数:**")
        for name, m in market.items():
            lines.append(f"- {name}: {m.get('price')} ({_pct_str(m.get('change_pct'))})")
    if turnover:
        lines.append(f"\n**两市成交额:** {turnover.get('total_turnover_yi', 'N/A')}亿元")
    if northbound and "warning" not in northbound:
        net = northbound.get("net_flow_yi", 0) or 0
        lines.append(f"**北向资金:** {net:+.2f}亿元 (日期:{northbound.get('date','N/A')})")
    elif northbound and "warning" in northbound:
        lines.append(f"**北向资金:** 数据不可用")
    if semi_flow:
        lines.append(f"**半导体板块资金:** 主力净流入{semi_flow.get('main_net_inflow_yi', 0)}亿元 "
                     f"净占比{semi_flow.get('main_net_ratio', 0) or 0:+.2f}% "
                     f"涨跌{semi_flow.get('change_pct', 0) or 0:+.2f}%")

    lines.append("")

    # ── 每支基金详细数据 ──
    lines.append("## 持仓数据\n")
    for h in holdings:
        code = h["code"]
        name = h["name"]
        amount = h["amount"]
        planned = h.get("planned", False)
        tag = "【计划买入，尚未建仓】" if planned else ""

        lines.append(f"### {name} `{code}` {tag}")
        lines.append(f"- 投入金额: {amount}元 | 类型: 场外基金 | 总资金占比: {amount/50800*100:.0f}%")

        # 净值 + 今日盈亏
        nav_data = otc_data.get(code)
        if nav_data:
            stale = _nav_stale_warning(str(nav_data.get("date", "")), today)
            daily_chg = nav_data.get("daily_change") or 0
            daily_pnl = round(amount * daily_chg / 100, 0)
            lines.append(f"- 净值: {nav_data.get('nav')} (日期:{nav_data.get('date')}){stale}")
            lines.append(f"- 今日: {_pct_str(daily_chg)} | 盈亏: {daily_pnl:+.0f}元")
        else:
            lines.append("- 净值: 尚未公布")

        # 表现
        perf = otc_perf.get(code, {})
        if perf and any(v is not None for v in perf.values()):
            lines.append(f"- 表现: 周{_pct_str(perf.get('w1'))} | "
                         f"月{_pct_str(perf.get('m1'))} | "
                         f"季{_pct_str(perf.get('m3'))} | "
                         f"年{_pct_str(perf.get('ytd'))}")

        # 估值
        val = index_val.get(code)
        if val:
            pe = val.get("pe")
            pe_pct = val.get("pe_percentile")
            if pe and pe_pct is not None:
                pe_status = "低估" if pe_pct < 30 else ("合理" if pe_pct < 80 else "高估")
                lines.append(f"- 估值: PE={pe}倍 | PE分位={pe_pct}% | PB={val.get('pb')}倍 | 状态={pe_status}")
                lines.append(f"- 估值纪律: 当前分位→单次最多建议{30 if pe_pct<30 else (20 if pe_pct<50 else (10 if pe_pct<80 else 0))}%总资金")

        # 技术面
        tech = otc_tech.get(code, {})
        if tech and "error" not in tech:
            lines.append(f"- 技术: 净值={tech.get('latest_nav')} | "
                         f"vsMA20={_pct_str(tech.get('price_vs_ma20_pct'))} | "
                         f"vsMA60={_pct_str(tech.get('price_vs_ma60_pct'))} | "
                         f"RSI(14)={tech.get('rsi14')}")

        lines.append("")

    # ── 基金雷达（每周扫描结果） ──
    if scanner_data:
        from src.fund_scanner import format_scanner_prompt
        candidates = scanner_data.get("candidates", [])
        if candidates:
            scanner_prompt = format_scanner_prompt(candidates)
            lines.append(scanner_prompt)
            lines.append("")

    # ── 组合总盈亏 ──
    total_daily_pnl = 0.0
    for h in holdings:
        code = h["code"]
        nav_data = otc_data.get(code)
        if nav_data:
            chg = nav_data.get("daily_change") or 0
            total_daily_pnl += h["amount"] * chg / 100
    lines.append(f"**今日组合总盈亏: {total_daily_pnl:+.0f}元**")

    # ── 输出要求 ──
    lines.append("---")
    lines.append(f"数据时间: {data.get('timestamp', '')[:19]}")
    lines.append(f"投资者: 学生 | 总资金70800元 | 风格=机会驱动 | 全部场外基金")
    lines.append("")
    lines.append("**请严格按照系统提示词的格式输出报告。**")
    lines.append("对 planned=true 的标的，重点判断入场时机，给出具体净值区间和金额。")
    lines.append("估值分位>80%的标的，不要建议买入。")

    return "\n".join(lines)


def analyze(data: dict[str, Any], api_key: str | None = None,
            scanner_data: dict[str, Any] | None = None) -> dict[str, str]:
    """
    主入口：组装 prompt → 调 DeepSeek → 返回分析结果。
    返回 {"report": "...", "error": "..."} 二选一。
    """
    if api_key is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")

    if not api_key:
        return {"error": "未设置 DEEPSEEK_API_KEY，请检查环境变量"}

    try:
        system_prompt = load_system_prompt()
        user_prompt = build_report_prompt(data, scanner_data)

        logger.info("调用 DeepSeek API 生成投资建议...")
        report = call_deepseek(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=api_key,
            temperature=DEFAULT_INVEST_TEMP,
            max_tokens=DEFAULT_INVEST_TOKENS,
        )

        return {"report": report}
    except Exception as e:
        logger.error(f"DeepSeek API 调用失败: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    logging.basicConfig(level=logging.INFO)

    from src.fetch_data import fetch_all, save_cache

    print("抓取数据中...")
    data = fetch_all()
    save_cache(data)
    print("数据分析中...")
    result = analyze(data)
    if "error" in result:
        print(f"错误: {result['error']}")
    else:
        print(result["report"])
