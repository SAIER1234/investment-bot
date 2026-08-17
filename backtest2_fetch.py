"""
回测2数据抓取脚本
抓取: 18个中证行业指数PE+价格 | 31个申万一级行业价格 | QDII美股代理 | 黄金 | 中债10Y | 沪深300 PE
输出: data/backtest2/*.json
"""
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.common import disable_proxy

disable_proxy()

import akshare as ak
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("backtest2_fetch")

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "backtest2")
os.makedirs(OUT_DIR, exist_ok=True)

# 18个中证行业（有PE数据）
CSI_SECTORS = {
    '000932': '消费', '000933': '医药', '000922': '红利',
    '399998': '煤炭', '399967': '军工', '399971': '传媒',
    '930614': '钢铁', '930641': '中药', '930708': '有色',
    '930713': 'CS人工智', '931151': '光伏', '931719': 'CS电池',
    '931573': '港股互联', '930782': 'CS新能车', '931079': '5G通信',
    '930608': 'CS医药', '930612': 'CS消费', '931071': '人工智能',
}

# 31个申万一级行业（价格分位对照层，无PE）
SW_SECTORS = {
    '801010': '农林牧渔', '801030': '基础化工', '801040': '钢铁', '801050': '有色金属',
    '801080': '电子', '801110': '家用电器', '801120': '食品饮料', '801130': '纺织服饰',
    '801140': '轻工制造', '801150': '医药生物', '801160': '公用事业', '801170': '交通运输',
    '801180': '房地产', '801200': '商贸零售', '801210': '社会服务', '801230': '综合',
    '801710': '建筑材料', '801720': '建筑装饰', '801730': '电力设备', '801740': '国防军工',
    '801750': '计算机', '801760': '传媒', '801770': '通信', '801780': '银行',
    '801790': '非银金融', '801880': '汽车', '801890': '机械设备', '801950': '煤炭',
    '801960': '石油石化', '801970': '环保', '801980': '美容护理',
}

US_QDII = {
    '050025': '博时标普500A',   # 美股标普500代理 2012-06起
    '270042': '广发纳指100A',   # 纳指100代理 2012-08起
}


