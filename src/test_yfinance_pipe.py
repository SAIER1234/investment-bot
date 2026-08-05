"""
yfinance 数据管道探测脚本
验证美股指数PE分位 + 价格历史 + 实际利率在GitHub Actions上的可用性
本地中国IP会被Yahoo限流，GitHub Actions美国IP正常
"""
import sys
import json
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

# ── 探测 1: yfinance 导入 ──
print("=" * 60)
print("探测 1: yfinance 可用性")
print("=" * 60)
try:
    import yfinance as yf
    print(f"✅ yfinance 版本: {yf.__version__}")
except Exception as e:
    print(f"❌ yfinance 导入失败: {e}")
    sys.exit(1)


def probe_index(ticker: str, name: str) -> dict:
    """探测单个指数的数据可用性"""
    result = {"ticker": ticker, "name": name, "ok": False, "errors": []}

    t = yf.Ticker(ticker)

    # ── info 数据 ──
    try:
        info = t.info
        result["trailingPE"] = info.get("trailingPE")
        result["forwardPE"] = info.get("forwardPE")
        result["priceToBook"] = info.get("priceToBook")
        result["fiftyDayAverage"] = info.get("fiftyDayAverage")
        result["twoHundredDayAverage"] = info.get("twoHundredDayAverage")
        result["regularMarketPrice"] = info.get("regularMarketPrice") or info.get("previousClose")

        # 列出所有PE相关字段
        pe_keys = [k for k in info.keys() if "pe" in k.lower() or "ratio" in k.lower()]
        result["pe_related_keys"] = pe_keys

        if result["trailingPE"]:
            print(f"  trailingPE: {result['trailingPE']}")
        if result["forwardPE"]:
            print(f"  forwardPE: {result['forwardPE']}")
        if result["regularMarketPrice"]:
            print(f"  价格: {result['regularMarketPrice']}")
        print(f"  PE相关字段: {pe_keys}")
    except Exception as e:
        result["errors"].append(f"info: {e}")
        print(f"  ⚠️ info获取失败: {e}")

    # ── 价格历史 ──
    try:
        hist = t.history(period="10y")
        if not hist.empty:
            closes = hist["Close"]
            latest = float(closes.iloc[-1])
            result["price_latest"] = round(latest, 2)
            result["price_data_points"] = len(hist)
            result["price_history_start"] = str(hist.index[0].date())
            result["price_history_end"] = str(hist.index[-1].date())

            # 价格分位
            pct = round((closes < latest).sum() / len(closes) * 100, 1)
            result["price_percentile"] = pct

            # 均线
            ma200 = round(float(closes.iloc[-200:].mean()), 2) if len(closes) >= 200 else None
            result["ma200"] = ma200
            vs_ma200 = round((latest / ma200 - 1) * 100, 2) if ma200 else None
            result["vs_ma200_pct"] = vs_ma200

            print(f"  价格历史: {len(hist)}点, {hist.index[0].date()} → {hist.index[-1].date()}")
            print(f"  最新价: {latest}")
            print(f"  价格分位(10Y): {pct}%")
            print(f"  vs MA200: {vs_ma200}%")
        else:
            result["errors"].append("history: 返回空")
            print(f"  ⚠️ 价格历史为空")
    except Exception as e:
        result["errors"].append(f"history: {e}")
        print(f"  ⚠️ 价格历史获取失败: {e}")

    result["ok"] = result["trailingPE"] is not None and "price_data_points" in result
    return result


