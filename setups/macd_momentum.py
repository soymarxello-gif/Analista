from __future__ import annotations

import pandas as pd


def _float(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _weekly_macd_hist_non_bearish(df: pd.DataFrame) -> bool | None:
    if df is None or df.empty or "close" not in df.columns:
        return None
    if not isinstance(df.index, pd.DatetimeIndex) or len(df) < 90:
        return None

    weekly_close = df["close"].astype(float).resample("W-FRI").last().dropna()
    if len(weekly_close) < 35:
        return None

    ema_fast = weekly_close.ewm(span=12, adjust=False).mean()
    ema_slow = weekly_close.ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    latest = _float(hist.iloc[-1])
    previous = _float(hist.iloc[-2])
    two_ago = _float(hist.iloc[-3])
    if latest is None or previous is None or two_ago is None:
        return None

    return not (latest < previous < two_ago)


def detect_macd_momentum(df: pd.DataFrame, config: dict) -> dict:
    cfg = config.get("setups", {}).get("macd_momentum", {})
    if not cfg.get("enabled", True):
        return {"is_macd_momentum": False}
    if df is None or len(df) < 90:
        return {"is_macd_momentum": False}

    row = df.iloc[-1]
    previous = df.iloc[-2]
    two_ago = df.iloc[-3]
    close = _float(row.get("close"))
    ema20 = _float(row.get("ema20"))
    sma50 = _float(row.get("sma50"))
    sma200 = _float(row.get("sma200"))
    atr = _float(row.get("atr"))
    rsi = _float(row.get("rsi"))
    hist = _float(row.get("macd_hist"))
    hist_prev = _float(previous.get("macd_hist"))
    hist_two_ago = _float(two_ago.get("macd_hist"))
    relative_volume = _float(row.get("relative_volume"), 0.0) or 0.0

    if None in {close, ema20, sma50, sma200, atr, rsi, hist, hist_prev, hist_two_ago}:
        return {"is_macd_momentum": False}

    min_rsi = float(cfg.get("min_rsi", 50))
    max_rsi = float(cfg.get("max_rsi", 72))
    max_overextended_rsi = float(cfg.get("max_rsi_overextended", 75))
    min_relative_volume = float(cfg.get("min_relative_volume", 0.80))
    max_distance_pct = float(cfg.get("max_distance_ema20_pct", 0.055))
    max_distance_atr = float(cfg.get("max_distance_ema20_atr", 1.75))
    require_weekly_non_bearish = bool(cfg.get("require_weekly_macd_non_bearish", True))

    distance_pct = close / ema20 - 1.0 if ema20 else None
    distance_atr = (close - ema20) / atr if atr else None
    weekly_non_bearish = _weekly_macd_hist_non_bearish(df)

    trend_ok = close > sma50 and close > sma200 and ema20 >= sma50 * 0.98
    histogram_two_day_rising = hist > hist_prev > hist_two_ago
    rsi_ok = min_rsi <= rsi <= max_rsi and rsi < max_overextended_rsi
    extension_ok = (
        distance_pct is not None
        and distance_atr is not None
        and distance_pct <= max_distance_pct
        and distance_atr <= max_distance_atr
    )
    volume_ok = relative_volume >= min_relative_volume
    weekly_ok = (
        weekly_non_bearish is not False
        if require_weekly_non_bearish
        else True
    )

    is_setup = bool(
        trend_ok
        and histogram_two_day_rising
        and rsi_ok
        and extension_ok
        and volume_ok
        and weekly_ok
    )

    trigger_level = max(
        _float(row.get("high"), close) or close,
        _float(previous.get("high"), close) or close,
    )

    return {
        "is_macd_momentum": is_setup,
        "macd_momentum_level": float(trigger_level) if trigger_level is not None else None,
        "macd_momentum_reason": (
            "daily_macd_hist_2d_rising_weekly_non_bearish"
            if is_setup
            else ""
        ),
    }
