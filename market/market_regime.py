\
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from data.price_client import download_daily_prices
from indicators.pipeline import add_all_indicators


MACRO_DATA_FRESHNESS = "DELAYED_OR_EOD"
MACRO_SOURCE = "yfinance"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _latest_close(df: pd.DataFrame | None) -> float | None:
    if df is None or df.empty or "close" not in df.columns:
        return None

    close = df["close"].dropna()
    if close.empty:
        return None

    return _safe_float(close.iloc[-1])


def _change_value(df: pd.DataFrame | None, days: int) -> float | None:
    if df is None or df.empty or "close" not in df.columns:
        return None

    close = df["close"].dropna()
    if len(close) <= days:
        return None

    latest = _safe_float(close.iloc[-1])
    previous = _safe_float(close.iloc[-days - 1])
    if latest is None or previous is None:
        return None

    return latest - previous


def _change_pct(df: pd.DataFrame | None, days: int) -> float | None:
    if df is None or df.empty or "close" not in df.columns:
        return None

    close = df["close"].dropna()
    if len(close) <= days:
        return None

    latest = _safe_float(close.iloc[-1])
    previous = _safe_float(close.iloc[-days - 1])
    if latest is None or previous in (None, 0):
        return None

    return latest / previous - 1


def _macro_snapshot(symbol: str | None, prices: dict[str, pd.DataFrame]) -> dict:
    if not symbol:
        return {
            "symbol": None,
            "available": False,
            "latest": None,
            "change_5d": None,
            "change_20d": None,
            "change_5d_pct": None,
            "change_20d_pct": None,
        }

    df = prices.get(symbol)
    latest = _latest_close(df)
    return {
        "symbol": symbol,
        "available": latest is not None,
        "latest": latest,
        "change_5d": _change_value(df, 5),
        "change_20d": _change_value(df, 20),
        "change_5d_pct": _change_pct(df, 5),
        "change_20d_pct": _change_pct(df, 20),
    }


def _direction(value: float | None, threshold: float = 0.0) -> str:
    if value is None:
        return "unknown"
    if value > threshold:
        return "rising"
    if value < -threshold:
        return "falling"
    return "flat"


