from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from universe.equity_validator import assess_universe


@dataclass
class EarlyFilterState:
    hard_rejected: list[dict] = field(default_factory=list)
    no_history: list[dict] = field(default_factory=list)
    eligible_metadata: dict[str, dict] = field(default_factory=dict)


def _num(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def hard_filter_reasons(row: dict, config: dict) -> list[str]:
    filters = config.get("filters", {})
    min_price = float(filters.get("min_price", 10))
    min_market_cap = float(filters.get("min_market_cap_usd", 1_500_000_000))
    reasons = [
        part.strip()
        for part in str(row.get("universe_veto_reasons") or "").split(",")
        if part.strip()
    ]
    price = _num(row.get("price"))
    market_cap = _num(row.get("market_cap"))
    if price is not None and price < min_price:
        reasons.append("price_below_min")
    if market_cap is None or market_cap < min_market_cap:
        reasons.append("market_cap_below_min")
    return list(dict.fromkeys(reasons))


def install_early_filters(scanner_module, config: dict) -> EarlyFilterState:
    """Wrap scanner clients so hard filters run before historical downloads."""
    state = EarlyFilterState()
    original_enrich = scanner_module.enrich_metadata
    original_download = scanner_module.download_daily_prices

    def enrich_and_filter(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
        enriched = assess_universe(original_enrich(df, cfg), cfg)
        if enriched.empty:
            return enriched

        accepted: list[dict] = []
        for row in enriched.to_dict(orient="records"):
            reasons = hard_filter_reasons(row, cfg)
            if reasons:
                rejected = dict(row)
                rejected["early_veto_reasons"] = ", ".join(reasons)
                state.hard_rejected.append(rejected)
            else:
                accepted.append(row)
                ticker = str(row.get("ticker") or "").upper()
                if ticker:
                    state.eligible_metadata[ticker] = dict(row)
        return pd.DataFrame(accepted)

    def download_and_audit(tickers, *args, **kwargs):
        result = original_download(tickers, *args, **kwargs)
        result = result or {}
        for ticker in tickers:
            symbol = str(ticker).upper()
            frame = result.get(symbol)
            if frame is None or frame.empty:
                row = dict(state.eligible_metadata.get(symbol, {"ticker": symbol}))
                row["early_veto_reasons"] = "missing_price_history"
                state.no_history.append(row)
        return result

    scanner_module.enrich_metadata = enrich_and_filter
    scanner_module.download_daily_prices = download_and_audit
    return state


def _audit_row(source: dict, *, reason: str, stage: str) -> dict:
    return {
        **source,
        "ticker": source.get("ticker"),
        "signal": "VETO",
        "veto_reasons": reason,
        "all_veto_reasons": reason,
        "penalty_reasons": "",
        "reason_summary": f"Veto: {reason}",
        "scanner_stage": stage,
        "setup_type": "NO_VALID_SETUP",
        "trigger_confirmed": False,
        "entry": None,
        "stop": None,
        "target": None,
        "rr": None,
        "final_score": 0.0,
        "liquidity_pass": False,
        "options_data_available": False,
        "options_source": "skipped_early_veto",
    }


def append_early_veto_rows(df: pd.DataFrame, state: EarlyFilterState) -> pd.DataFrame:
    rows = []
    rows.extend(
        _audit_row(
            row,
            reason=str(row.get("early_veto_reasons") or "hard_filter_fail"),
            stage="HARD_FILTER_VETO",
        )
        for row in state.hard_rejected
    )
    rows.extend(
        _audit_row(row, reason="missing_price_history", stage="NO_HISTORY_VETO")
        for row in state.no_history
    )
    if not rows:
        return df.copy()
    audit = pd.DataFrame(rows)
    if df.empty:
        return audit
    return pd.concat([df, audit], ignore_index=True, sort=False)
