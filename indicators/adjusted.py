from __future__ import annotations

import pandas as pd


def price_series(df: pd.DataFrame, raw_column: str, adjusted_column: str | None = None) -> pd.Series:
    """Return an adjusted price series when available, otherwise the raw price.

    Indicator modules use this helper to stay consistent with the OHLCV cleaner:
    Yahoo adjusted prices are preferred for technical calculations, but missing
    adjusted columns never break the scanner.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.Series(dtype=float)

    adjusted = str(adjusted_column or "").strip()
    raw = str(raw_column or "").strip()
    if adjusted and adjusted in df.columns:
        series = pd.to_numeric(df[adjusted], errors="coerce")
        if series.notna().any():
            return series
    if raw in df.columns:
        return pd.to_numeric(df[raw], errors="coerce")
    return pd.Series(index=df.index, dtype=float)
