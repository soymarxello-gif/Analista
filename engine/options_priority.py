from __future__ import annotations

from typing import Any


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_options_priority(candidate: dict) -> float:
    """Rank technically relevant candidates before expensive options requests."""
    setup_type = str(candidate.get("setup_type") or "NO_VALID_SETUP")
    if setup_type == "NO_VALID_SETUP":
        return 0.0

    score = (
        0.24 * _number(candidate.get("structure_score"), 0.5)
        + 0.20 * _number(candidate.get("trend_score"), 0.5)
        + 0.18 * _number(candidate.get("rr_score"), 0.0)
        + 0.13 * _number(candidate.get("momentum_score"), 0.5)
        + 0.10 * _number(candidate.get("volume_score"), 0.5)
        + 0.10 * _number(candidate.get("rs_score"), 0.5)
        + 0.05 * _number(candidate.get("liquidity_score"), 0.5)
    )
    if bool(candidate.get("trigger_confirmed")):
        score += 0.08
    rr = _number(candidate.get("rr"), 0.0)
    if rr >= 2.0:
        score += 0.04
    return round(max(0.0, min(1.0, score)), 6)


def select_options_tickers(candidates: list[dict], max_tickers: int) -> list[str]:
    """Return unique ticker symbols ordered by descending preliminary quality."""
    ranked = sorted(
        candidates,
        key=lambda row: (calculate_options_priority(row), str(row.get("ticker") or "")),
        reverse=True,
    )
    selected: list[str] = []
    for row in ranked:
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker or ticker in selected:
            continue
        if calculate_options_priority(row) <= 0:
            continue
        selected.append(ticker)
        if len(selected) >= max(0, int(max_tickers)):
            break
    return selected
