import json
from datetime import datetime, timezone

from data import fundamentals_client as client


def test_extract_quote_context_prefers_session_specific_timestamp():
    info = {
        "marketState": "POSTPOST",
        "regularMarketTime": 100,
        "postMarketTime": 200,
    }
    result = client._extract_quote_context(
        info,
        fetched_at=datetime(2026, 7, 18, 22, 0, tzinfo=timezone.utc),
    )
    assert result["market_session"] == "POST"
    assert result["quote_timestamp"] == 200.0
    assert result["regular_market_time"] == 100.0
    assert result["quote_timestamp_source"] == "yahoo_quote_summary"


def test_extract_quote_context_marks_unknown_when_yahoo_has_no_time():
    result = client._extract_quote_context(
        {"marketState": "CLOSED"},
        fetched_at=datetime(2026, 7, 18, 22, 0, tzinfo=timezone.utc),
    )
    assert result["market_session"] == "CLOSED"
    assert result["quote_timestamp"] is None
    assert result["quote_timestamp_source"] is None


def test_cache_rejects_legacy_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "CACHE_DIR", tmp_path)
    path = tmp_path / "TEST.json"
    path.write_text(json.dumps({"ticker": "TEST"}), encoding="utf-8")
    assert client._load_cache("TEST", 60) is None


def test_cache_roundtrip_preserves_version_and_data(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "CACHE_DIR", tmp_path)
    client._save_cache("TEST", {"ticker": "TEST", "quote_timestamp": 123.0})
    result = client._load_cache("TEST", 60)
    assert result is not None
    assert result["ticker"] == "TEST"
    assert result["quote_timestamp"] == 123.0
    assert result["cache_schema_version"] == client.CACHE_SCHEMA_VERSION
    assert result["cache_saved_at"]
