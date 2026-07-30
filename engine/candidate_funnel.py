from __future__ import annotations

from collections import Counter
from typing import Any


SIGNAL_PRIORITY = {
    "TRIGGER_CONFIRMED": 0,
    "READY_WAIT_TRIGGER": 1,
    "WATCHLIST": 2,
    "AVOID": 3,
    "VETO": 4,
}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text and text.lower() not in {"nan", "none", "null"} else default


def _funnel_score(row: dict) -> float:
    signal = _text(row.get("preliminary_signal"), "VETO").upper()
    signal_component = max(0.0, 1.0 - 0.20 * SIGNAL_PRIORITY.get(signal, 4))
    return round(
        100
        * (
            0.32 * (_float(row.get("preliminary_trade_score")) / 100.0)
            + 0.16 * (_float(row.get("preliminary_final_score")) / 100.0)
            + 0.14 * _float(row.get("trend_score"), 0.0)
            + 0.12 * _float(row.get("momentum_score"), 0.0)
            + 0.10 * _float(row.get("liquidity_score"), 0.0)
            + 0.08 * _float(row.get("source_quality_score"), 0.0)
            + 0.08 * signal_component
        ),
        4,
    )


def select_deep_analysis_candidates(
    candidates: list[dict],
    *,
    target_tickers: int = 50,
    min_tickers: int = 40,
    max_tickers: int = 60,
    max_sector_share: float = 0.20,
) -> tuple[list[str], dict[str, dict]]:
    """
    Select the universe that receives expensive scenario analysis.

    This layer is a funnel only. It does not emit signals, recommendations or
    operational levels. Canonical mode keeps every eligible operational or
    research row; legacy mode retains the historical bounded behavior.
    """
    if not candidates or max_tickers <= 0:
        return [], {}

    canonical_mode = any("technical_analysis_lane" in row for row in candidates)
    if canonical_mode:
        ranked = []
        for row in candidates:
            ticker = _text(row.get("ticker")).upper()
            if not ticker:
                continue
            ranked.append(
                {
                    **row,
                    "ticker": ticker,
                    "sector": _text(row.get("sector"), "UNKNOWN"),
                    "_score": _float(row.get("technical_opportunity_score"), 0.0),
                }
            )
        ranked.sort(
            key=lambda row: (
                0
                if _text(row.get("technical_analysis_lane")).upper()
                == "ADVANCE_DEEP_ANALYSIS"
                else 1
                if _text(row.get("technical_analysis_lane")).upper()
                == "ADVANCE_RESEARCH_ANALYSIS"
                else 2,
                -row["_score"],
                -_float(row.get("preliminary_trade_score")),
                row["ticker"],
            )
        )
        eligible = [
            row
            for row in ranked
            if _text(row.get("technical_analysis_lane")).upper()
            in {"ADVANCE_DEEP_ANALYSIS", "ADVANCE_RESEARCH_ANALYSIS"}
        ]
        selected = eligible
        selected_tickers = [row["ticker"] for row in selected]
        selected_set = set(selected_tickers)
        rank_by_ticker = {
            ticker: rank for rank, ticker in enumerate(selected_tickers, start=1)
        }
        audit = {}
        for row in ranked:
            ticker = row["ticker"]
            selected_flag = ticker in selected_set
            lane = _text(row.get("technical_analysis_lane"), "UNKNOWN").upper()
            audit[ticker] = {
                "deep_analysis_selected": selected_flag,
                "deep_analysis_tier": (
                    "OPERATIONAL"
                    if lane == "ADVANCE_DEEP_ANALYSIS"
                    else "RESEARCH"
                    if lane == "ADVANCE_RESEARCH_ANALYSIS"
                    else "NONE"
                ),
                "deep_analysis_rank": rank_by_ticker.get(ticker),
                "deep_analysis_score": row["_score"],
                "deep_analysis_reason": (
                    "selected_by_canonical_technical_eligibility"
                    if selected_flag
                    else f"not_selected_lane_{lane.lower()}"
                ),
                "deep_analysis_sector": row["sector"],
            }
        return selected_tickers, audit

    target = max(int(min_tickers), min(int(target_tickers), int(max_tickers)))
    sector_cap = max(3, int(round(target * max_sector_share)))
    ranked: list[dict] = []
    for row in candidates:
        ticker = _text(row.get("ticker")).upper()
        if not ticker:
            continue
        signal = _text(row.get("preliminary_signal"), "VETO").upper()
        ranked.append(
            {
                **row,
                "ticker": ticker,
                "sector": _text(row.get("sector"), "UNKNOWN"),
                "_score": _funnel_score(row),
                "_signal_priority": SIGNAL_PRIORITY.get(signal, 99),
            }
        )

    ranked.sort(
        key=lambda row: (
            row["_signal_priority"],
            -row["_score"],
            -_float(row.get("preliminary_trade_score")),
            row["ticker"],
        )
    )

    selected: list[dict] = []
    deferred: list[dict] = []
    sector_counts: Counter[str] = Counter()
    for row in ranked:
        if len(selected) >= target:
            break
        sector = row["sector"]
        if sector != "UNKNOWN" and sector_counts[sector] >= sector_cap:
            deferred.append(row)
            continue
        selected.append(row)
        sector_counts[sector] += 1

    if len(selected) < min(target, len(ranked)):
        already = {row["ticker"] for row in selected}
        for row in deferred + ranked:
            if row["ticker"] in already:
                continue
            selected.append(row)
            already.add(row["ticker"])
            if len(selected) >= target:
                break

    selected_tickers = [row["ticker"] for row in selected[:max_tickers]]
    selected_set = set(selected_tickers)
    rank_by_ticker = {ticker: rank for rank, ticker in enumerate(selected_tickers, start=1)}
    audit: dict[str, dict] = {}
    for row in ranked:
        ticker = row["ticker"]
        selected_flag = ticker in selected_set
        audit[ticker] = {
            "deep_analysis_selected": selected_flag,
            "deep_analysis_rank": rank_by_ticker.get(ticker),
            "deep_analysis_score": row["_score"],
            "deep_analysis_reason": (
                "selected_by_bounded_diversified_funnel"
                if selected_flag
                else "outside_deep_analysis_budget"
            ),
            "deep_analysis_sector": row["sector"],
        }
    return selected_tickers, audit
