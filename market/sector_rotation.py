\
from __future__ import annotations

import pandas as pd

from data.technical_bars import closed_weekly_close

DEFAULT_SECTOR_BENCHMARKS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Industrials": "XLI",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

SECTOR_CONTEXT_COLUMNS = [
    "ticker",
    "sector_benchmark_symbol",
    "sector_weekly_macd_hist",
    "sector_weekly_macd_slope_1w",
    "sector_weekly_macd_prev_slope_1w",
    "sector_weekly_macd_acceleration",
    "sector_weekly_macd_state",
    "sector_weekly_macd_acceleration_state",
    "sector_context_status",
    "sector_context_reason",
    "sector_relative_return_20d",
    "sector_relative_return_60d",
    "sector_relative_line_slope_20d",
    "sector_relative_strength_score",
    "sector_relative_leadership_status",
]


def _safe_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def sector_benchmark_map(config: dict | None = None) -> dict[str, str]:
    cfg = (config or {}).get("sector_context", {})
    configured = cfg.get("benchmark_etfs") or {}
    mapping = {**DEFAULT_SECTOR_BENCHMARKS, **configured}
    return {
        _safe_text(sector): _safe_text(symbol).upper()
        for sector, symbol in mapping.items()
        if _safe_text(sector) and _safe_text(symbol)
    }


def sector_benchmark_symbols_for_meta(meta: pd.DataFrame, config: dict | None = None) -> list[str]:
    if meta.empty or "sector" not in meta.columns:
        return []
    mapping = sector_benchmark_map(config)
    symbols = []
    for sector in meta["sector"].dropna().astype(str).unique():
        symbol = mapping.get(_safe_text(sector))
        if symbol:
            symbols.append(symbol)
    return sorted(set(symbols))


def _empty_sector_context() -> pd.DataFrame:
    return pd.DataFrame(columns=SECTOR_CONTEXT_COLUMNS)


def _classify_sector_macd_histogram(
    *,
    latest: float | None,
    previous: float | None,
    two_ago: float | None,
    epsilon: float = 1e-9,
) -> dict:
    if latest is None or previous is None or two_ago is None:
        return {
            "sector_weekly_macd_hist": None,
            "sector_weekly_macd_slope_1w": None,
            "sector_weekly_macd_prev_slope_1w": None,
            "sector_weekly_macd_acceleration": None,
            "sector_weekly_macd_state": "SECTOR_MACD_UNKNOWN",
            "sector_weekly_macd_acceleration_state": "UNKNOWN",
            "sector_context_status": "UNKNOWN",
            "sector_context_reason": "sector_macd_histogram_missing",
        }

    slope = latest - previous
    prev_slope = previous - two_ago
    acceleration = slope - prev_slope

    if slope > epsilon and acceleration > epsilon:
        state = "SECTOR_MACD_ACCELERATING"
        acceleration_state = "ACCELERATING"
        status = "SUPPORTIVE"
        reason = "sector_weekly_macd_histogram_accelerating"
    elif slope > epsilon and acceleration >= -epsilon:
        state = "SECTOR_MACD_IMPROVING"
        acceleration_state = "STABLE"
        status = "SUPPORTIVE"
        reason = "sector_weekly_macd_histogram_improving"
    elif slope > epsilon and acceleration < -epsilon:
        state = "SECTOR_MACD_IMPROVING_BUT_DECELERATING"
        acceleration_state = "DECELERATING"
        status = "WATCH"
        reason = "sector_weekly_macd_improving_but_decelerating"
    elif slope < -epsilon and latest < 0:
        state = "SECTOR_MACD_BEARISH"
        acceleration_state = "DECELERATING"
        status = "RISK"
        reason = "sector_weekly_macd_bearish_and_falling"
    elif slope < -epsilon:
        state = "SECTOR_MACD_DECELERATING"
        acceleration_state = "DECELERATING"
        status = "RISK"
        reason = "sector_weekly_macd_histogram_decelerating"
    else:
        state = "SECTOR_MACD_MIXED"
        acceleration_state = "FLAT"
        status = "WATCH"
        reason = "sector_weekly_macd_histogram_flat_or_mixed"

    return {
        "sector_weekly_macd_hist": latest,
        "sector_weekly_macd_slope_1w": slope,
        "sector_weekly_macd_prev_slope_1w": prev_slope,
        "sector_weekly_macd_acceleration": acceleration,
        "sector_weekly_macd_state": state,
        "sector_weekly_macd_acceleration_state": acceleration_state,
        "sector_context_status": status,
        "sector_context_reason": reason,
    }


