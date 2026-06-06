\
import pandas as pd

def add_relative_strength_scores(rows: list[dict]) -> list[dict]:
    df = pd.DataFrame(rows)
    if df.empty:
        return rows
    for col in ["ret20", "ret63"]:
        if col not in df:
            df[col] = 0.0
    df["rs_score"] = (0.5 * df["ret20"].rank(pct=True) + 0.5 * df["ret63"].rank(pct=True)).fillna(0.5)
    mapping = dict(zip(df["ticker"], df["rs_score"]))
    for r in rows:
        r["rs_score"] = float(mapping.get(r["ticker"], 0.5))
    return rows
