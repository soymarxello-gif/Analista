from __future__ import annotations

from typing import Any

import pandas as pd


def _to_float(value: Any) -> float | None:
    """Convert common numeric payload values to float safely."""
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def validate_universe(df: pd.DataFrame, config: dict, strict_metadata: bool = False) -> pd.DataFrame:
    """
    Validate tradable universe.

    strict_metadata=False:
        First-pass validation after Yahoo screener. Missing quote_type or market_cap only warns.

    strict_metadata=True:
        Second-pass validation after metadata enrichment. Missing/non-equity quote_type can fail
        if configured, reducing ETF/fund/preferred/warrant contamination.

    Notes:
        This function filters the upstream universe.
        Final report-level VETO rows and all_veto_reasons must also be enforced later
        in the scanner/signal layer, because failed rows are removed here.
    """
    if df.empty:
        return df

    out = df.copy()

    universe_cfg = config.get("universe", {})
    filters_cfg = config.get("filters", {})
    liquidity_cfg = config.get("liquidity", {})

    excluded_terms = [str(x).lower() for x in universe_cfg.get("exclude_name_contains", [])]
    allowed_quote_types = {str(x).upper() for x in universe_cfg.get("allowed_quote_types", ["EQUITY"])}
    allowed_exchanges = {str(x).upper() for x in universe_cfg.get("allowed_exchanges", [])}

    min_price = _to_float(filters_cfg.get("min_price"))
    if min_price is None:
        min_price = _to_float(liquidity_cfg.get("min_price", 10))
    if min_price is None:
        min_price = 10.0

    min_market_cap_usd = _to_float(filters_cfg.get("min_market_cap_usd", 2_500_000_000))
    if min_market_cap_usd is None:
        min_market_cap_usd = 2_500_000_000.0

    strict_post = bool(universe_cfg.get("strict_post_enrichment", True))
    allow_missing_quote_type_strict = bool(universe_cfg.get("allow_missing_quote_type_after_enrichment", False))
    require_market_cap_after_enrichment = bool(
        universe_cfg.get("require_market_cap_after_enrichment", strict_metadata)
    )

    validation_status: list[str] = []
    warnings: list[str] = []
    universe_veto_reasons: list[str] = []

    for _, row in out.iterrows():
        ticker = str(row.get("ticker", "")).upper().strip()
        company = str(row.get("company") or "")

        quote_type = row.get("quote_type")
        exchange = row.get("exchange")

        quote_type_text = str(quote_type).upper().strip() if quote_type is not None else ""
        exchange_text = str(exchange).upper().strip() if exchange is not None else ""

        status = "PASS"
        warn: list[str] = []
        reasons: list[str] = []

        # Quote type / security type validation.
        if quote_type_text:
            if quote_type_text not in allowed_quote_types:
                status = "FAIL"
                _append_unique(reasons, "non_tradable_instrument")
                _append_unique(reasons, "excluded_security_type")
                warn.append(f"quote_type={quote_type}")
        else:
            warn.append("quote_type no disponible")
            if strict_metadata and strict_post and not allow_missing_quote_type_strict:
                status = "FAIL"
                _append_unique(reasons, "missing_quote_type_after_enrichment")
                warn.append("quote_type requerido tras enriquecimiento")

        # Exchange validation. Keep as warning because Yahoo exchange values can be inconsistent.
        if allowed_exchanges and exchange_text and exchange_text not in allowed_exchanges:
            warn.append(f"exchange no permitido/configurado: {exchange}")

        # Name-based exclusions.
        name_l = company.lower()
        if any(term in name_l for term in excluded_terms):
            status = "FAIL"
            _append_unique(reasons, "excluded_security_type")
            warn.append("nombre contiene término excluido")

        # Common non-common-stock suffixes.
        if ticker.endswith(("-W", "-WS", "-WT", "-U", "-UN", "-R", "-RT")):
            status = "FAIL"
            _append_unique(reasons, "excluded_security_type")
            warn.append("posible warrant/unit/right")

        # Dot share classes can be common stock (BRK.B), so do not blanket reject.
        # Caret, equals, slash and crypto FX suffixes are benchmarks/futures/synthetic.
        if any(x in ticker for x in ["^", "=", "/"]) or ticker.endswith("-USD"):
            status = "FAIL"
            _append_unique(reasons, "non_tradable_instrument")
            warn.append("ticker no compatible con acción común")

        # Price hard filter.
        price = _to_float(
            row.get("price")
            if "price" in row.index
            else row.get("regularMarketPrice")
            if "regularMarketPrice" in row.index
            else row.get("last_price")
        )

        if price is not None:
            if price < float(min_price):
                status = "FAIL"
                _append_unique(reasons, "price_below_min")
                warn.append(f"price {price:.2f} < min_price {float(min_price):.2f}")
        else:
            warn.append("price no disponible")
            # Missing price before enrichment may be acceptable. After enrichment it should fail.
            if strict_metadata:
                status = "FAIL"
                _append_unique(reasons, "missing_price_after_enrichment")

        # Market cap hard filter when data is available.
        market_cap = _to_float(
            row.get("market_cap")
            if "market_cap" in row.index
            else row.get("marketCap")
            if "marketCap" in row.index
            else row.get("market_cap_usd")
        )

        if market_cap is not None:
            if market_cap < float(min_market_cap_usd):
                status = "FAIL"
                _append_unique(reasons, "market_cap_below_min")
                warn.append(
                    f"market_cap {market_cap:.0f} < min_market_cap_usd {float(min_market_cap_usd):.0f}"
                )
        else:
            warn.append("market_cap no disponible")
            if strict_metadata and require_market_cap_after_enrichment:
                status = "FAIL"
                _append_unique(reasons, "missing_market_cap_after_enrichment")

        validation_status.append(status)
        warnings.append("; ".join(warn))
        universe_veto_reasons.append(";".join(reasons))

    out["validation_status"] = validation_status
    out["data_quality_warning"] = warnings
    out["universe_veto_reasons"] = universe_veto_reasons

    # Keep compatibility: all_veto_reasons will later be the scanner/report-level canonical field.
    # At universe-validation level, expose the same reasons under this name when present.
    out["all_veto_reasons"] = out["universe_veto_reasons"]

    return out[out["validation_status"] == "PASS"].reset_index(drop=True)