def calculate_weekly_sector_macd_context(price_frame: pd.DataFrame, config: dict | None = None) -> dict:
    if price_frame is None or price_frame.empty:
        return _classify_sector_macd_histogram(latest=None, previous=None, two_ago=None)

    cfg = (config or {}).get("sector_context", {})
    macd_cfg = cfg.get("macd", {})
    fast = int(macd_cfg.get("fast", 12))
    slow = int(macd_cfg.get("slow", 26))
    signal = int(macd_cfg.get("signal", 9))
    min_weeks = int(cfg.get("min_weeks", max(slow + signal + 3, 35)))

    close_col = "adj_close" if "adj_close" in price_frame.columns else "close"
    if close_col not in price_frame.columns:
        return _classify_sector_macd_histogram(latest=None, previous=None, two_ago=None)

    close = pd.to_numeric(price_frame[close_col], errors="coerce").dropna()
    if close.empty:
        return _classify_sector_macd_histogram(latest=None, previous=None, two_ago=None)

    index = pd.to_datetime(close.index, errors="coerce")
    close = pd.Series(close.to_numpy(dtype=float), index=index).dropna()
    close = close[~close.index.isna()].sort_index()
    if close.empty:
        return _classify_sector_macd_histogram(latest=None, previous=None, two_ago=None)

    weekly, _ = closed_weekly_close(
        close,
        weekly_rule=str(cfg.get("weekly_rule", "W-FRI")),
    )
    if len(weekly) < min_weeks:
        result = _classify_sector_macd_histogram(latest=None, previous=None, two_ago=None)
        result["sector_context_reason"] = "sector_weekly_history_insufficient"
        return result

    ema_fast = weekly.ewm(span=fast, adjust=False).mean()
    ema_slow = weekly.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = (macd_line - signal_line).dropna()
    if len(hist) < 3:
        return _classify_sector_macd_histogram(latest=None, previous=None, two_ago=None)

    return _classify_sector_macd_histogram(
        latest=float(hist.iloc[-1]),
        previous=float(hist.iloc[-2]),
        two_ago=float(hist.iloc[-3]),
    )


