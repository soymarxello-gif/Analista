from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from scoring.signal_classifier import classify_signal

EXCLUDED_QUOTE_TYPES = {
    "ETN",
    "MUTUALFUND",
    "MUTUAL_FUND",
    "PREFERRED",
    "PREFERRED_SHARE",
    "WARRANT",
    "RIGHT",
    "UNIT",
    "CLOSED_END_FUND",
}


def _num(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "pass"}
    return bool(value)


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


def _parse_reasons(value) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    for separator in (";", "|"):
        text = text.replace(separator, ",")
    return [part.strip() for part in text.split(",") if part.strip()]


def assess_quote_quality(row: dict, config: dict) -> tuple[str, str]:
    bid = _num(row.get("bid"))
    ask = _num(row.get("ask"))
    price = _num(row.get("price"))

    if bid is None or ask is None:
        return "MISSING", "LOW"
    if bid <= 0 or ask <= 0 or ask <= bid:
        return "INVALID", "LOW"

    midpoint = (bid + ask) / 2
    spread_pct = (ask - bid) / midpoint if midpoint > 0 else None
    max_spread = float(config.get("liquidity", {}).get("max_spread_pct", 0.03))
    max_distance = float(config.get("liquidity", {}).get("max_quote_distance_pct", 0.15))

    if price is not None and price > 0:
        distance = abs(midpoint - price) / price
        if distance > max_distance:
            return "STALE_POSSIBLE", "LOW"

    if spread_pct is None or spread_pct > max_spread:
        return "WIDE_OR_INCOHERENT", "LOW"
    if spread_pct > max_spread / 2:
        return "VALID", "MEDIUM"
    return "VALID", "HIGH"


def _hard_veto_reasons(row: dict, config: dict) -> list[str]:
    reasons: list[str] = []
    filters = config.get("filters", {})
    min_price = float(filters.get("min_price", 10))
    min_market_cap = float(filters.get("min_market_cap_usd", 1_500_000_000))

    price = _num(row.get("price"))
    market_cap = _num(row.get("market_cap"))
    quote_type = str(row.get("quote_type") or "").strip().upper()
    allowed_quote_types = {
        str(value).upper() for value in config.get("universe", {}).get("allowed_quote_types", ["EQUITY"])
    }
    is_etf = quote_type == "ETF"

    if price is None or price < min_price:
        reasons.append("price_below_min")
    if not is_etf and market_cap is not None and market_cap < min_market_cap:
        reasons.append("market_cap_below_min")
    if quote_type and quote_type not in allowed_quote_types:
        reasons.append("non_tradable_instrument")
    if quote_type in EXCLUDED_QUOTE_TYPES:
        reasons.append("excluded_security_type")
    return reasons


def _score100(*values, default=50.0) -> float:
    nums = [_num(v) for v in values]
    nums = [v for v in nums if v is not None]
    if not nums:
        return float(default)
    normalized = [v * 100 if 0 <= v <= 1 else v for v in nums]
    return round(max(0.0, min(100.0, sum(normalized) / len(normalized))), 2)


def _add_scores(row: dict, config: dict) -> None:
    row["asset_quality_score"] = _score100(
        row.get("liquidity_score"), row.get("trend_score")
    )
    row["setup_quality_score"] = _score100(
        row.get("structure_score"), row.get("rr_score"), row.get("momentum_score"), row.get("volume_score")
    )
    row["context_score"] = _score100(
        row.get("rs_score"), row.get("sector_score"), row.get("trend_score")
    )

    options_available = _bool(row.get("options_data_available"))
    row["institutional_score"] = (
        _score100(row.get("options_score")) if options_available else None
    )

    weights = config.get("trade_score_weights", {})
    weighted = [
        (row["asset_quality_score"], float(weights.get("asset_quality", 0.25))),
        (row["setup_quality_score"], float(weights.get("setup_quality", 0.40))),
        (row["context_score"], float(weights.get("technical_context", weights.get("context", 0.25)))),
    ]

    total_weight = sum(weight for _, weight in weighted) or 1.0
    final_trade_score = sum(score * weight for score, weight in weighted) / total_weight

    if row.get("setup_type") == "NO_VALID_SETUP":
        final_trade_score = min(final_trade_score, 49.0)
    row["final_trade_score"] = round(final_trade_score, 2)
    row["score_breakdown"] = (
        f"asset={row['asset_quality_score']}; setup={row['setup_quality_score']}; "
        f"technical_context={row['context_score']}; "
        f"advisory_fundamental={_score100(row.get('fundamental_score'))}; "
        f"advisory_options={row['institutional_score']}"
    )


