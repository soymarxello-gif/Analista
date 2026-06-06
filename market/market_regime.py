\
from __future__ import annotations

from data.price_client import download_daily_prices
from indicators.pipeline import add_all_indicators


def classify_market_regime(config: dict) -> dict:
    b = config.get("benchmarks", {})
    symbols = [b.get("broad_market", "SPY"), b.get("growth_market", "QQQ"), b.get("small_caps", "IWM"),
               b.get("volatility", "^VIX"), b.get("us10y", "^TNX"), b.get("dollar", "DX-Y.NYB")]
    prices = download_daily_prices([s for s in symbols if s], period="1y", interval="1d")
    diagnostics = {}
    score = 0

    def latest(symbol):
        df = prices.get(symbol)
        if df is None or df.empty or len(df) < 200:
            return None
        return add_all_indicators(df, config)

    spy = latest(b.get("broad_market", "SPY"))
    qqq = latest(b.get("growth_market", "QQQ"))
    iwm = latest(b.get("small_caps", "IWM"))
    vix_df = prices.get(b.get("volatility", "^VIX"))

    if spy is not None:
        row = spy.iloc[-1]
        c = row["close"]
        spy_ma50 = c > row.get("sma50", c)
        spy_ma200 = c > row.get("sma200", c)
        score += int(spy_ma50) + int(spy_ma200)
        diagnostics["spy_above_ma50"] = bool(spy_ma50)
        diagnostics["spy_above_ma200"] = bool(spy_ma200)

    if qqq is not None:
        row = qqq.iloc[-1]
        cond = row["close"] > row.get("sma50", row["close"])
        score += int(cond)
        diagnostics["qqq_above_ma50"] = bool(cond)

    if iwm is not None:
        row = iwm.iloc[-1]
        cond = row["close"] > row.get("sma50", row["close"])
        score += int(cond)
        diagnostics["iwm_above_ma50"] = bool(cond)

    if vix_df is not None and not vix_df.empty:
        vix = float(vix_df["close"].iloc[-1])
        high = config.get("market_regime", {}).get("vix", {}).get("high_risk_above", 25)
        low = config.get("market_regime", {}).get("vix", {}).get("low_risk_below", 16)
        score += 1 if vix < high else 0
        if vix < low:
            score += 1
        diagnostics["vix"] = vix

    # Placeholder for US10Y/DXY non-spiking checks.
    score += 1
    diagnostics["rates_dollar_placeholder"] = True

    cfg = config.get("market_regime", {})
    if score >= cfg.get("risk_on", {}).get("min_score", 6):
        regime = "risk_on"
        min_candidate_score = cfg.get("risk_on", {}).get("min_candidate_score", 75)
        block = False
    elif score >= cfg.get("neutral", {}).get("min_score", 4):
        regime = "neutral"
        min_candidate_score = cfg.get("neutral", {}).get("min_candidate_score", 82)
        block = False
    else:
        regime = "risk_off"
        min_candidate_score = cfg.get("risk_off", {}).get("min_candidate_score", 90)
        block = cfg.get("risk_off", {}).get("block_new_longs", True)

    return {
        "regime": regime,
        "regime_score": score,
        "regime_score_norm": min(score / 7, 1.0),
        "min_candidate_score": min_candidate_score,
        "block_new_longs": block,
        "diagnostics": diagnostics,
    }
