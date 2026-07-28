from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from engine import scanner_engine
from engine import technical_prefilter
from engine.scenario_engine import classify_ema20_extension_status


def _prices(value: float = 50.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [value] * 120,
            "high": [value + 1] * 120,
            "low": [value - 1] * 120,
            "close": [value] * 120,
            "volume": [1_000_000] * 120,
        },
        index=pd.bdate_range("2026-01-01", periods=120),
    )


def _evidence(
    *,
    daily_state: str = "MACD_HIST_POSITIVE_EXPANDING",
    weekly_state: str = "WEEKLY_MACD_HIST_IMPROVING",
    ema20_state: str = "HEALTHY",
) -> dict:
    return {
        "evidence_available": True,
        "technical_close": 50.0,
        "technical_ema20": 49.0,
        "technical_distance_ema20_pct": 0.02,
        "technical_distance_ema20_atr": 0.35,
        "technical_macd_hist": 0.30,
        "technical_macd_hist_change_1d": 0.10,
        "technical_macd_hist_two_day_rising": daily_state
        in {
            "MACD_HIST_POSITIVE_EXPANDING",
            "MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO",
        },
        "weekly_macd_histogram_state": weekly_state,
        "_daily_state": daily_state,
        "_ema20_state": ema20_state,
    }


def test_price_below_ema20_does_not_mark_overextension() -> None:
    assert (
        classify_ema20_extension_status(
            {
                "technical_distance_ema20_atr": -1.50,
                "technical_distance_ema20_pct": -0.04,
            }
        )
        == "HEALTHY"
    )


def test_price_above_ema20_marks_overextension() -> None:
    assert (
        classify_ema20_extension_status(
            {
                "technical_distance_ema20_atr": 1.60,
                "technical_distance_ema20_pct": 0.06,
            }
        )
        == "OVEREXTENDED"
    )


def test_daily_and_weekly_macd_must_pass_prefilter(monkeypatch) -> None:
    monkeypatch.setattr(
        technical_prefilter,
        "build_technical_evidence",
        lambda frame: _evidence(daily_state="MACD_HIST_DETERIORATING"),
    )
    monkeypatch.setattr(
        technical_prefilter,
        "classify_macd_histogram",
        lambda evidence: evidence["_daily_state"],
    )
    monkeypatch.setattr(
        technical_prefilter,
        "classify_ema20_extension_status",
        lambda evidence: evidence["_ema20_state"],
    )

    result = technical_prefilter.evaluate_technical_prefilter(_prices())

    assert result["technical_prefilter_status"] == "FAIL"
    assert result["daily_macd_prefilter_status"] == "FAIL"
    assert "daily_macd_macd_hist_deteriorating" in result["technical_prefilter_reason"]


def test_weekly_decelerating_fails_prefilter_even_when_daily_improves(monkeypatch) -> None:
    monkeypatch.setattr(
        technical_prefilter,
        "build_technical_evidence",
        lambda frame: _evidence(weekly_state="WEEKLY_MACD_HIST_DECELERATING"),
    )
    monkeypatch.setattr(
        technical_prefilter,
        "classify_macd_histogram",
        lambda evidence: evidence["_daily_state"],
    )
    monkeypatch.setattr(
        technical_prefilter,
        "classify_ema20_extension_status",
        lambda evidence: evidence["_ema20_state"],
    )

    result = technical_prefilter.evaluate_technical_prefilter(_prices())

    assert result["technical_prefilter_status"] == "FAIL"
    assert result["weekly_macd_prefilter_status"] == "FAIL"
    assert "weekly_macd_weekly_macd_hist_decelerating" in result["technical_prefilter_reason"]


def test_technical_prefilter_runs_before_metadata_and_skips_rejected(monkeypatch, tmp_path):
    screen = pd.DataFrame(
        [
            {"ticker": "PASS1", "price": 30.0},
            {"ticker": "FAIL1", "price": 30.0},
        ]
    )
    calls: list[tuple] = []

    monkeypatch.setattr(
        scanner_engine,
        "run_screeners",
        lambda config: SimpleNamespace(dataframe=screen),
    )

    def fake_validate(df, config, strict_metadata=False):
        calls.append(("validate", strict_metadata, tuple(df["ticker"])))
        return df.iloc[0:0].copy() if strict_metadata else df.copy()

    monkeypatch.setattr(scanner_engine, "validate_universe", fake_validate)
    monkeypatch.setattr(
        scanner_engine,
        "download_daily_prices",
        lambda tickers, **kwargs: {ticker: _prices(30.0) for ticker in tickers},
    )
    monkeypatch.setattr(scanner_engine, "add_all_indicators", lambda frame, config: frame)

    def fake_prefilter(frame):
        # The scanner iterates in ticker order and uses the same frame shape in this test.
        ticker = "PASS1" if len([c for c in calls if c[0] == "prefilter"]) == 0 else "FAIL1"
        calls.append(("prefilter", ticker))
        passed = ticker == "PASS1"
        return {
            "technical_prefilter_status": "PASS" if passed else "FAIL",
            "technical_prefilter_reason": "technical_prefilter_pass"
            if passed
            else "daily_macd_macd_hist_deteriorating",
            "daily_macd_prefilter_status": "PASS" if passed else "FAIL",
            "weekly_macd_prefilter_status": "PASS",
            "ema20_extension_prefilter_status": "PASS",
            "macd_histogram_state": "MACD_HIST_POSITIVE_EXPANDING"
            if passed
            else "MACD_HIST_DETERIORATING",
            "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_IMPROVING",
            "ema20_extension_status": "HEALTHY",
        }

    monkeypatch.setattr(scanner_engine, "evaluate_technical_prefilter", fake_prefilter)

    def fake_liquidity(ticker, frame, config, metadata):
        calls.append(("liquidity", ticker, bool(metadata)))
        return {
            "ticker": ticker,
            "price": 30.0,
            "avg_volume_20d": 1_000_000,
            "avg_volume_60d": 1_000_000,
            "dollar_volume_20d": 30_000_000,
            "dollar_volume_60d": 30_000_000,
            "liquidity_pass": True,
        }

    monkeypatch.setattr(scanner_engine, "compute_liquidity", fake_liquidity)

    enriched: list[str] = []

    def fake_enrich(df, config, stats=None):
        enriched.extend(df["ticker"].tolist())
        calls.append(("metadata", tuple(df["ticker"])))
        return df.copy()

    monkeypatch.setattr(scanner_engine, "enrich_metadata", fake_enrich)

    result = scanner_engine.run_scan(
        {"performance": {"scan_report_path": str(tmp_path / "scan_performance.json")}}
    )

    assert enriched == ["PASS1"]
    assert calls.index(("prefilter", "FAIL1")) < calls.index(("metadata", ("PASS1",)))
    assert ("metadata", ("FAIL1",)) not in calls
    assert not result.empty
    rejected = result[result["ticker"].eq("FAIL1")].iloc[0]
    assert rejected["signal"] == "AVOID"
    assert rejected["recommendation"] == "AVOID_FOR_NOW"
