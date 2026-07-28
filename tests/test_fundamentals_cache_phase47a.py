from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from data import fundamentals_client


def _config() -> dict:
    return {
        "data_sources": {
            "cache_ttl_minutes": {
                "fundamentals": 10080,
                "earnings": 720,
            },
            "metadata_fallback": {"enabled": False},
        }
    }


def _stale_first_config() -> dict:
    cfg = _config()
    cfg["fundamentals"] = {
        "metadata_enrichment": {
            "enabled": True,
            "prefer_stale_cache": True,
            "max_network_queries_per_run": 1,
        }
    }
    return cfg


def _write_cache(tmp_path, ticker: str, *, fundamentals_age: int, earnings_age: int):
    cache_dir = tmp_path / "cache" / "fundamentals"
    cache_dir.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    payload = {
        "ticker": ticker,
        "sector": "Technology",
        "market_cap": 5_000_000_000,
        "earnings_date": "2026-08-01",
        "_fundamentals_fetched_at": (
            now - timedelta(minutes=fundamentals_age)
        ).isoformat(),
        "_earnings_fetched_at": (now - timedelta(minutes=earnings_age)).isoformat(),
    }
    (cache_dir / f"{ticker}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_fresh_fundamentals_and_earnings_do_not_use_network(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_cache(tmp_path, "AAA", fundamentals_age=60, earnings_age=60)

    class FailYF:
        def Ticker(self, ticker):
            raise AssertionError("network should not be used")

    monkeypatch.setattr(fundamentals_client, "yf", FailYF())

    result = fundamentals_client.fetch_ticker_metadata("AAA", _config())

    assert result["sector"] == "Technology"
    assert result["fundamentals_cache_status"] == "HIT"
    assert result["earnings_cache_status"] == "HIT"


def test_fresh_fundamentals_refresh_only_stale_earnings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_cache(tmp_path, "AAA", fundamentals_age=60, earnings_age=800)
    calls = {"earnings": 0}

    class FakeTicker:
        def get_earnings_dates(self, limit=8):
            calls["earnings"] += 1
            return None

        @property
        def calendar(self):
            return {}

        def get_info(self):
            raise AssertionError("fundamentals should remain cached")

    class FakeYF:
        def Ticker(self, ticker):
            return FakeTicker()

    monkeypatch.setattr(fundamentals_client, "yf", FakeYF())

    result = fundamentals_client.fetch_ticker_metadata("AAA", _config())

    assert calls["earnings"] == 1
    assert result["fundamentals_cache_status"] == "HIT"
    assert result["earnings_cache_status"] == "REFRESHED"
    assert result["fundamentals_cache_age_minutes"] >= 59


def test_network_failure_uses_auditable_stale_cache(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_cache(tmp_path, "AAA", fundamentals_age=11000, earnings_age=800)

    class FakeTicker:
        def get_info(self):
            raise RuntimeError("offline")

        @property
        def info(self):
            raise RuntimeError("offline")

        def get_earnings_dates(self, limit=8):
            raise RuntimeError("offline")

        @property
        def calendar(self):
            raise RuntimeError("offline")

    class FakeYF:
        def Ticker(self, ticker):
            return FakeTicker()

    monkeypatch.setattr(fundamentals_client, "yf", FakeYF())

    result = fundamentals_client.fetch_ticker_metadata("AAA", _config())

    assert result["sector"] == "Technology"
    assert result["fundamentals_cache_status"] == "STALE_FALLBACK"
    assert result["earnings_cache_status"] == "STALE_FALLBACK"
    assert "offline" in result["fundamental_warning"]


def test_prefer_stale_cache_avoids_network_for_expired_metadata(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_cache(tmp_path, "AAA", fundamentals_age=11000, earnings_age=800)

    class FailYF:
        def Ticker(self, ticker):
            raise AssertionError("stale cache should avoid network")

    monkeypatch.setattr(fundamentals_client, "yf", FailYF())

    result = fundamentals_client.fetch_ticker_metadata("AAA", _stale_first_config())

    assert result["sector"] == "Technology"
    assert result["fundamentals_cache_status"] == "STALE_FALLBACK"
    assert result["earnings_cache_status"] == "STALE_FALLBACK"
    assert "cache stale usado" in result["fundamental_warning"]


def test_enrich_metadata_disables_network_after_query_limit(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[str, bool]] = []

    def fake_fetch(ticker, config, fallback_providers=None):
        network_enabled = (
            config.get("fundamentals", {})
            .get("metadata_enrichment", {})
            .get("network_enabled", True)
        )
        calls.append((ticker, bool(network_enabled)))
        return {
            "ticker": ticker,
            "sector": "Technology",
            "metadata_source": "yfinance" if network_enabled else "none",
            "fundamentals_cache_status": "FRESH_NETWORK" if network_enabled else "NETWORK_SKIPPED",
            "earnings_cache_status": "NETWORK_SKIPPED",
        }

    monkeypatch.setattr(fundamentals_client, "fetch_ticker_metadata", fake_fetch)
    out = fundamentals_client.enrich_metadata(
        fundamentals_client.pd.DataFrame([{"ticker": "AAA"}, {"ticker": "BBB"}, {"ticker": "CCC"}]),
        _stale_first_config(),
        stats={},
    )

    assert calls == [("AAA", True), ("BBB", False), ("CCC", False)]
    assert len(out) == 3