def calculate_sector_benchmark_context(
    meta: pd.DataFrame,
    sector_prices: dict[str, pd.DataFrame],
    config: dict | None = None,
    ticker_prices: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    if meta.empty or "ticker" not in meta.columns:
        return _empty_sector_context()

    mapping = sector_benchmark_map(config)
    sector_context_cache: dict[str, dict] = {}
    rows: list[dict] = []

    for _, item in meta.iterrows():
        ticker = _safe_text(item.get("ticker")).upper()
        sector = _safe_text(item.get("sector"))
        symbol = mapping.get(sector, "")
        if not ticker:
            continue
        if not symbol:
            context = _classify_sector_macd_histogram(latest=None, previous=None, two_ago=None)
            context["sector_context_reason"] = "sector_benchmark_missing"
        else:
            if symbol not in sector_context_cache:
                context = calculate_weekly_sector_macd_context(
                    sector_prices.get(symbol, pd.DataFrame()),
                    config,
                )
                sector_context_cache[symbol] = context
            context = sector_context_cache[symbol]

        rows.append(
            {
                "ticker": ticker,
                "sector_benchmark_symbol": symbol,
                **context,
                **_calculate_relative_strength(
                    (ticker_prices or {}).get(ticker),
                    sector_prices.get(symbol) if symbol else None,
                ),
            }
        )

    if not rows:
        return _empty_sector_context()
    return pd.DataFrame(rows, columns=SECTOR_CONTEXT_COLUMNS)


def _calculate_relative_strength(
    ticker_frame: pd.DataFrame | None,
    benchmark_frame: pd.DataFrame | None,
) -> dict:
    empty = {
        "sector_relative_return_20d": None,
        "sector_relative_return_60d": None,
        "sector_relative_line_slope_20d": None,
        "sector_relative_strength_score": None,
        "sector_relative_leadership_status": "UNKNOWN",
    }
    if ticker_frame is None or benchmark_frame is None or ticker_frame.empty or benchmark_frame.empty:
        return empty

    def close_series(frame: pd.DataFrame) -> pd.Series:
        column = "adj_close" if "adj_close" in frame.columns else "close"
        if column not in frame.columns:
            return pd.Series(dtype=float)
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        series.index = pd.to_datetime(series.index, errors="coerce")
        return series[~series.index.isna()].sort_index()

    ticker_close = close_series(ticker_frame)
    benchmark_close = close_series(benchmark_frame)
    aligned = pd.concat(
        [ticker_close.rename("ticker"), benchmark_close.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    if len(aligned) < 61:
        return empty

    ticker_return_20 = float(aligned["ticker"].iloc[-1] / aligned["ticker"].iloc[-21] - 1.0)
    benchmark_return_20 = float(aligned["benchmark"].iloc[-1] / aligned["benchmark"].iloc[-21] - 1.0)
    ticker_return_60 = float(aligned["ticker"].iloc[-1] / aligned["ticker"].iloc[-61] - 1.0)
    benchmark_return_60 = float(aligned["benchmark"].iloc[-1] / aligned["benchmark"].iloc[-61] - 1.0)
    excess_20 = ticker_return_20 - benchmark_return_20
    excess_60 = ticker_return_60 - benchmark_return_60

    relative_line = aligned["ticker"] / aligned["benchmark"]
    slope_20 = float(relative_line.iloc[-1] / relative_line.iloc[-21] - 1.0)
    score = max(
        0.0,
        min(
            100.0,
            50.0
            + 350.0 * excess_20
            + 150.0 * excess_60
            + 250.0 * slope_20,
        ),
    )
    if score >= 70 and excess_20 > 0 and slope_20 > 0:
        status = "LEADING"
    elif score <= 35 and excess_20 < 0 and slope_20 < 0:
        status = "LAGGING"
    else:
        status = "IN_LINE"
    return {
        "sector_relative_return_20d": excess_20,
        "sector_relative_return_60d": excess_60,
        "sector_relative_line_slope_20d": slope_20,
        "sector_relative_strength_score": round(score, 2),
        "sector_relative_leadership_status": status,
    }


def calculate_sector_rotation(meta: pd.DataFrame, prices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for _, r in meta.iterrows():
        t = r["ticker"]
        df = prices.get(t)
        if df is None or len(df) < 25:
            continue
        close = df["adj_close"] if "adj_close" in df.columns else df["close"]
        sma20 = close.rolling(20).mean()
        ret5 = close.iloc[-1] / close.iloc[-6] - 1 if len(df) >= 6 else 0
        ret20 = close.iloc[-1] / close.iloc[-21] - 1 if len(df) >= 21 else 0
        rows.append({
            "ticker": t,
            "sector": r.get("sector") or "Unknown",
            "industry": r.get("industry") or "Unknown",
            "ret5": ret5,
            "ret20": ret20,
            "above_sma20": close.iloc[-1] > sma20.iloc[-1],
        })
    base = pd.DataFrame(rows)
    if base.empty:
        return pd.DataFrame(columns=["ticker", "sector", "sector_score", "sector_return_5d", "sector_return_20d"])

    sector = base.groupby("sector").agg(
        sector_return_5d=("ret5", "median"),
        sector_return_20d=("ret20", "median"),
        sector_breadth=("above_sma20", "mean"),
    ).reset_index()

    def pct_rank(s):
        return s.rank(pct=True).fillna(0.5)

    sector["sector_score"] = (
        0.4 * pct_rank(sector["sector_return_5d"]) +
        0.4 * pct_rank(sector["sector_return_20d"]) +
        0.2 * sector["sector_breadth"].fillna(0.5)
    ).clip(0, 1)

    return base[["ticker", "sector"]].merge(sector, on="sector", how="left")
