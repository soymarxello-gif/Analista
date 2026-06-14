from __future__ import annotations

from pathlib import Path

from tools import alpaca_readonly_connectivity_audit as audit


def _fake_request(url: str, headers: dict[str, str], timeout_seconds: int):
    assert headers["APCA-API-KEY-ID"] == "KEY123456"
    assert headers["APCA-API-SECRET-KEY"] == "SECRET123456"
    assert timeout_seconds == 3
    if url.endswith("/v2/account"):
        return 200, {
            "id": "account-id",
            "account_number": "PA123456789",
            "status": "ACTIVE",
            "currency": "USD",
            "trading_blocked": False,
            "account_blocked": False,
            "transfers_blocked": False,
            "pattern_day_trader": False,
            "portfolio_value": "100000",
        }
    if url.endswith("/v2/clock"):
        return 200, {
            "timestamp": "2026-06-14T12:00:00Z",
            "is_open": False,
            "next_open": "2026-06-15T13:30:00Z",
            "next_close": "2026-06-15T20:00:00Z",
        }
    if "/v2/stocks/AAPL/quotes/latest?feed=iex" in url:
        return 200, {
            "symbol": "AAPL",
            "quote": {
                "bp": 199.1,
                "ap": 199.2,
                "t": "2026-06-14T12:00:00Z",
            },
        }
    raise AssertionError(f"unexpected url: {url}")


def test_missing_credentials_returns_warn_without_traceback(monkeypatch) -> None:
    for name in ["APCA_API_KEY_ID", "ALPACA_API_KEY_ID", "APCA_API_SECRET_KEY", "ALPACA_API_SECRET_KEY"]:
        monkeypatch.delenv(name, raising=False)

    result = audit.run_audit(request_fn=_fake_request)

    assert result["status"] == "WARN"
    assert result["credentials_present"] is False
    assert "missing_alpaca_credentials" in result["issues"]
    assert result["orders_endpoint_called"] is False
    assert result["execution_enabled"] is False


def test_account_clock_and_iex_quote_pass_with_mocked_responses(monkeypatch) -> None:
    monkeypatch.setenv("APCA_API_KEY_ID", "KEY123456")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "SECRET123456")

    result = audit.run_audit(symbol="AAPL", timeout_seconds=3, request_fn=_fake_request)

    assert result["status"] == "PASS"
    assert result["credentials_present"] is True
    assert result["account_check"]["status"] == "PASS"
    assert result["clock_check"]["status"] == "PASS"
    assert result["iex_quote_check"]["status"] == "PASS"
    assert result["account_summary"]["status"] == "ACTIVE"
    assert result["iex_quote_summary"]["feed"] == "iex"
    assert result["iex_quote_summary"]["bid_price_present"] is True
    assert result["iex_quote_summary"]["ask_price_present"] is True


def test_data_failure_is_warn_not_execution(monkeypatch) -> None:
    monkeypatch.setenv("APCA_API_KEY_ID", "KEY123456")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "SECRET123456")

    def fake_request(url: str, headers: dict[str, str], timeout_seconds: int):
        if "quotes/latest" in url:
            return 403, {"code": "subscription", "message": "feed unavailable"}
        return _fake_request(url, headers, timeout_seconds)

    result = audit.run_audit(symbol="AAPL", timeout_seconds=3, request_fn=fake_request)

    assert result["status"] == "WARN"
    assert "iex_quote_check_failed" in result["issues"]
    assert result["orders_endpoint_called"] is False
    assert result["execution_enabled"] is False


def test_save_reports_generates_json_and_markdown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APCA_API_KEY_ID", "KEY123456")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "SECRET123456")
    result = audit.run_audit(symbol="AAPL", timeout_seconds=3, request_fn=_fake_request)

    json_out = tmp_path / "alpaca.json"
    md_out = tmp_path / "alpaca.md"
    audit.save_reports(result, json_out=json_out, markdown_out=md_out)

    assert json_out.exists()
    assert md_out.exists()
    text = md_out.read_text(encoding="utf-8")
    assert "Alpaca read-only connectivity audit" in text
    assert "No real order" in text


def test_source_does_not_call_execution_endpoints() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8")

    assert 'method="GET"' in source
    assert "/v2/orders" not in source
    assert "submit_order" not in source
    assert "place_order" not in source
    assert "send_order" not in source
    assert "buy_order" not in source
    assert "sell_order" not in source
    assert "TRIGGER_CONFIRMED" not in source
    assert "BUY_SETUP_ACTIVE" not in source
