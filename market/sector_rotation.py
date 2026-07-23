from __future__ import annotations

import pandas as pd


def calculate_sector_rotation(meta: pd.DataFrame, prices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for _, r in meta.iterrows():
        t = r["ticker"]
        df = prices.get(t)
        if df is None or len(df) < 25:
            continue
        ret5 = df["close"].iloc[-1] / df["close"].iloc[-6] - 1 if len(df) >= 6 else 0
        ret20 = df["close"].iloc[-1] / df["close"].iloc[-21] - 1 if len(df) >= 21 else 0
        rows.append({
            "ticker": t,
            "sector": r.get("sector") or "Unknown",
            "industry": r.get("industry") or "Unknown",
            "ret5": ret5,
            "ret20": ret20,
            "above_sma20": df["close"].iloc[-1] > df["close"].rolling(20).mean().iloc[-1],
        })
    base = pd.DataFrame(rows)
    if base.empty:
        return pd.DataFrame(columns=["ticker", "sector_score", "sector_return_5d", "sector_return_20d"])

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
