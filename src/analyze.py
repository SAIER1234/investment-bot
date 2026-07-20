"""
AI 分析模块
将抓取到的数据组装成 prompt，调用 DeepSeek API 生成投资建议。
"""

import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT_DIR, "config")


def load_system_prompt() -> str:
    """加载系统提示词"""
    path = os.path.join(CONFIG_DIR, "system_prompt.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # 跳过 markdown 标题和 frontmatter
        # 找到第一个 # 标题后开始
        lines = content.split("\n")
        start = 0
        for i, line in enumerate(lines):
            if line.startswith("# "):
                start = i
                break
        return "\n".join(lines[start:])
    return "你是一个激进风格的基金投资顾问，为一位中国学生投资者服务。"


def build_report_prompt(data: dict[str, Any]) -> str:
    """将抓取到的数据组装成给 AI 分析的 prompt"""
    portfolio = data.get("portfolio", {})
    holdings = portfolio.get("holdings", [])
    watchlist = portfolio.get("watchlist", [])
    etf_data = data.get("etf_data", {})
    otc_data = data.get("otc_data", {})
    etf_perf = data.get("etf_performance", {})
    market = data.get("market_overview", {})
    smcd = data.get("semiconductor", {})
    heavy = data.get("heavy_holdings", [])

    prompt_parts = ["以下是今日收盘后的基金和市场数据，请基于此给出投资分析和操作建议。\n"]

    # ── 大盘 ──
    prompt_parts.append("## 今日大盘")
    for name, info in market.items():
        chg = info.get("change_pct")
        chg_str = f"{chg:+.2f}%" if chg is not None else "N/A"
        prompt_parts.append(f"- {name}: {info.get('price')}  ({chg_str})")

    # ── 半导体板块 ──
    prompt_parts.append(f"\n## 半导体板块\n- {smcd.get('name', '')}: "
                        f"收盘 {smcd.get('close')}, 涨跌幅 {smcd.get('change_pct')}%")

    # ── 持仓基金 ──
    prompt_parts.append("\n## 持仓基金")
    for h in holdings:
        code = h["code"]
        name = h["name"]
        amount = h["amount"]
        planned = h.get("planned", False)
        tag = " [计划买入，尚未建仓]" if planned else ""
        prompt_parts.append(f"\n### {name} ({code}){tag}")
        prompt_parts.append(f"- 投入金额: {amount}元")
        prompt_parts.append(f"- 类型: {h.get('type', '')}")

        if code in etf_data:
            e = etf_data[code]
            prompt_parts.append(f"- 最新价: {e.get('price')}")
            prompt_parts.append(f"- 今日涨跌幅: {e.get('change_pct', 0):+.2f}%")
            disc = e.get("discount_pct", 0) or 0
            prompt_parts.append(f"- 折溢价率: {disc:+.2f}%")
            nav = e.get("nav")
            if nav:
                prompt_parts.append(f"- IOPV/净值: {nav}")
            # 近期表现
            perf = etf_perf.get(code, {})
            if perf:
                prompt_parts.append(
                    f"- 近一周: {_pct_str(perf.get('w1'))}  "
                    f"近一月: {_pct_str(perf.get('m1'))}  "
                    f"近三月: {_pct_str(perf.get('m3'))}  "
                    f"今年以来: {_pct_str(perf.get('ytd'))}"
                )
        elif code in otc_data:
            o = otc_data[code]
            if o:
                nav_date = str(o.get("date", ""))
                today_str = data.get("timestamp", "")[:10]
                stale_warning = ""
                if nav_date and nav_date != today_str:
                    stale_warning = f" ⚠️ 非今日数据！最新可用净值为 {nav_date} 公布"
                prompt_parts.append(f"- 最新净值: {o.get('nav')}  (日期: {nav_date}){stale_warning}")
                prompt_parts.append(f"- 日增长率: {o.get('daily_change', 0):+.2f}%" if o.get('daily_change') is not None else "- 日增长率: N/A")
            else:
                prompt_parts.append("- 今日净值尚未公布或抓取失败")

    # ── 关注标的 ──
    if watchlist:
        prompt_parts.append("\n## 关注列表（仅供参考）")
        for w in watchlist:
            code = w["code"]
            name = w["name"]
            prompt_parts.append(f"\n### {name} ({code})")
            prompt_parts.append(f"- 关注理由: {w.get('reason', '')}")
            if code in etf_data:
                e = etf_data[code]
                prompt_parts.append(f"- 最新价: {e.get('price')}, 涨跌幅: {e.get('change_pct', 0):+.2f}%")

    # ── 重仓股 ──
    if heavy:
        prompt_parts.append("\n## 半导体设备核心重仓股今日表现")
        for stock in heavy:
            prompt_parts.append(
                f"- {stock['name']}({stock['code']}): "
                f"{stock.get('price')}  {stock.get('change_pct', 0):+.2f}%"
            )

    # ── 元信息 ──
    prompt_parts.append(f"\n---\n数据时间: {data.get('timestamp', '')}")
    prompt_parts.append(f"投资者画像: 学生, 总资金{portfolio.get('total_capital', 'N/A')}元, 风险偏好{portfolio.get('risk_profile', '')}")

    return "\n".join(prompt_parts)


def call_deepseek(system_prompt: str, user_prompt: str, api_key: str) -> str:
    """调用 DeepSeek API 生成投资建议"""
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=4096,
    )

    return response.choices[0].message.content or ""


def analyze(data: dict[str, Any], api_key: str | None = None) -> dict[str, str]:
    """
    主入口：组装 prompt → 调 DeepSeek → 返回分析结果。
    返回 {"report": "...", "error": "..."} 二选一。
    """
    if api_key is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")

    if not api_key:
        return {"error": "未设置 DEEPSEEK_API_KEY，请检查环境变量或 .env 文件"}

    try:
        system_prompt = load_system_prompt()
        user_prompt = build_report_prompt(data)

        logger.info("调用 DeepSeek API 生成投资建议...")
        report = call_deepseek(system_prompt, user_prompt, api_key)

        return {"report": report}
    except Exception as e:
        logger.error(f"DeepSeek API 调用失败: {e}")
        return {"error": str(e)}


def _pct_str(val: float | None) -> str:
    """格式化百分比"""
    if val is None:
        return "N/A"
    return f"{val:+.2f}%"


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
