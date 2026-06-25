from __future__ import annotations

from engine.candidate_funnel import select_deep_analysis_candidates


def _candidate(index: int, *, sector: str = "Technology", signal: str = "WATCHLIST") -> dict:
    return {
        "ticker": f"T{index:03d}",
        "sector": sector,
        "preliminary_signal": signal,
        "preliminary_trade_score": 90 - index * 0.2,
        "preliminary_final_score": 85 - index * 0.1,
        "trend_score": 0.9,
        "momentum_score": 0.8,
        "liquidity_score": 0.9,
        "source_quality_score": 0.8,
    }


def test_funnel_targets_fifty_and_tracks_every_candidate() -> None:
    sectors = ["Technology", "Financial Services", "Industrials", "Healthcare", "Energy"]
    candidates = [_candidate(i, sector=sectors[i % len(sectors)]) for i in range(100)]

    selected, audit = select_deep_analysis_candidates(candidates)

    assert len(selected) == 50
    assert len(audit) == 100
    assert sum(bool(row["deep_analysis_selected"]) for row in audit.values()) == 50
    assert set(row["deep_analysis_reason"] for row in audit.values()) == {
        "selected_by_bounded_diversified_funnel",
        "outside_deep_analysis_budget",
    }


def test_funnel_controls_sector_concentration_when_alternatives_exist() -> None:
    candidates = [_candidate(i, sector="Technology") for i in range(40)]
    candidates += [_candidate(100 + i, sector=f"Sector{i % 5}") for i in range(40)]

    selected, audit = select_deep_analysis_candidates(
        candidates,
        target_tickers=50,
        min_tickers=40,
        max_tickers=60,
        max_sector_share=0.20,
    )

    selected_sectors = [audit[ticker]["deep_analysis_sector"] for ticker in selected]
    assert selected_sectors.count("Technology") <= 10


def test_funnel_prefers_operable_preliminary_signals() -> None:
    candidates = [_candidate(i, sector=f"S{i % 5}", signal="WATCHLIST") for i in range(50)]
    candidates += [_candidate(100 + i, sector=f"S{i % 5}", signal="VETO") for i in range(50)]

    selected, _audit = select_deep_analysis_candidates(candidates, target_tickers=40)

    assert all(int(ticker[1:]) < 100 for ticker in selected)