def normalize_candidate(row: dict, config: dict) -> dict:
    out = dict(row)
    quote_status, quote_quality = assess_quote_quality(out, config)
    out["quote_status"] = quote_status
    out["execution_quote_quality"] = quote_quality

    hard_reasons = _hard_veto_reasons(out, config)
    existing_veto = _parse_reasons(out.get("all_veto_reasons")) + _parse_reasons(out.get("veto_reasons"))
    penalties = _parse_reasons(out.get("penalty_reasons"))

    _add_scores(out, config)

    signal, classifier_reasons = classify_signal(out, config)
    all_veto = _unique(existing_veto + hard_reasons + classifier_reasons)

    if hard_reasons:
        signal = "VETO"
    if out.get("setup_type") == "NO_VALID_SETUP":
        signal = "VETO"
        all_veto = _unique(all_veto + ["no_valid_setup"])

    trigger = _bool(out.get("trigger_confirmed"))
    rr = _num(out.get("rr"), 0.0) or 0.0
    if signal == "TRIGGER_CONFIRMED" and (not trigger or quote_quality == "LOW" or rr < 2.0):
        signal = "WATCHLIST"
        if quote_quality == "LOW":
            penalties.append("execution_quote_unconfirmed")
        if not trigger:
            penalties.append("trigger_not_confirmed")
        if rr < 2.0:
            penalties.append("rr_below_trigger_minimum")

    if signal == "READY_WAIT_TRIGGER" and trigger:
        if quote_quality != "LOW" and rr >= 2.0:
            signal = "TRIGGER_CONFIRMED"
        else:
            signal = "WATCHLIST"
            penalties.append("trigger_conditions_incomplete")

    allowed = set(config.get("signals", {}).get("allowed_states", []))
    if signal not in allowed:
        signal = "WATCHLIST" if not all_veto else "VETO"
        penalties.append("unsupported_signal_downgraded")

    entry = out.get("entry")
    stop = out.get("stop")
    target = out.get("target")
    out["theoretical_entry"] = out.get("theoretical_entry", entry)
    out["theoretical_stop"] = out.get("theoretical_stop", stop)
    out["theoretical_target"] = out.get("theoretical_target", target)

    if signal == "VETO":
        out["actionable_entry"] = None
        out["actionable_stop"] = None
        out["actionable_target"] = None
    else:
        out["actionable_entry"] = out.get("actionable_entry", entry)
        out["actionable_stop"] = out.get("actionable_stop", stop)
        out["actionable_target"] = out.get("actionable_target", target)

    out["signal"] = signal
    out["all_veto_reasons"] = ", ".join(_unique(all_veto))
    out["veto_reasons"] = out["all_veto_reasons"]
    out["penalty_reasons"] = ", ".join(_unique(penalties))
    return out


def normalize_scan(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    rows = [normalize_candidate(row, config) for row in df.to_dict(orient="records")]
    out = pd.DataFrame(rows)

    out["legacy_rank"] = out["final_score"].rank(
        method="first", ascending=False, na_option="bottom"
    ).astype("Int64")
    out["trade_rank"] = out["final_trade_score"].rank(
        method="first", ascending=False, na_option="bottom"
    ).astype("Int64")
    out["rank_delta"] = out["legacy_rank"] - out["trade_rank"]
    out["legacy_rank_basis"] = "final_score"
    out["trade_rank_basis"] = "final_trade_score"

    signal_order = {
        "TRIGGER_CONFIRMED": 0,
        "READY_WAIT_TRIGGER": 1,
        "WATCHLIST": 2,
        "AVOID": 3,
        "VETO": 4,
    }
    out["_signal_order"] = out["signal"].map(signal_order).fillna(9)

    if config.get("ranking_audit", {}).get("change_production_ranking", False):
        sort_cols = ["_signal_order", "final_trade_score", "final_score"]
    else:
        sort_cols = ["_signal_order", "final_score"]

    out = out.sort_values(sort_cols, ascending=[True] + [False] * (len(sort_cols) - 1))
    out = out.drop(columns=["_signal_order"]).reset_index(drop=True)
    if "rank" in out.columns:
        out = out.drop(columns=["rank"])
    out.insert(0, "rank", range(1, len(out) + 1))
    return out
