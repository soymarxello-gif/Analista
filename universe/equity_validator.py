\
from __future__ import annotations

import pandas as pd


def validate_universe(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    universe_cfg = config.get("universe", {})
    excluded_terms = [x.lower() for x in universe_cfg.get("exclude_name_contains", [])]
    allowed_quote_types = set(universe_cfg.get("allowed_quote_types", ["EQUITY"]))

    validation_status = []
    warnings = []

    for _, row in out.iterrows():
        ticker = str(row.get("ticker", "")).upper()
        company = str(row.get("company") or "")
        quote_type = row.get("quote_type")
        status = "PASS"
        warn = []

        if quote_type and str(quote_type).upper() not in allowed_quote_types:
            status = "FAIL"
            warn.append(f"quote_type={quote_type}")

        name_l = company.lower()
        if any(term in name_l for term in excluded_terms):
            status = "FAIL"
            warn.append("nombre contiene término excluido")

        if "-" in ticker and ticker.endswith(("-W", "-U", "-R")):
            status = "FAIL"
            warn.append("posible warrant/unit/right")

        if not quote_type:
            warn.append("quote_type no disponible")

        validation_status.append(status)
        warnings.append("; ".join(warn))

    out["validation_status"] = validation_status
    out["data_quality_warning"] = warnings
    return out[out["validation_status"] == "PASS"].reset_index(drop=True)