def save_json(name: str, data) -> None:
    path = os.path.join(OUT_DIR, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    logger.info(f"已保存 {name} ({len(data)}条)")


def fetch_csi_sectors() -> dict:
    """中证行业指数: 日期/收盘/滚动市盈率"""
    result = {}
    for code, name in CSI_SECTORS.items():
        for attempt in range(3):
            try:
                df = ak.stock_zh_index_hist_csindex(symbol=code, start_date='20050101', end_date='20300101')
                rows = []
                for _, r in df.iterrows():
                    pe = r.get('滚动市盈率')
                    rows.append({
                        'd': str(r['日期'])[:10],
                        'c': float(r['收盘']),
                        'pe': round(float(pe), 4) if pe is not None and not pd.isna(pe) else None,
                    })
                result[code] = {'name': name, 'rows': rows}
                logger.info(f"CSI {name}({code}): {rows[0]['d']} → {rows[-1]['d']} 共{len(rows)}点")
                break
            except Exception as e:
                if attempt == 2:
                    logger.error(f"CSI {name}({code}) 抓取失败: {e}")
                time.sleep(2 + attempt * 2)
        time.sleep(0.3)
    return result


def fetch_sw_sectors() -> dict:
    """申万一级行业指数: 日期/收盘（价格分位对照层）"""
    result = {}
    for code, name in SW_SECTORS.items():
        for attempt in range(3):
            try:
                df = ak.index_hist_sw(symbol=code, period='day')
                rows = [{'d': str(r['日期'])[:10], 'c': float(r['收盘'])} for _, r in df.iterrows()]
                result[code] = {'name': name, 'rows': rows}
                logger.info(f"SW {name}({code}): {rows[0]['d']} → {rows[-1]['d']} 共{len(rows)}点")
                break
            except Exception as e:
                if attempt == 2:
                    logger.error(f"SW {name}({code}) 抓取失败: {e}")
                time.sleep(2 + attempt * 2)
        time.sleep(0.3)
    return result


def fetch_us_qdii() -> dict:
    """QDII基金净值做美股代理"""
    result = {}
    for code, name in US_QDII.items():
        for attempt in range(3):
            try:
                df = ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势')
                rows = [{'d': str(r['净值日期'])[:10], 'nav': float(r['单位净值'])} for _, r in df.iterrows()]
                result[code] = {'name': name, 'rows': rows}
                logger.info(f"QDII {name}({code}): {rows[0]['d']} → {rows[-1]['d']} 共{len(rows)}点")
                break
            except Exception as e:
                if attempt == 2:
                    logger.error(f"QDII {name}({code}) 抓取失败: {e}")
                time.sleep(2 + attempt * 2)
        time.sleep(0.3)
    return result


def fetch_gold() -> dict:
    """上金所Au99.99"""
    for attempt in range(3):
        try:
            df = ak.spot_hist_sge(symbol='Au99.99')
            rows = [{'d': str(r['date'])[:10], 'c': float(r['close'])} for _, r in df.iterrows()]
            logger.info(f"黄金: {rows[0]['d']} → {rows[-1]['d']} 共{len(rows)}点")
            return {'name': '黄金Au99.99', 'rows': rows}
        except Exception as e:
            if attempt == 2:
                logger.error(f"黄金抓取失败: {e}")
            time.sleep(2 + attempt * 2)
    return {'name': '黄金', 'rows': []}


def fetch_cn_10y() -> dict:
    """中国10Y国债收益率"""
    for attempt in range(3):
        try:
            df = ak.bond_zh_us_rate()
            rows = [{'d': str(r['日期'])[:10], 'y': float(r['中国国债收益率10年'])} for _, r in df.iterrows()
                    if not pd.isna(r['中国国债收益率10年'])]
            logger.info(f"中债10Y: {rows[0]['d']} → {rows[-1]['d']} 共{len(rows)}点")
            return {'name': '中国10Y国债', 'rows': rows}
        except Exception as e:
            if attempt == 2:
                logger.error(f"国债抓取失败: {e}")
            time.sleep(2 + attempt * 2)
    return {'name': '中国10Y国债', 'rows': []}


def fetch_csi300() -> dict:
    """沪深300 PE（全球轮动A股腿）"""
    for attempt in range(3):
        try:
            df = ak.stock_zh_index_hist_csindex(symbol='000300', start_date='20050101', end_date='20300101')
            rows = []
            for _, r in df.iterrows():
                pe = r.get('滚动市盈率')
                if pe is not None and not pd.isna(pe):
                    rows.append({'d': str(r['日期'])[:10], 'c': float(r['收盘']), 'pe': round(float(pe), 4)})
            logger.info(f"沪深300: {rows[0]['d']} → {rows[-1]['d']} 共{len(rows)}点")
            return {'name': '沪深300', 'rows': rows}
        except Exception as e:
            if attempt == 2:
                logger.error(f"沪深300抓取失败: {e}")
            time.sleep(2 + attempt * 2)
    return {'name': '沪深300', 'rows': []}


if __name__ == "__main__":
    logger.info("=== 开始抓取回测2数据 ===")
    t0 = time.time()

    csi = fetch_csi_sectors()
    save_json('csi_sectors.json', csi)

    sw = fetch_sw_sectors()
    save_json('sw_sectors.json', sw)

    us = fetch_us_qdii()
    save_json('us_qdii.json', us)

    gold = fetch_gold()
    save_json('gold.json', gold)

    cn10 = fetch_cn_10y()
    save_json('cn_10y.json', cn10)

    csi300 = fetch_csi300()
    save_json('csi300.json', csi300)

    logger.info(f"=== 全部完成，耗时{(time.time()-t0)/60:.1f}分钟 ===")