def probe_tips() -> dict:
    """探测实际利率数据 (TIPS ETF)"""
    result = {"ok": False}
    print()
    print("=" * 60)
    print("探测 3: 美国实际利率 (TIPS)")
    print("=" * 60)

    # 方法1: TIP ETF (iShares TIPS Bond ETF)
    try:
        tip = yf.Ticker("TIP")
        info = tip.info
        result["TIP_price"] = info.get("regularMarketPrice") or info.get("previousClose")
        result["TIP_yield"] = info.get("yield") or info.get("trailingAnnualDividendYield")
        print(f"  TIP价格: {result.get('TIP_price')}")
        print(f"  TIP收益率: {result.get('TIP_yield')}")
    except Exception as e:
        print(f"  ⚠️ TIP ETF: {e}")

    # 方法2: ^TNX (10Y Treasury Yield) 作为替代 — 实际利率 ≈ 名义利率 - 通胀预期
    try:
        tnx = yf.Ticker("^TNX")
        info = tnx.info
        result["TNX_price"] = info.get("regularMarketPrice") or info.get("previousClose")
        print(f"  10Y美债收益率(^TNX): {result.get('TNX_price')}%")
        # 实际利率 ≈ 名义 - 2%长期通胀目标
        if result.get("TNX_price"):
            result["real_yield_est"] = round(result["TNX_price"] - 2.0, 2)
            print(f"  实际利率估算(名义-2%): {result['real_yield_est']}%")
    except Exception as e:
        print(f"  ⚠️ ^TNX: {e}")

    result["ok"] = bool(result.get("TIP_price") or result.get("TNX_price"))
    return result


# ── 主探测 ──
if __name__ == "__main__":
    results = {
        "timestamp": datetime.now().isoformat(),
        "indices": [],
        "tips": {},
        "verdict": "",
    }

    # 探测标普500
    print()
    print("=" * 60)
    print("探测 2a: 标普500 (^GSPC)")
    print("=" * 60)
    sp500 = probe_index("^GSPC", "标普500")
    results["indices"].append(sp500)

    # SPY ETF作为备用
    print()
    print("=" * 60)
    print("探测 2b: SPY ETF (备用)")
    print("=" * 60)
    spy = probe_index("SPY", "标普500 ETF")
    results["indices"].append(spy)

    # 探测纳指100
    print()
    print("=" * 60)
    print("探测 2c: 纳指100 (^NDX)")
    print("=" * 60)
    ndx = probe_index("^NDX", "纳指100")
    results["indices"].append(ndx)

    # QQQ ETF作为备用
    print()
    print("=" * 60)
    print("探测 2d: QQQ ETF (备用)")
    print("=" * 60)
    qqq = probe_index("QQQ", "纳指100 ETF")
    results["indices"].append(qqq)

    # 探测实际利率
    results["tips"] = probe_tips()

    # ── 最终判定 ──
    print()
    print("=" * 60)
    print("探测总结")
    print("=" * 60)

    for r in results["indices"]:
        status = "✅" if r["ok"] else "❌"
        pe = r.get("trailingPE", "N/A")
        pct = r.get("price_percentile", "N/A")
        pts = r.get("price_data_points", 0)
        print(f"  {status} {r['name']} ({r['ticker']}): PE={pe}, 价格分位={pct}%, 历史{pts}点")

    tips_ok = results["tips"]["ok"]
    print(f"  {'✅' if tips_ok else '⚠️'} 实际利率: {'可用' if tips_ok else '部分可用'}")

    # 至少一个指数有PE + 一个有时价历史 → 管道可用
    pe_ok = any(r["trailingPE"] is not None for r in results["indices"])
    hist_ok = any(r.get("price_data_points", 0) > 1000 for r in results["indices"])

    if pe_ok and hist_ok:
        results["verdict"] = "✅ 管道可用"
        print(f"\n✅ 管道可用 — PE数据{'有' if pe_ok else '无'}，价格历史{'有' if hist_ok else '无'}")
    else:
        results["verdict"] = "⚠️ 管道部分可用，需调整方案"
        print(f"\n⚠️ 部分可用 — PE:{pe_ok}, 历史:{hist_ok}")

    # 保存结果供workflow读取
    output = {
        "timestamp": results["timestamp"],
        "verdict": results["verdict"],
        "sp500_pe": sp500.get("trailingPE"),
        "sp500_price_pct": sp500.get("price_percentile"),
        "sp500_ok": sp500["ok"],
        "ndx_pe": ndx.get("trailingPE"),
        "ndx_price_pct": ndx.get("price_percentile"),
        "ndx_ok": ndx["ok"],
        "spy_pe": spy.get("trailingPE"),
        "spy_ok": spy["ok"],
        "qqq_pe": qqq.get("trailingPE"),
        "qqq_ok": qqq["ok"],
        "real_yield_est": results["tips"].get("real_yield_est"),
    }

    with open("data/yfinance_probe_result.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到 data/yfinance_probe_result.json")
    print(json.dumps(output, ensure_ascii=False, indent=2))
