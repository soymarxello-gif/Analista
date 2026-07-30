from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import yaml

from engine import scanner_engine


def _prices(value: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [value] * 70,
            "high": [value + 1] * 70,
            "low": [value - 1] * 70,
            "close": [value] * 70,
            "volume": [1_000_000] * 70,
        },
        index=pd.date_range("2026-01-01", periods=70, freq="D"),
    )


def test_liquidity_funnel_runs_before_metadata_and_skips_rejected_tickers(
    monkeypatch, tmp_path
):
    calls: list[object] = []
    screen = pd.DataFrame(
        [
            {"ticker": "LIQUID", "price": 30.0},
            {"ticker": "THIN", "price": 30.0},
        ]
    )

    monkeypatch.setattr(
        scanner_engine,
        "run_screeners",
        lambda config: SimpleNamespace(dataframe=screen),
    )

    validation_calls = {"count": 0}

    def fake_validate(df, config, strict_metadata=False):
        validation_calls["count"] += 1
        calls.append(("validate", strict_metadata, tuple(df["ticker"])))
        if strict_metadata:
            return df.iloc[0:0].copy()
        return df.copy()

    monkeypatch.setattr(scanner_engine, "validate_universe", fake_validate)

    def fake_download(tickers, **kwargs):
        calls.append(("prices", tuple(tickers)))
        return {ticker: _prices(30.0) for ticker in tickers}

    monkeypatch.setattr(scanner_engine, "download_daily_prices", fake_download)
    monkeypatch.setattr(
        scanner_engine,
        "add_all_indicators",
        lambda frame, config: frame,
    )
    monkeypatch.setattr(
        scanner_engine,
        "evaluate_technical_prefilter",
        lambda frame: {
            "technical_prefilter_status": "PASS",
            "technical_prefilter_reason": "technical_prefilter_pass",
            "daily_macd_prefilter_status": "PASS",
            "weekly_macd_prefilter_status": "PASS",
            "ema20_extension_prefilter_status": "PASS",
        },
    )

    def fake_liquidity(ticker, frame, config, metadata):
        calls.append(("liquidity", ticker, bool(metadata)))
        passed = ticker == "LIQUID"
        return {
            "ticker": ticker,
            "price": 30.0,
            "avg_volume_20d": 1_000_000,
            "avg_volume_60d": 1_000_000,
            "dollar_volume_20d": 30_000_000 if passed else 1_000_000,
            "dollar_volume_60d": 30_000_000 if passed else 1_000_000,
            "liquidity_pass": passed,
        }

    monkeypatch.setattr(scanner_engine, "compute_liquidity", fake_liquidity)

    enriched: list[str] = []

    def fake_enrich(df, config, stats=None):
        enriched.extend(df["ticker"].tolist())
        calls.append(("metadata", tuple(df["ticker"])))
        return df.copy()

    monkeypatch.setattr(scanner_engine, "enrich_metadata", fake_enrich)

    report_path = tmp_path / "scan_performance.json"
    result = scanner_engine.run_scan(
        {"performance": {"scan_report_path": str(report_path)}}
    )

    assert result["ticker"].tolist() == ["THIN"]
    assert result.iloc[0]["technical_analysis_lane"] == "REJECT_RISK"
    assert enriched == ["LIQUID"]
    assert calls.index(("prices", ("LIQUID", "THIN"))) < calls.index(
        ("metadata", ("LIQUID",))
    )
    assert ("metadata", ("THIN",)) not in calls
    assert validation_calls["count"] == 2
    assert report_path.exists()


def test_deep_analysis_has_no_minimum_quota_and_keeps_a_safety_ceiling() -> None:
    with open("config.yaml", "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    funnel = config["deep_analysis"]["candidate_funnel"]
    assert funnel["target_tickers"] == 0
    assert funnel["min_tickers"] == 0
    assert funnel["max_tickers"] >= 1000