def _fmt(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "NA"
    return f"{value:.2f}{suffix}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "NA"
    return _fmt(value * 100, "%")


def _macro_context(
    snapshots: dict[str, dict],
    config: dict,
) -> tuple[str, str, str]:
    vix_cfg = config.get("market_regime", {}).get("vix", {})
    vix_high = float(vix_cfg.get("high_risk_above", 25))
    vix_low = float(vix_cfg.get("low_risk_below", 16))

    available = [snap for snap in snapshots.values() if snap.get("available")]
    if not available:
        return (
            "MISSING",
            "UNKNOWN",
            "macro data unavailable from yfinance",
        )

    if len(available) == len(snapshots):
        status = "AVAILABLE"
    else:
        status = "PARTIAL"

    vix = snapshots["vix"].get("latest")
    us10y = snapshots["us10y"]
    us30y = snapshots["us30y"]
    dxy = snapshots["dxy"]
    wti = snapshots["wti"]
    btc = snapshots["btc"]

    risk_points = 0
    notes: list[str] = []

    if vix is not None:
        if vix >= vix_high:
            risk_points += 2
            notes.append(f"VIX elevated at {_fmt(vix)}")
        elif vix < vix_low:
            notes.append(f"VIX calm at {_fmt(vix)}")
        else:
            notes.append(f"VIX neutral at {_fmt(vix)}")
    else:
        notes.append("VIX unavailable")

    us10y_dir = _direction(us10y.get("change_20d"), threshold=0.25)
    us30y_dir = _direction(us30y.get("change_20d"), threshold=0.25)
    if us10y_dir == "rising":
        risk_points += 1
    if us30y_dir == "rising":
        risk_points += 1
    notes.append(
        "yields "
        f"US10Y {us10y_dir} ({_fmt(us10y.get('latest'))}, 20d {_fmt(us10y.get('change_20d'))}); "
        f"US30Y {us30y_dir} ({_fmt(us30y.get('latest'))}, 20d {_fmt(us30y.get('change_20d'))})"
    )

    dxy_dir = _direction(dxy.get("change_20d_pct"), threshold=0.02)
    if dxy_dir == "rising":
        risk_points += 1
        dxy_note = "DXY strong"
    elif dxy_dir == "falling":
        dxy_note = "DXY weak"
    else:
        dxy_note = "DXY neutral"
    notes.append(f"{dxy_note} ({_fmt(dxy.get('latest'))}, 20d {_fmt_pct(dxy.get('change_20d_pct'))})")

    wti_dir = _direction(wti.get("change_20d_pct"), threshold=0.03)
    btc_dir = _direction(btc.get("change_20d_pct"), threshold=0.05)
    notes.append(f"WTI {wti_dir} ({_fmt(wti.get('latest'))}, 20d {_fmt_pct(wti.get('change_20d_pct'))})")
    notes.append(f"BTC {btc_dir} ({_fmt(btc.get('latest'))}, 20d {_fmt_pct(btc.get('change_20d_pct'))})")

    if risk_points >= 4:
        risk_flag = "RISK_OFF_PRESSURE"
    elif risk_points >= 2:
        risk_flag = "MIXED_MACRO"
    else:
        risk_flag = "RISK_ON_SUPPORTIVE"

    return status, risk_flag, "; ".join(notes)


def classify_market_regime(config: dict) -> dict:
    b = config.get("benchmarks", {})
    symbols = [
        b.get("broad_market", "SPY"),
        b.get("growth_market", "QQQ"),
        b.get("small_caps", "IWM"),
        b.get("volatility", "^VIX"),
        b.get("us10y", "^TNX"),
        b.get("us30y", "^TYX"),
        b.get("dollar", "DX-Y.NYB"),
        b.get("crude_oil", "CL=F"),
        b.get("bitcoin", "BTC-USD"),
    ]
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
    us10y_symbol = b.get("us10y", "^TNX")
    us30y_symbol = b.get("us30y", "^TYX")
    dollar_symbol = b.get("dollar", "DX-Y.NYB")

    macro_snapshots = {
        "us10y": _macro_snapshot(us10y_symbol, prices),
        "us30y": _macro_snapshot(us30y_symbol, prices),
        "vix": _macro_snapshot(b.get("volatility", "^VIX"), prices),
        "dxy": _macro_snapshot(dollar_symbol, prices),
        "wti": _macro_snapshot(b.get("crude_oil", "CL=F"), prices),
        "btc": _macro_snapshot(b.get("bitcoin", "BTC-USD"), prices),
    }

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

    us10y = macro_snapshots["us10y"]
    dxy = macro_snapshots["dxy"]
    if us10y.get("available"):
        us10y_not_spiking = (us10y.get("change_20d") is None) or us10y.get("change_20d") <= 0.25
        score += int(us10y_not_spiking)
        diagnostics["us10y_not_spiking_20d"] = bool(us10y_not_spiking)

    if dxy.get("available"):
        dxy_not_strong = (dxy.get("change_20d_pct") is None) or dxy.get("change_20d_pct") <= 0.02
        score += int(dxy_not_strong)
        diagnostics["dxy_not_strengthening_20d"] = bool(dxy_not_strong)

    macro_context_status, macro_risk_flag, macro_notes = _macro_context(macro_snapshots, config)
    diagnostics["macro"] = macro_snapshots

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
        "regime_score_norm": min(score / 8, 1.0),
        "min_candidate_score": min_candidate_score,
        "block_new_longs": block,
        "macro_context_status": macro_context_status,
        "macro_risk_flag": macro_risk_flag,
        "macro_notes": macro_notes,
        "macro_source": MACRO_SOURCE,
        "macro_timestamp": datetime.now(timezone.utc).isoformat(),
        "macro_data_freshness": MACRO_DATA_FRESHNESS,
        "diagnostics": diagnostics,
    }
