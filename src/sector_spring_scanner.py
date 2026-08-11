"""
全市场春扫模块 — 跨行业S1/A1/A2/A3信号检测
每周五扫描所有CSI行业指数的PE分位，标记春/夏/秋/冬，
对春行业调用三问法利润验证，生成S/A级信号。
"""
import logging
import os
from datetime import date
from typing import Any

from src.common import DATA_DIR, disable_proxy, ensure_data_dir, load_json, save_json

disable_proxy()
import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

# 16个CSI行业指数（与回测一致的代码）
CSI_SECTORS = {
    '000932': '中证消费', '000933': '中证医药',
    '399967': '中证军工', '399971': '中证传媒',
    '930608': 'CS医药', '930612': 'CS消费', '930641': '中证中药',
    '930708': '中证有色', '930713': 'CS人工智', '930782': 'CS新能车',
    '931071': '人工智能', '931079': '5G通信',
    '931151': '光伏产业', '931573': 'CS港股通互联网', '931719': 'CS电池',
}

CACHE_FILE = "spring_scan_cache.json"

# 三问法黑名单（行业在被监管打压/结构性衰退时跳过）
SECTOR_BLACKLIST = {'动漫游戏', '中证传媒'}


def _get_pe_percentile(code: str) -> dict[str, Any] | None:
    """获取单个CSI指数的PE分位和季节"""
    try:
        df = ak.stock_zh_index_hist_csindex(symbol=code, start_date='20050101', end_date='20300101')
        df = df.dropna(subset=['滚动市盈率'])
        if len(df) < 200:
            return None
        pe_s = df['滚动市盈率']
        latest = df.iloc[-1]
        cur_pe = round(float(latest['滚动市盈率']), 1)
        cur_pct = round((pe_s < cur_pe).sum() / len(pe_s) * 100, 1)
        season = '春' if cur_pct < 30 else ('夏' if cur_pct < 60 else ('秋' if cur_pct < 80 else '冬'))
        return {
            'pe': cur_pe, 'pe_pct': cur_pct, 'season': season,
            'date': str(latest['日期'])[:10],
            'years': (df.iloc[-1]['日期'] - df.iloc[0]['日期']).days / 365.25,
        }
    except Exception as e:
        logger.warning(f"CSI {code} PE获取失败: {e}")
        return None


def scan_all_sectors() -> dict[str, Any]:
    """主入口：扫描所有行业，标记春/夏/秋/冬，识别S/A级候选"""
    results = []
    spring_candidates = []   # PE<30%
    a_candidates = []        # PE<40%
    extreme_candidates = []  # PE<5%或>95%

    for code, name in CSI_SECTORS.items():
        if name in SECTOR_BLACKLIST:
            continue
        pe_data = _get_pe_percentile(code)
        if not pe_data:
            continue

        pct = pe_data['pe_pct']
        entry = {'code': code, 'name': name, **pe_data}

        if pct < 5:
            entry['extreme'] = 'undervalued'
            extreme_candidates.append(entry)
        elif pct > 95:
            entry['extreme'] = 'overvalued'
            extreme_candidates.append(entry)

        if pct < 30:
            spring_candidates.append(entry)
        elif pct < 40:
            a_candidates.append(entry)

        results.append(entry)

    return {
        'scan_date': date.today().isoformat(),
        'total_sectors': len(results),
        'spring_count': len(spring_candidates),
        'a_count': len(a_candidates),
        'extreme_count': len(extreme_candidates),
        'spring': spring_candidates,
        'a_level': a_candidates,
        'extreme': extreme_candidates,
        'all': results,
    }


def format_spring_scan_prompt(scan_result: dict[str, Any]) -> str:
    """格式化为给DeepSeek的prompt片段"""
    if not scan_result or scan_result.get('total_sectors', 0) == 0:
        return ""

    lines = ["## 全市场春扫（跨行业S/A级信号）\n"]
    lines.append(f"扫描{scan_result['total_sectors']}个行业，{scan_result['spring_count']}个在春天。\n")

    # 春季行业（PE<30%）— S级候选
    spring = scan_result.get('spring', [])
    if spring:
        lines.append("### 🌸 春季行业（PE<30%，S级候选）\n")
        for s in spring:
            emerging = "[新兴]" if s.get('years', 99) < 5 else ""
            lines.append(f"- **{s['name']}**{emerging}: PE={s['pe']} PE分位={s['pe_pct']}% ({s['season']})")
            if s.get('years', 99) < 5:
                lines.append(f"  - PE数据仅{s['years']:.1f}年，分位仅供参考。新兴规则PE<55%即可。")

    # A级候选（PE<40%）
    a_level = scan_result.get('a_level', [])
    if a_level:
        lines.append("\n### 🌱 A级候选（PE<40%）\n")
        for s in a_level[:5]:
            lines.append(f"- **{s['name']}**: PE={s['pe']} PE分位={s['pe_pct']}%")

    # 极端分位
    extreme = scan_result.get('extreme', [])
    if extreme:
        lines.append("\n### ⚡ 极端分位（A3候选）\n")
        for s in extreme:
            tag = "极低(可能反转)" if s.get('extreme') == 'undervalued' else "极高(可能反转)"
            lines.append(f"- **{s['name']}**: PE分位={s['pe_pct']}% {tag}")

    lines.append("")
    lines.append("**指令:** 春行业中三问法通过的→按S/A级信号格式大声报告。")
    lines.append("PE数据<5年的新兴行业→自动放宽至PE<55%门槛。")

    return "\n".join(lines)


def scan_if_needed(force: bool = False) -> dict[str, Any] | None:
    """每周五扫描，或force=True强制扫描"""
    ensure_data_dir()
    cache_path = os.path.join(DATA_DIR, CACHE_FILE)
    today = date.today()

    if not force and os.path.exists(cache_path):
        try:
            cache = load_json(cache_path)
            last_scan = cache.get('scan_date', '')[:10]
            if last_scan:
                days_since = (today - date.fromisoformat(last_scan)).days
                if days_since < 7:
                    logger.info(f"复用春扫缓存({days_since}天前)")
                    return cache
        except Exception:
            pass

    logger.info("执行全市场春扫...")
    result = scan_all_sectors()
    save_json(cache_path, result)
    logger.info(f"春扫完成: {result['spring_count']}春/{result['a_count']}A级/{result['extreme_count']}极端")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = scan_all_sectors()
    print(f"总行业: {r['total_sectors']}")
    print(f"春: {r['spring_count']} | A级: {r['a_count']} | 极端: {r['extreme_count']}")
    print(format_spring_scan_prompt(r))
