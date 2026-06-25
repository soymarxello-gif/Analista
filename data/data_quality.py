from __future__ import annotations

import pandas as pd

CORE_CRITICAL_FIELDS = [
    "ticker",
    "price",
    "market_cap",
    "avg_volume_20d",
    "dollar_volume_20d",
    "liquidity_pass",
    "trend_score",
    "rr",
    "setup_type",
]

MARKET_IMPORTANT_FIELDS = [
    "atr",
    "atr_pct",
    "relative_volume",
    "volume_score",
    "momentum_score",
    "rs_score",
]

FUNDAMENTAL_IMPORTANT_FIELDS = [
    "sector",
    "industry",
    "earnings_date",
    "days_to_earnings",
    "revenue_growth",
    "earnings_growth",
    "operating_margins",
    "debt_to_equity",
    "return_on_equity",
]

OPTIONS_FIELDS = [
    "options_score",
    "options_bias",
    "options_confidence",
    "put_call_volume_ratio",
    "put_call_oi_ratio",
    "call_volume_share",
    "near_call_oi_share",
]

EXECUTION_FIELDS = [
    "quote_status",
    "execution_quote_quality",
    "bid_ask_valid",
]


# Backward-compatible names.
CRITICAL_FIELDS = CORE_CRITICAL_FIELDS

IMPORTANT_FIELDS = (
    MARKET_IMPORTANT_FIELDS
    + FUNDAMENTAL_IMPORTANT_FIELDS
    + OPTIONS_FIELDS
    + EXECUTION_FIELDS
)


def _is_missing(value) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    text = str(value).strip().lower()
    return text in {"", "none", "nan", "null", "na", "n/a"}


def _clip01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _missing(row: dict, fields: list[str]) -> list[str]:
    return [f for f in fields if _is_missing(row.get(f))]


def _score_from_missing(
    missing_count: int,
    total_count: int,
    penalty: float,
) -> float:
    if total_count <= 0:
        return 1.0

    score = 1.0 - missing_count * penalty
    return _clip01(score)


def _execution_quality_score(row: dict) -> float:
    quote_status = str(row.get("quote_status") or "").upper().strip()
    execution_quote_quality = str(row.get("execution_quote_quality") or "").upper().strip()

    if execution_quote_quality == "HIGH" and quote_status == "VALID":
        return 1.0

    if execution_quote_quality == "MEDIUM":
        return 0.75

    if quote_status in {"STALE_POSSIBLE", "WIDE_OR_INCOHERENT"}:
        return 0.45

    if quote_status in {"INVALID", "MISSING"} or execution_quote_quality == "LOW":
        return 0.30

    return 0.60


def _options_quality_score(row: dict, missing_options: list[str]) -> float:
    options_available = bool(row.get("options_data_available"))
    options_bias = str(row.get("options_bias") or "").upper().strip()
    options_confidence = str(row.get("options_confidence") or "").upper().strip()

    if not options_available or options_bias == "UNKNOWN_OPTIONS_FLOW":
        return 0.0

    if options_confidence == "HIGH":
        base = 1.0
    elif options_confidence == "MEDIUM":
        base = 0.75
    elif options_confidence == "LOW":
        base = 0.45
    else:
        base = 0.50

    return _clip01(base - 0.08 * len(missing_options))


def score_data_quality(row: dict, config: dict | None = None) -> dict:
    """
    Data-quality score for scanner output rows.

    Phase 11:
    - Core operational data is separated from fundamentals, options and execution quote quality.
    - Missing options data should not turn an otherwise usable stock into LOW core data quality.
    - execution_quote_quality remains separate and still controls whether a row can be TRIGGER_CONFIRMED elsewhere.
    """
    config = config or {}
    dq_cfg = config.get("data_quality", {})

    core_fields = dq_cfg.get("core_critical_fields", CORE_CRITICAL_FIELDS)
    market_fields = dq_cfg.get("market_important_fields", MARKET_IMPORTANT_FIELDS)
    fundamental_fields = dq_cfg.get("fundamental_important_fields", FUNDAMENTAL_IMPORTANT_FIELDS)
    options_fields = dq_cfg.get("options_fields", OPTIONS_FIELDS)

    core_missing = _missing(row, core_fields)
    market_missing = _missing(row, market_fields)
    fundamental_missing = _missing(row, fundamental_fields)
    options_missing = _missing(row, options_fields)

    core_score = _score_from_missing(
        len(core_missing),
        len(core_fields),
        dq_cfg.get("core_missing_penalty", 0.20),
    )

    market_score = _score_from_missing(
        len(market_missing),
        len(market_fields),
        dq_cfg.get("market_missing_penalty", 0.06),
    )

    fundamental_score = _score_from_missing(
        len(fundamental_missing),
        len(fundamental_fields),
        dq_cfg.get("fundamental_missing_penalty", 0.04),
    )

    options_quality_score = _options_quality_score(row, options_missing)
    execution_quality_score = _execution_quality_score(row)

    # General data quality should mainly reflect tradability and analysis completeness.
    # Options are deliberately excluded here because UNKNOWN_OPTIONS_FLOW is handled separately.
    score = (
        dq_cfg.get("core_weight", 0.55) * core_score
        + dq_cfg.get("market_weight", 0.20) * market_score
        + dq_cfg.get("fundamental_weight", 0.15) * fundamental_score
        + dq_cfg.get("execution_weight", 0.10) * execution_quality_score
    )

    score = _clip01(score)

    warnings = []
    if core_missing:
        warnings.append("missing core: " + ",".join(core_missing))
    if market_missing:
        warnings.append("missing market: " + ",".join(market_missing))
    if fundamental_missing:
        warnings.append("missing fundamental: " + ",".join(fundamental_missing))
    if options_missing:
        warnings.append("missing options: " + ",".join(options_missing))

    # Backward-compatible fields:
    # - missing_critical_fields now means true core operational missing fields.
    # - missing_important_fields excludes options; options have their own field.
    missing_critical = core_missing
    missing_important = market_missing + fundamental_missing

    if core_missing:
        confidence = "LOW"
    elif score >= 0.90:
        confidence = "HIGH"
    elif score >= 0.75:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "data_quality_score": round(score, 4),
        "data_quality_confidence": confidence,
        "missing_critical_fields": ",".join(missing_critical),
        "missing_important_fields": ",".join(missing_important),
        "data_quality_warning": "; ".join(warnings),

        # Phase 11 explicit components.
        "core_data_quality_score": round(core_score, 4),
        "market_data_quality_score": round(market_score, 4),
        "fundamental_data_quality_score": round(fundamental_score, 4),
        "options_data_quality_score": round(options_quality_score, 4),
        "execution_data_quality_score": round(execution_quality_score, 4),

        "core_missing_fields": ",".join(core_missing),
        "market_missing_fields": ",".join(market_missing),
        "fundamental_missing_fields": ",".join(fundamental_missing),
        "options_missing_fields": ",".join(options_missing),
    }