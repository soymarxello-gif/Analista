from __future__ import annotations

import pandas as pd


def assess_universe(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Annotate every symbol without removing failed rows."""
    if df.empty:
        return df.copy()

    out = df.copy()
    universe_cfg = config.get("universe", {})
    excluded_terms = [str(x).lower() for x in universe_cfg.get("exclude_name_contains", [])]
    allowed_quote_types = {
        str(x).upper() for x in universe_cfg.get("allowed_quote_types", ["EQUITY"])
    }

    statuses: list[str] = []
    warnings: list[str] = []
    reasons: list[str] = []

    for _, row in out.iterrows():
        ticker = str(row.get("ticker", "")).upper()
        company = str(row.get("company") or "")
        quote_type = str(row.get("quote_type") or "").upper()
        row_reasons: list[str] = []
        row_warnings: list[str] = []

        if quote_type and quote_type not in allowed_quote_types:
            row_reasons.append("non_tradable_instrument")
            row_warnings.append(f"quote_type={quote_type}")
        if any(term in company.lower() for term in excluded_terms):
            row_reasons.append("excluded_security_name")
            row_warnings.append("nombre contiene término excluido")
        if "-" in ticker and ticker.endswith(("-W", "-U", "-R")):
            row_reasons.append("excluded_security_suffix")
            row_warnings.append("posible warrant/unit/right")
        if not quote_type:
            row_warnings.append("quote_type no disponible")

        statuses.append("FAIL" if row_reasons else "PASS")
        warnings.append("; ".join(row_warnings))
        reasons.append(", ".join(row_reasons))

    out["validation_status"] = statuses
    out["data_quality_warning"] = warnings
    out["universe_veto_reasons"] = reasons
    return out


def validate_universe(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    assessed = assess_universe(df, config)
    if assessed.empty:
        return assessed
    return assessed[assessed["validation_status"] == "PASS"].reset_index(drop=True)
