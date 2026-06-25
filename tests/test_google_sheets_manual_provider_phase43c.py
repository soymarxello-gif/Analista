from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from engine.data_sources import analysis_quotes
from engine.data_sources.google_sheets_manual import (
    GOOGLE_SHEETS_SOURCE,
    clear_google_sheets_cache,
    load_google_sheets_records,
    parse_google_sheets_csv,
    record_to_analysis_quote,
)
from engine.data_sources.metadata_fallback import apply_metadata_fallback, build_metadata_providers
from tools.source_coverage_audit import build_source_coverage_report


def _csv(updated_at: str) -> str:
    return (
        "ticker,source,updated_at,confidence,price,bid,ask,sector,industry,market_cap,earnings_date\n"
        f"AAPL,GOOGLEFINANCE,{updated_at},MEDIUM,200.2,200.1,200.3,Technology,"
        "Consumer Electronics,3000000000000,2026-07-30\n"
    )


def test_google_sheets_parser_keeps_auditable_ticker_records() -> None:
    parsed = parse_google_sheets_csv(_csv(datetime.now(timezone.utc).isoformat()))

    assert parsed["status"] == "PASS"
    assert parsed["valid_rows"] == 1
    record = parsed["records"]["AAPL"]
    assert record["sector"] == "Technology"
    assert record["market_cap"] == 3_000_000_000_000
    assert record["confidence"] == "MEDIUM"
    assert record["usable"] is True


def test_published_sheet_fixture_with_preamble_yields_189_numeric_records() -> None:
    updated_at = datetime.now(timezone.utc).isoformat()
    rows = [
        f"T{i:03d},GOOGLEFINANCE,{updated_at},LOW,{100 + i}.25,,,,,,\"{1_000_000_000 + i:,}\""
        for i in range(189)
    ]
    text = (
        "Publicar_CSV - contrato de datos para Analista,,,,,,,,,,\n"
        "No renombrar columnas.,,,,,,,,,,\n"
        ",,,,,,,,,,\n"
        "ticker,source,updated_at,confidence,price,bid,ask,sector,industry,earnings_date,market_cap\n"
        + "\n".join(rows)
        + "\n"
    )

    parsed = parse_google_sheets_csv(text)

    assert parsed["header_row"] == 4
    assert parsed["valid_rows"] == 189
    assert parsed["records"]["T000"]["price"] == 100.25
    assert parsed["records"]["T188"]["market_cap"] == 1_000_000_188


def test_stale_google_sheets_rows_are_audited_but_not_usable() -> None:
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    parsed = parse_google_sheets_csv(_csv(old), max_stale_minutes=60)

    assert parsed["status"] == "WARN"
    assert parsed["stale_rows"] == 1
    assert parsed["records"] == {}
    assert "stale_rows" in parsed["issues"]


def test_google_sheets_metadata_fills_only_missing_yahoo_fields(monkeypatch) -> None:
    records = parse_google_sheets_csv(_csv(datetime.now(timezone.utc).isoformat()))["records"]

    monkeypatch.setattr(
        "engine.data_sources.google_sheets_manual.load_google_sheets_records",
        lambda *args, **kwargs: {"status": "PASS", "records": records, "issues": []},
    )
    config = {
        "data_sources": {
            "providers": {
                "google_sheets_manual": {
                    "enabled": True,
                    "published_csv_url": "https://example.test/sheet.csv",
                }
            }
        }
    }
    providers = build_metadata_providers(config)
    out = apply_metadata_fallback(
        {
            "ticker": "AAPL",
            "metadata_source": "yfinance",
            "sector": "Yahoo Technology",
            "industry": None,
            "market_cap": None,
        },
        config,
        providers,
    )

    assert out["sector"] == "Yahoo Technology"
    assert out["sector_source"] == "YAHOO_FINANCE"
    assert out["industry"] == "Consumer Electronics"
    assert out["industry_source"] == "GOOGLE_SHEETS_MANUAL"
    assert out["market_cap"] == 3_000_000_000_000
    assert out["market_cap_source"] == "GOOGLE_SHEETS_MANUAL"
    assert out["metadata_fallback_used"] is True


def test_google_sheets_quote_is_used_after_alpaca_without_execution_changes(monkeypatch) -> None:
    record = parse_google_sheets_csv(_csv(datetime.now(timezone.utc).isoformat()))["records"]["AAPL"]
    monkeypatch.setattr(analysis_quotes, "alpaca_credentials_present", lambda: False)
    monkeypatch.setattr(
        analysis_quotes,
        "load_google_sheets_records",
        lambda *args, **kwargs: {"status": "PASS", "records": {"AAPL": record}, "issues": []},
    )
    config = {
        "data_sources": {
            "analysis_quotes": {"enabled": True, "use_google_sheets_manual": True},
            "providers": {
                "alpaca_iex": {"enabled": True},
                "google_sheets_manual": {
                    "enabled": True,
                    "published_csv_url": "https://example.test/sheet.csv",
                },
            },
        }
    }

    fallbacks = analysis_quotes.build_analysis_quote_fallbacks(["AAPL"], config)
    quote = fallbacks["AAPL"]
    assert quote["analysis_quote_source"] == GOOGLE_SHEETS_SOURCE

    row = {
        "ticker": "AAPL",
        "signal": "WATCHLIST",
        "recommendation": "RECHECK_LIVE_QUOTE",
        "quote_status": "MISSING",
        "execution_quote_quality": "LOW",
        "analysis_price": None,
        "analysis_bid": None,
        "analysis_ask": None,
        "secondary_data_sources_used": "",
    }
    out = analysis_quotes.apply_analysis_quote_fallback(row, quote)

    assert out["analysis_price"] == 200.2
    assert out["analysis_quote_freshness"] == "DELAYED_20_MIN"
    assert out["quote_status"] == "MISSING"
    assert out["execution_quote_quality"] == "LOW"
    assert out["signal"] == "WATCHLIST"
    assert out["recommendation"] == "RECHECK_LIVE_QUOTE"


