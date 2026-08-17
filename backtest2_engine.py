"""
回测2引擎 — 真实策略的最大诚实近似
=====================================
数据层:
  - 中证18行业 PE+价格 (2011-2026, 真实PE)
  - 申万31行业 价格   (1999-2026, 价格分位对照层, 无PE)
  - QDII净值做美股代理 (2012-2026, 含人民币汇率噪声)
  - 002910真实净值做核心仓 (2017起, 之前用沪深300衔接)
  - 沪深300 PE (A股季节+全球轮动A股腿)

策略层(与真实策略逐项对应):
  买入S1: PE分位<30% + 隐含利润增速>50%
  买入A1: PE分位<40% + 隐含利润增速>30%
  卖出R1(严格): 利润增速 < PE分位涨幅 → 卖; 或利润增速<-10%兜底
  卖出R2(门槛): PE分位>50%后才启用R1判断
  卖出R3(旧代理): PE分位>80%卖
  全球轮动: S2(A股>65%+美股<35%→转美股), S3(三市全贵→锁死新买入,不强制卖)

利润反推(核心代理):
  隐含盈利 E = 价格 / PE_TTM
  隐含利润增速 = E(t)/E(t-250交易日) - 1
  缺陷: TTM平滑使增速滞后约半年、幅度打折 → 双向偏保守(漏信号+延迟卖)

M2资金模型(真实双向车道):
  core仓25%起步(002910真实净值波动) + 机会仓(卖出后资金回core滚收益)
  对照: 保守版(机会仓闲置现金0收益)

执行规则(防止高估):
  - 信号T日收盘后计算, T+1日收盘成交
  - 成本: 买0.15% + 卖0.5% + 管理费年化1.0%(按日计提)
  - 期末强平未平仓持仓计入交易
  - 无未来函数: 所有指标只用T日及之前数据
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data", "backtest2")

# ── 策略参数 ──
S1_PE_MAX = 30.0
S1_PROFIT_MIN = 50.0
A1_PE_MAX = 40.0
A1_PROFIT_MIN = 30.0
SELL_R1_PROFIT_FLOOR = -10.0
SELL_R2_PE_GATE = 50.0
SELL_R3_PE_MAX = 80.0
BUY_COST = 0.0015
SELL_COST = 0.005
MGMT_FEE = 0.010
CORE_RATIO = 0.25
SAT_MAX_POSITIONS = 3
PROFIT_WINDOW = 250
PE_PCT_MIN_SAMPLES = 200

# 全球轮动参数
S2_A_MIN = 65.0
S2_US_MAX = 35.0
S2_EXIT_A = 50.0
S2_EXIT_US = 70.0
S3_A = 80.0
S3_SPY = 80.0
S3_QQQ = 70.0
US_PCT_WINDOW = 2500


def load_json(name: str) -> dict:
    with open(os.path.join(DATA_DIR, name), encoding='utf-8') as f:
        return json.load(f)


def build_frame(csi_sectors: dict) -> dict:
    """构建面板: {code: df(datetime索引, close/pe/name)}"""
    frames = {}
    for code, info in csi_sectors.items():
        df = pd.DataFrame(info['rows'])
        df['d'] = pd.to_datetime(df['d'])
        df = df.set_index('d').sort_index()
        df = df.rename(columns={'c': 'close', 'pe': 'pe'})
        df['name'] = info['name']
        frames[code] = df
    return frames


def add_indicators(frames: dict) -> dict:
    """pe_pct(expanding分位) + 隐含盈利 + profit_yoy(250交易日同比)。无未来函数。"""
    out = {}
    for code, df in frames.items():
        df = df.copy()
        # 关键: 分位只在有效PE上计算。若含NaN, NaN会稀释分母把分位系统性压低
        pe_valid = df['pe'].dropna()
        pct = pe_valid.expanding(min_periods=PE_PCT_MIN_SAMPLES).apply(
            lambda s: (s[:-1] < s[-1]).mean() * 100, raw=True)
        df['pe_pct'] = pct  # 索引对齐, 无效PE日为NaN
        df['implied'] = df['close'] / df['pe']
        df['profit_yoy'] = df['implied'] / df['implied'].shift(PROFIT_WINDOW) * 100 - 100
        out[code] = df
    return out


def compute_sw_pct(sw_sectors: dict) -> dict:
    """申万对照层: 价格分位(10年滚动)作为PE分位代理"""
    out = {}
    for code, info in sw_sectors.items():
        df = pd.DataFrame(info['rows'])
        df['d'] = pd.to_datetime(df['d'])
        df = df.set_index('d').sort_index()
        close = df['c']
        pct = close.rolling(US_PCT_WINDOW, min_periods=500).apply(
            lambda s: (s[:-1] < s[-1]).mean() * 100, raw=True)
        out[code] = pd.DataFrame({'close': close, 'pe_pct_proxy': pct, 'name': info['name']})
    return out


def build_core_returns() -> pd.Series:
    """
    核心仓日收益序列: 002910真实净值(2017-01-25起), 之前用沪深300衔接。
    返回以主日历为索引的日收益Series(无数据日=0)。
    """
    raw = load_json('core_fund.json')
    core = pd.DataFrame(raw['rows'])
    core['d'] = pd.to_datetime(core['d'])
    core = core.set_index('d').sort_index()['nav']
    ret = core.pct_change().fillna(0.0)

    csi300_raw = load_json('csi300.json')
    c300 = pd.DataFrame(csi300_raw['rows'])
    c300['d'] = pd.to_datetime(c300['d'])
    c300 = c300.set_index('d').sort_index().rename(columns={'c': 'close'})['close']
    pre_ret = c300.pct_change().fillna(0.0)
    # 2017-01-25之前的日期用沪深300
    switch = core.index[0]
    combined = pd.concat([pre_ret[pre_ret.index < switch], ret])
    return combined


class Simulator:
    """
    M1: 满仓单标的滚动
    M2: 核心25%(真实净值波动) + 机会仓(最多3仓)
        sat_to_core=True: 机会仓卖出后资金回核心滚收益(双向车道)
        sat_to_core=False: 闲置现金0收益(保守对照)
    均支持全球轮动开关。
    """

    def __init__(self, panel: dict, csi300: pd.DataFrame, us_qdii: dict,
                 core_ret: pd.Series, global_rotation: bool, sell_rule: str,
                 model: str, sat_to_core: bool = True):
        self.panel = panel
        self.csi300 = csi300
        self.us_qdii = us_qdii
        self.core_ret = core_ret
        self.gr = global_rotation
        self.sell_rule = sell_rule
        self.model = model
        self.sat_to_core = sat_to_core
        self.trades = []
        self.nav_series = []

    # ── 信号 ──
    def buy_signal(self, code: str, d: pd.Timestamp) -> bool:
        df = self.panel[code]
        if d not in df.index:
            return False
        row = df.loc[d]
        pct, yoy = row['pe_pct'], row['profit_yoy']
        if pd.isna(pct) or pd.isna(yoy):
            return False
        return (pct < S1_PE_MAX and yoy > S1_PROFIT_MIN) or (pct < A1_PE_MAX and yoy > A1_PROFIT_MIN)

    def sell_signal(self, code: str, d: pd.Timestamp, buy_pe_pct: float) -> bool:
        df = self.panel[code]
        if d not in df.index:
            return False
        row = df.loc[d]
        pct, yoy = row['pe_pct'], row['profit_yoy']
        if pd.isna(pct) or pd.isna(yoy):
            return False
        if self.sell_rule == 'R1':
            return (yoy < pct - buy_pe_pct) or (yoy < SELL_R1_PROFIT_FLOOR)
        elif self.sell_rule == 'R2':
            return ((pct > SELL_R2_PE_GATE and yoy < pct - buy_pe_pct)) or (yoy < SELL_R1_PROFIT_FLOOR)
        elif self.sell_rule == 'R3':
            return pct > SELL_R3_PE_MAX
        raise ValueError(self.sell_rule)

    def close_price(self, code: str, d: pd.Timestamp) -> float:
        """<=d最近可得收盘价（新指数在部分日期无数据）"""
        sub = self.panel[code].loc[:d, 'close']
        return float(sub.iloc[-1])

    def core_daily_ret(self, d: pd.Timestamp) -> float:
        sub = self.core_ret.loc[:d]
        return 0.0 if sub.empty else float(sub.iloc[-1])

    # ── 全球轮动 ──
    def s2_triggered(self, d: pd.Timestamp) -> bool:
        if not self.gr:
            return False
        a = self.csi300_pe_pct_at(d)
        us = self.us_price_pct_at(d)
        if a is None or us is None:
            return False
        return a > S2_A_MIN and us < S2_US_MAX

    def s3_triggered(self, d: pd.Timestamp) -> bool:
        if not self.gr:
            return False
        a = self.csi300_pe_pct_at(d)
        spy = self.us_price_pct_at(d, '050025')
        qqq = self.us_price_pct_at(d, '270042')
        if a is None or spy is None or qqq is None:
            return False
        return a > S3_A and spy > S3_SPY and qqq > S3_QQQ

    def csi300_pe_pct_at(self, d: pd.Timestamp):
        sub = self.csi300.loc[:d, 'pe_pct']
        return None if sub.empty or pd.isna(sub.iloc[-1]) else float(sub.iloc[-1])

    def us_price_pct_at(self, d: pd.Timestamp, code: str = '050025'):
        sub = self.us_qdii[code].loc[:d, 'price_pct']
        return None if sub.empty or pd.isna(sub.iloc[-1]) else float(sub.iloc[-1])

    def _record_trade(self, code: str, d: pd.Timestamp, buy_price: float, buy_date: pd.Timestamp,
                      net: float, cost_basis: float, reason: str):
        ret = (net / cost_basis - 1) * 100 if cost_basis > 0 else 0.0
        self.trades.append({'code': code, 'name': str(self.panel[code].iloc[0]['name']),
                            'buy': str(buy_date.date()), 'sell': str(d.date()),
                            'reason': reason, 'ret': round(ret, 2)})

    # ── 主循环 ──
    def run(self) -> dict:
        if self.model == 'M1':
            self._run_m1()
        else:
            self._run_m2()
        nav = pd.Series({d: v for d, v in self.nav_series})
        return self._summary(nav)

    def _run_m1(self):
        """满仓单标的: 现金1.0起步。期末强平。"""
        cash = 1.0
        holding = None
        dates = [d for d in sorted({d for df in self.panel.values() for d in df.index})
                 if d >= pd.Timestamp('2011-06-28')]
        for i, d in enumerate(dates):
            if i == 0:
                self.nav_series.append((d, 1.0))
                continue
            d_prev = dates[i - 1]
            if holding:
                if self.sell_signal(holding['code'], d_prev, holding['buy_pe_pct']):
                    px = self.close_price(holding['code'], d)
                    hold_days = max((d - holding['buy_date']).days, 1)
                    gross = cash * (px / holding['buy_price'])
                    net = gross * (1 - SELL_COST) - gross * MGMT_FEE * hold_days / 365
                    self._record_trade(holding['code'], d, holding['buy_price'], holding['buy_date'],
                                       net, cash, f'卖出{self.sell_rule}')
                    cash = net
                    holding = None
            if not holding and not (self.gr and self.s3_triggered(d_prev)):
                candidates = [c for c in self.panel if self.buy_signal(c, d_prev)]
                if candidates:
                    best = min(candidates, key=lambda c: self.panel[c].loc[d_prev, 'pe_pct'])
                    px = self.close_price(best, d)
                    cash = cash * (1 - BUY_COST)
                    holding = {'code': best, 'buy_price': px, 'buy_date': d,
                               'buy_pe_pct': float(self.panel[best].loc[d_prev, 'pe_pct'])}
            nav = cash * (self.close_price(holding['code'], d) / holding['buy_price']) if holding else cash
            self.nav_series.append((d, nav))
        # 期末强平
        if holding:
            d = dates[-1]
            px = self.close_price(holding['code'], d)
            hold_days = max((d - holding['buy_date']).days, 1)
            gross = cash * (px / holding['buy_price'])
            net = gross * (1 - SELL_COST) - gross * MGMT_FEE * hold_days / 365
            self._record_trade(holding['code'], d, holding['buy_price'], holding['buy_date'],
                               net, cash, '期末强平')
            self.nav_series[-1] = (d, net)

    def _run_m2(self):
        """
        核心25%起步(真实净值波动) + 机会仓。
        sat_to_core=True: 卖出回核心滚收益; False: 现金0收益。
        """
        core = CORE_RATIO
        sat_cash = 1.0 - CORE_RATIO
        positions = {}
        dates = [d for d in sorted({d for df in self.panel.values() for d in df.index})
                 if d >= pd.Timestamp('2011-06-28')]
        for i, d in enumerate(dates):
            if i == 0:
                self.nav_series.append((d, 1.0))
                continue
            d_prev = dates[i - 1]
            r_core = self.core_daily_ret(d)
            core *= (1 + r_core)
            if self.sat_to_core:
                sat_cash *= (1 + r_core)
            # 卖出检查
            for code in list(positions):
                p = positions[code]
                if self.sell_signal(code, d_prev, p['buy_pe_pct']):
                    px = self.close_price(code, d)
                    hold_days = max((d - p['buy_date']).days, 1)
                    gross = p['shares'] * px
                    net = gross * (1 - SELL_COST) - gross * MGMT_FEE * hold_days / 365
                    self._record_trade(code, d, p['buy_price'], p['buy_date'], net,
                                       p['shares'] * p['buy_price'], f'卖出{self.sell_rule}')
                    sat_cash += net
                    del positions[code]
            # 买入: 有空位+信号+S3未锁死
            if len(positions) < SAT_MAX_POSITIONS and not (self.gr and self.s3_triggered(d_prev)):
                candidates = [c for c in self.panel if c not in positions and self.buy_signal(c, d_prev)]
                if candidates:
                    best = min(candidates, key=lambda c: self.panel[c].loc[d_prev, 'pe_pct'])
                    alloc = min(sat_cash * (1.0 / SAT_MAX_POSITIONS), sat_cash)
                    if alloc > 0.001:
                        px = self.close_price(best, d)
                        positions[best] = {'shares': alloc * (1 - BUY_COST) / px, 'buy_price': px,
                                           'buy_date': d,
                                           'buy_pe_pct': float(self.panel[best].loc[d_prev, 'pe_pct'])}
                        sat_cash -= alloc
            nav = core + sat_cash + sum(p['shares'] * self.close_price(c, d) for c, p in positions.items())
            self.nav_series.append((d, nav))
        # 期末强平所有仓位
        if positions:
            d = dates[-1]
            for code, p in list(positions.items()):
                px = self.close_price(code, d)
                hold_days = max((d - p['buy_date']).days, 1)
                gross = p['shares'] * px
                net = gross * (1 - SELL_COST) - gross * MGMT_FEE * hold_days / 365
                self._record_trade(code, d, p['buy_price'], p['buy_date'], net,
                                   p['shares'] * p['buy_price'], '期末强平')
                sat_cash += net
            self.nav_series[-1] = (d, core + sat_cash)

    def _summary(self, nav: pd.Series) -> dict:
        total_ret = (nav.iloc[-1] - 1.0) * 100
        years = (nav.index[-1] - nav.index[0]).days / 365.25
        annual = ((nav.iloc[-1]) ** (1 / years) - 1) * 100
        dd = (nav / nav.cummax() - 1).min() * 100
        wins = [t for t in self.trades if t['ret'] > 0]
        return {
            'model': self.model, 'sell_rule': self.sell_rule, 'global_rotation': self.gr,
            'sat_to_core': self.sat_to_core if self.model == 'M2' else None,
            'total_return_pct': round(total_ret, 2), 'annual_pct': round(annual, 2),
            'max_drawdown_pct': round(float(dd), 2), 'n_trades': len(self.trades),
            'win_rate': round(len(wins) / len(self.trades) * 100, 1) if self.trades else None,
            'avg_ret': round(float(np.mean([t['ret'] for t in self.trades])), 2) if self.trades else None,
            'years': round(years, 2), 'start': str(nav.index[0].date()), 'end': str(nav.index[-1].date()),
        }


def build_csi300():
    """沪深300: PE分位+价格"""
    raw = load_json('csi300.json')
    df = pd.DataFrame(raw['rows'])
    df['d'] = pd.to_datetime(df['d'])
    df = df.set_index('d').sort_index()
    df = df.rename(columns={'c': 'close'})
    df['pe_pct'] = df['pe'].expanding(min_periods=PE_PCT_MIN_SAMPLES).apply(
        lambda s: (s[:-1] < s[-1]).mean() * 100, raw=True)
    return df


def build_us_qdii():
    """美股代理: 价格分位(10年滚动)"""
    raw = load_json('us_qdii.json')
    out = {}
    for code, info in raw.items():
        df = pd.DataFrame(info['rows'])
        df['d'] = pd.to_datetime(df['d'])
        df = df.set_index('d').sort_index()
        df['price_pct'] = df['nav'].rolling(US_PCT_WINDOW, min_periods=500).apply(
            lambda s: (s[:-1] < s[-1]).mean() * 100, raw=True)
        out[code] = df
    return out


def run_all_scenarios() -> dict:
    csi = load_json('csi_sectors.json')
    panel = add_indicators(build_frame(csi))
    csi300 = build_csi300()
    us = build_us_qdii()
    core_ret = build_core_returns()
    results = []
    scenarios = []
    for model in ['M1', 'M2']:
        for rule in ['R1', 'R2', 'R3']:
            scenarios.append((model, rule, False, True))
            scenarios.append((model, rule, True, True))
    # M2保守现金版对照(仅R1)
    scenarios.append(('M2', 'R1', False, False))
    for model, rule, gr, sat_to_core in scenarios:
        sim = Simulator(panel, csi300, us, core_ret, global_rotation=gr,
                        sell_rule=rule, model=model, sat_to_core=sat_to_core)
        r = sim.run()
        r['trades'] = sim.trades
        results.append(r)
        print(f"{model} {rule} gr={gr} sat2core={sat_to_core}: 年化{r['annual_pct']}% "
              f"回撤{r['max_drawdown_pct']}% 交易{r['n_trades']}笔 胜率{r['win_rate']}%")
    return results


def _last_valid_close(panel: dict, code: str, d: pd.Timestamp) -> float:
    """<=d最后一个>0的收盘价"""
    sub = panel[code].loc[:d, 'close']
    pos = sub[sub > 0]
    return float(pos.iloc[-1]) if len(pos) else 0.0


def run_sw_layer(core_ret: pd.Series) -> dict:
    """申万对照层: 26.6年价格分位, 纯估值轮动(PE分位代理<30%买, >80%卖), M1/M2"""
    sw = load_json('sw_sectors.json')
    panel = compute_sw_pct(sw)
    results = []
    for model in ['M1', 'M2']:
        dates = sorted({d for df in panel.values() for d in df.index})
        cash = 1.0
        core = 0.25
        sat_cash = 0.75
        positions = {}
        trades = []
        navs = []
        for i, d in enumerate(dates):
            if i == 0:
                navs.append((d, 1.0))
                continue
            d_prev = dates[i - 1]
            if model == 'M2':
                sub = core_ret.loc[:d]
                r = float(sub.iloc[-1]) if len(sub) else 0.0
                core *= (1 + r)
                sat_cash *= (1 + r)
            for code in list(positions):
                p = positions[code]
                if d_prev in panel[code].index:
                    pct = panel[code].loc[d_prev, 'pe_pct_proxy']
                else:
                    pct = np.nan
                if not pd.isna(pct) and pct > SELL_R3_PE_MAX:
                    px = _last_valid_close(panel, code, d)
                    if px <= 0:
                        continue
                    hold_days = max((d - p['buy_date']).days, 1)
                    gross = p['shares'] * px
                    net = gross * (1 - SELL_COST) - gross * MGMT_FEE * hold_days / 365
                    cost_basis = p['shares'] * p['buy_price']
                    ret = (net / cost_basis - 1) * 100 if cost_basis > 0 else 0
                    trades.append({'code': code, 'name': str(panel[code].iloc[0]['name']),
                                   'buy': str(p['buy_date'].date()), 'sell': str(d.date()),
                                   'reason': '卖出R3', 'ret': round(ret, 2)})
                    if model == 'M1':
                        cash += net
                    else:
                        sat_cash += net
                    del positions[code]
            # 买入: 分位<30 (对照层无利润过滤)
            def _candidates():
                out = []
                for c in panel:
                    if c in positions or d_prev not in panel[c].index:
                        continue
                    pct = panel[c].loc[d_prev, 'pe_pct_proxy']
                    if not pd.isna(pct) and pct < S1_PE_MAX:
                        out.append((c, pct))
                return out
            if model == 'M1':
                if not positions:
                    cands = _candidates()
                    if cands:
                        best, _ = min(cands, key=lambda x: x[1])
                        px = _last_valid_close(panel, best, d)
                        if px > 0:
                            cash = cash * (1 - BUY_COST)
                            positions = {best: {'shares': cash / px, 'buy_price': px, 'buy_date': d}}
                            cash = 0.0
            else:
                if len(positions) < SAT_MAX_POSITIONS:
                    cands = _candidates()
                    if cands:
                        best, _ = min(cands, key=lambda x: x[1])
                        px = _last_valid_close(panel, best, d)
                        if px > 0:
                            alloc = min(sat_cash * (1.0 / SAT_MAX_POSITIONS), sat_cash)
                            positions[best] = {'shares': alloc * (1 - BUY_COST) / px,
                                               'buy_price': px, 'buy_date': d}
                            sat_cash -= alloc
            if model == 'M1':
                nav = cash + sum(p['shares'] * _last_valid_close(panel, c, d)
                                 for c, p in positions.items())
            else:
                nav = core + sat_cash + sum(p['shares'] * _last_valid_close(panel, c, d)
                                            for c, p in positions.items())
            navs.append((d, nav))
        # 期末强平
        if positions:
            d = dates[-1]
            for code, p in list(positions.items()):
                px = _last_valid_close(panel, code, d)
                if px <= 0:
                    continue
                gross = p['shares'] * px
                net = gross * (1 - SELL_COST)
                cost_basis = p['shares'] * p['buy_price']
                ret = (net / cost_basis - 1) * 100 if cost_basis > 0 else 0
                trades.append({'code': code, 'name': str(panel[code].iloc[0]['name']),
                               'buy': str(p['buy_date'].date()), 'sell': str(d.date()),
                               'reason': '期末强平', 'ret': round(ret, 2)})
                if model == 'M1':
                    cash += net
                else:
                    sat_cash += net
            if model == 'M2':
                navs[-1] = (d, core + sat_cash)
            else:
                navs[-1] = (d, cash)
        nav = pd.Series({d: v for d, v in navs})
        total = (nav.iloc[-1] - 1) * 100
        years = (nav.index[-1] - nav.index[0]).days / 365.25
        annual = (nav.iloc[-1] ** (1 / years) - 1) * 100
        dd = (nav / nav.cummax() - 1).min() * 100
        wins = [t for t in trades if t['ret'] > 0]
        results.append({
            'model': model, 'sell_rule': 'R3', 'global_rotation': False, 'layer': 'SW价格分位26年',
            'sat_to_core': None,
            'total_return_pct': round(total, 2), 'annual_pct': round(annual, 2),
            'max_drawdown_pct': round(float(dd), 2), 'n_trades': len(trades),
            'win_rate': round(len(wins) / len(trades) * 100, 1) if trades else None,
            'avg_ret': round(float(np.mean([t['ret'] for t in trades])), 2) if trades else None,
            'years': round(years, 2), 'start': str(nav.index[0].date()), 'end': str(nav.index[-1].date()),
            'trades': trades,
        })
        print(f"SW层 {model}: 年化{annual:.2f}% 回撤{dd:.2f}% 交易{len(trades)}笔")
    return results


def benchmark_csi300() -> dict:
    """基准: 沪深300 buy&hold (2011-06-28起, 与主力回测同窗)"""
    csi300 = build_csi300()
    c = csi300['close']
    start, end = c.index[0], c.index[-1]
    total = (c.iloc[-1] / c.iloc[0] - 1) * 100
    years = (end - start).days / 365.25
    annual = ((c.iloc[-1] / c.iloc[0]) ** (1 / years) - 1) * 100
    dd = (c / c.cummax() - 1).min() * 100
    return {'name': '沪深300 buy&hold(2011-2026)', 'total_return_pct': round(total, 2),
            'annual_pct': round(annual, 2), 'max_drawdown_pct': round(float(dd), 2),
            'years': round(years, 2), 'start': str(start.date()), 'end': str(end.date())}


def benchmark_core_fund() -> dict:
    """基准: 002910 buy&hold (2017-01-25起)"""
    raw = load_json('core_fund.json')
    df = pd.DataFrame(raw['rows'])
    df['d'] = pd.to_datetime(df['d'])
    df = df.set_index('d').sort_index()['nav']
    total = (df.iloc[-1] / df.iloc[0] - 1) * 100
    years = (df.index[-1] - df.index[0]).days / 365.25
    annual = ((df.iloc[-1] / df.iloc[0]) ** (1 / years) - 1) * 100
    dd = (df / df.cummax() - 1).min() * 100
    return {'name': '002910 buy&hold(2017-2026)', 'total_return_pct': round(total, 2),
            'annual_pct': round(annual, 2), 'max_drawdown_pct': round(float(dd), 2),
            'years': round(years, 2), 'start': str(df.index[0].date()), 'end': str(df.index[-1].date())}


if __name__ == '__main__':
    print('=== 基准 ===')
    b = benchmark_csi300()
    print(b)
    b2 = benchmark_core_fund()
    print(b2)
    print('\n=== 主力回测 (中证行业真PE, 2011-2026) ===')
    res = run_all_scenarios()
    with open(os.path.join(DATA_DIR, 'results_main.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f'已保存 results_main.json')
    print('\n=== 对照层 (申万价格分位, 1999-2026) ===')
    res_sw = run_sw_layer(build_core_returns())
    with open(os.path.join(DATA_DIR, 'results_sw.json'), 'w', encoding='utf-8') as f:
        json.dump(res_sw, f, ensure_ascii=False, indent=1, default=str)
    print(f'已保存 results_sw.json')
    with open(os.path.join(DATA_DIR, 'benchmark.json'), 'w', encoding='utf-8') as f:
        json.dump({'csi300': b, 'core_fund': b2}, f, ensure_ascii=False, indent=1, default=str)
    print('全部完成')
