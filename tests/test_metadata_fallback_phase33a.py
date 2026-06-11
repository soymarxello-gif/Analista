from __future__ import annotations

import pandas as pd

from data.fundamentals_client import enrich_metadata
from engine.data_sources.metadata_fallback import StaticMetadataProvider, apply_metadata_fallback
from engine.data_sources.source_priority import FINVIZ, MARKETWATCH, YAHOO_FINANCE
from scoring.signal_classifier import classify_signal


def provider(source: str, records: dict[str, dict]):
    return StaticMetadataProvider(source, records)


def test_yahoo_valid_is_not_overwritten_by_fallback():
    row = apply_metadata_fallback(
        {
            "ticker": "AAA",
            "metadata_source": "yfinance",
            "sector": "Technology",
            "industry": "Software",
            "market_cap": 5_000_000_000,
        },
        providers=[
            provider(
                FINVIZ,
                {
                    "AAA": {
                        "sector": "Healthcare",
                        "industry": "Biotech",
                        "market_cap": 9_000_000_000,
                    }
                },
            )
        ],
    )

    assert row["sector"] == "Technology"
    assert row["industry"] == "Software"
    assert row["market_cap"] == 5_000_000_000
    assert row["sector_source"] == YAHOO_FINANCE
    assert row["industry_source"] == YAHOO_FINANCE
    assert row["market_cap_source"] == YAHOO_FINANCE
    assert row["metadata_fallback_used"] is False
    assert row["metadata_confidence"] == "HIGH"


def test_yahoo_missing_finviz_valid_fills_sector_and_industry():
    row = apply_metadata_fallback(
        {"ticker": "BBB", "metadata_source": "yfinance", "market_cap": 6_000_000_000},
        providers=[
            provider(
                FINVIZ,
                {"BBB": {"sector": "Industrials", "industry": "Aerospace"}},
            )
        ],
    )

    assert row["sector"] == "Industrials"
    assert row["industry"] == "Aerospace"
    assert row["sector_source"] == FINVIZ
    assert row["industry_source"] == FINVIZ
    assert row["market_cap_source"] == YAHOO_FINANCE
    assert row["metadata_fallback_used"] is True
    assert row["metadata_fallback_sources"] == FINVIZ


def test_finviz_missing_marketwatch_valid_fills_sector_and_industry():
    row = apply_metadata_fallback(
        {"ticker": "CCC", "metadata_source": "yfinance", "market_cap": 7_000_000_000},
        providers=[
            provider(FINVIZ, {"CCC": {}}),
            provider(
                MARKETWATCH,
                {"CCC": {"sector": "Healthcare", "industry": "Medical Devices"}},
            ),
        ],
    )

    assert row["sector"] == "Healthcare"
    assert row["industry"] == "Medical Devices"
    assert row["sector_source"] == MARKETWATCH
    assert row["industry_source"] == MARKETWATCH
    assert row["metadata_fallback_used"] is True
    assert row["metadata_fallback_sources"] == MARKETWATCH
    assert "FINVIZ:MISSING" in row["metadata_fallback_notes"]


def test_all_sources_missing_keeps_missing_and_marks_low_or_unknown_confidence():
    row = apply_metadata_fallback(
        {"ticker": "DDD", "metadata_source": "yfinance"},
        providers=[
            provider(FINVIZ, {"DDD": {}}),
            provider(MARKETWATCH, {"DDD": {}}),
        ],
    )

    assert row.get("sector") is None
    assert row["sector_source"] == "MISSING"
    assert row["industry_source"] == "MISSING"
    assert row["market_cap_source"] == "MISSING"
    assert row["metadata_fallback_used"] is False
    assert row["metadata_fallback_sources"] == ""
    assert row["metadata_confidence"] in {"LOW", "UNKNOWN"}
    assert "sector:MISSING_ALL_SOURCES" in row["metadata_fallback_notes"]


def test_enrich_metadata_row_uses_fallback_traceability(monkeypatch):
    def fake_fetch(ticker, config):
        return {
            "ticker": ticker,
            "metadata_source": "yfinance",
            "sector": None,
            "industry": None,
            "market_cap": 8_000_000_000,
        }

    monkeypatch.setattr("data.fundamentals_client.fetch_ticker_metadata", fake_fetch)
    monkeypatch.setattr(
        "data.fundamentals_client.build_metadata_providers",
        lambda _config: [provider(FINVIZ, {"EEE": {"sector": "Technology", "industry": "Semiconductors"}})],
    )

    out = enrich_metadata(pd.DataFrame([{"ticker": "EEE"}]), {"fundamentals": {"metadata_enrichment": {"enabled": True}}})
    record = out.iloc[0].to_dict()

    assert record["sector"] == "Technology"
    assert record["industry"] == "Semiconductors"
    assert record["sector_source"] == FINVIZ
    assert record["industry_source"] == FINVIZ
    assert record["metadata_fallback_used"] is True


def _trigger_row(**overrides):
    row = {
        "final_score": 95,
        "rr": 3.0,
        "trigger_confirmed": True,
        "liquidity_pass": True,
        "trend_score": 0.9,
        "setup_type": "BREAKOUT",
        "market_cap": 5_000_000_000,
        "price": 50,
        "quote_type": "EQUITY",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
    }
    row.update(overrides)
    return row


def test_metadata_fallback_cannot_confirm_trigger_when_quote_status_not_valid():
    cfg = {"signal_thresholds": {"trigger_confirmed": {"min_score": 85, "min_rr": 2.0, "require_trigger": True}}}
    row = _trigger_row(quote_status="MISSING", execution_quote_quality="HIGH", metadata_fallback_used=True)

    signal, _veto = classify_signal(row, cfg)

    assert signal != "TRIGGER_CONFIRMED"


def test_metadata_fallback_cannot_confirm_trigger_when_execution_quote_quality_low():
    cfg = {"signal_thresholds": {"trigger_confirmed": {"min_score": 85, "min_rr": 2.0, "require_trigger": True}}}
    row = _trigger_row(execution_quote_quality="LOW", metadata_fallback_used=True)

    signal, _veto = classify_signal(row, cfg)

    assert signal != "TRIGGER_CONFIRMED"