def test_alpaca_remains_higher_priority_than_google_sheets(monkeypatch) -> None:
    monkeypatch.setattr(analysis_quotes, "alpaca_credentials_present", lambda: True)
    monkeypatch.setattr(
        analysis_quotes,
        "fetch_alpaca_iex_analysis_quotes",
        lambda *args, **kwargs: {
            "AAPL": {
                "analysis_price": 201.0,
                "analysis_quote_source": "ALPACA_IEX_READ_ONLY",
            }
        },
    )
    monkeypatch.setattr(
        analysis_quotes,
        "load_google_sheets_records",
        lambda *args, **kwargs: {
            "status": "PASS",
            "records": {
                "AAPL": {
                    "ticker": "AAPL",
                    "price": 200.0,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "confidence": "MEDIUM",
                }
            },
        },
    )
    config = {
        "data_sources": {
            "analysis_quotes": {"enabled": True},
            "providers": {
                "alpaca_iex": {"enabled": True},
                "google_sheets_manual": {
                    "enabled": True,
                    "published_csv_url": "https://example.test/sheet.csv",
                },
            },
        }
    }

    result = analysis_quotes.build_analysis_quote_fallbacks(["AAPL"], config)

    assert result["AAPL"]["analysis_price"] == 201.0
    assert result["AAPL"]["analysis_quote_source"] == "ALPACA_IEX_READ_ONLY"


def test_google_sheets_is_not_limited_by_alpaca_max_tickers(monkeypatch) -> None:
    tickers = [f"T{i:03d}" for i in range(100)]
    monkeypatch.setattr(analysis_quotes, "alpaca_credentials_present", lambda: True)
    monkeypatch.setattr(
        analysis_quotes,
        "fetch_alpaca_iex_analysis_quotes",
        lambda selected, **kwargs: {
            ticker: {
                "analysis_price": 200.0,
                "analysis_quote_source": "ALPACA_IEX_READ_ONLY",
            }
            for ticker in selected
        },
    )
    monkeypatch.setattr(
        analysis_quotes,
        "load_google_sheets_records",
        lambda *args, **kwargs: {
            "status": "PASS",
            "records": {
                ticker: {
                    "ticker": ticker,
                    "price": 100.0,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "confidence": "LOW",
                }
                for ticker in tickers
            },
        },
    )
    config = {
        "data_sources": {
            "analysis_quotes": {"enabled": True, "max_tickers_per_run": 75},
            "providers": {
                "alpaca_iex": {"enabled": True},
                "google_sheets_manual": {
                    "enabled": True,
                    "published_csv_url": "https://example.test/sheet.csv",
                },
            },
        }
    }

    result = analysis_quotes.build_analysis_quote_fallbacks(tickers, config)

    assert len(result) == 100
    assert result["T074"]["analysis_quote_source"] == "ALPACA_IEX_READ_ONLY"
    assert result["T075"]["analysis_quote_source"] == GOOGLE_SHEETS_SOURCE
    assert result["T099"]["analysis_quote_source"] == GOOGLE_SHEETS_SOURCE


def test_google_sheets_loader_reuses_in_process_cache() -> None:
    clear_google_sheets_cache()
    calls = 0
    updated_at = datetime.now(timezone.utc).isoformat()

    def fake_request(url: str, timeout_seconds: int):
        nonlocal calls
        calls += 1
        return 200, _csv(updated_at)

    first = load_google_sheets_records(
        "https://example.test/sheet.csv",
        request_fn=fake_request,
    )
    second = load_google_sheets_records(
        "https://example.test/sheet.csv",
        request_fn=fake_request,
    )

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert calls == 1


def test_source_coverage_exposes_delayed_source_and_freshness() -> None:
    report = build_source_coverage_report(
        pd.DataFrame(
            [
                {
                    "ticker": "AAPL",
                    "analysis_price": 200.2,
                    "analysis_bid": 200.1,
                    "analysis_ask": 200.3,
                    "analysis_quote_source": GOOGLE_SHEETS_SOURCE,
                    "analysis_quote_freshness": "DELAYED_20_MIN",
                    "analysis_quote_confidence": "MEDIUM",
                    "secondary_data_sources_used": GOOGLE_SHEETS_SOURCE,
                }
            ]
        )
    )

    assert report["analysis_quotes"]["analysis_quote_source"][GOOGLE_SHEETS_SOURCE] == 1
    assert report["analysis_quotes"]["analysis_quote_freshness"]["DELAYED_20_MIN"] == 1
    assert report["missing_rates"]["analysis_price"] == 0.0
