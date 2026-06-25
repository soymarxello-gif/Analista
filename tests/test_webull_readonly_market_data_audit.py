from __future__ import annotations

from pathlib import Path

from tools import webull_readonly_market_data_audit as audit


def _fake_request(url: str, headers: dict[str, str], timeout_seconds: int):
    assert "x-app-key" in headers
    assert "x-signature" in headers
    assert timeout_seconds == 3
    if "snapshot" in url:
        return 200, {"data": [{"symbol": "AAPL", "lastPrice": "200.12"}]}
    if "quotes" in url:
        return 200, {"symbol": "AAPL", "bid": "200.10", "ask": "200.15"}
    if "bars" in url:
        return 200, {"bars": [{"close": "200.12"}]}
    raise AssertionError(f"unexpected url: {url}")


def test_missing_credentials_returns_warn_without_traceback(monkeypatch) -> None:
    for name in ["WEBULL_APP_KEY", "WEBULL_API_KEY", "WEBULL_APP_SECRET", "WEBULL_API_SECRET"]:
        monkeypatch.delenv(name, raising=False)

    result = audit.run_audit(request_fn=_fake_request)

    assert result["status"] == "WARN"
    assert result["credentials_present"] is False
    assert "missing_webull_credentials" in result["issues"]
    assert result["execution_enabled"] is False
    assert result["execution_endpoint_called"] is False


def test_webull_market_data_passes_with_mocked_responses(monkeypatch) -> None:
    monkeypatch.setenv("WEBULL_APP_KEY", "KEY123456")
    monkeypatch.setenv("WEBULL_APP_SECRET", "SECRET123456")

    result = audit.run_audit(symbol="AAPL", timeout_seconds=3, request_fn=_fake_request)

    assert result["status"] == "PASS"
    assert result["credentials_present"] is True
    assert len(result["endpoint_checks"]) == 3
    assert all(check["status"] == "PASS" for check in result["endpoint_checks"])
    assert result["provider"]["source"] == "WEBULL_OPENAPI"
    assert result["execution_enabled"] is False


def test_webull_401_is_credentials_warning_not_route_failure(monkeypatch) -> None:
    monkeypatch.setenv("WEBULL_APP_KEY", "KEY123456")
    monkeypatch.setenv("WEBULL_APP_SECRET", "SECRET123456")

    def fake_401(url: str, headers: dict[str, str], timeout_seconds: int):
        return 401, {"message": "unauthorized"}

    result = audit.run_audit(symbol="AAPL", timeout_seconds=3, request_fn=fake_401)

    assert result["status"] == "WARN"
    assert "webull_credentials_invalid_or_signature_rejected" in result["issues"]
    assert "webull_endpoint_unavailable" not in result["issues"]
    assert result["execution_enabled"] is False


def test_save_reports_generates_json_and_markdown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WEBULL_APP_KEY", "KEY123456")
    monkeypatch.setenv("WEBULL_APP_SECRET", "SECRET123456")
    result = audit.run_audit(symbol="AAPL", timeout_seconds=3, request_fn=_fake_request)

    json_out = tmp_path / "webull.json"
    md_out = tmp_path / "webull.md"
    audit.save_reports(result, json_out=json_out, markdown_out=md_out)

    assert json_out.exists()
    assert md_out.exists()
    assert "Webull read-only market data audit" in md_out.read_text(encoding="utf-8")


def test_source_does_not_call_execution_endpoints() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8")

    assert 'method="GET"' in source
    assert "/v2/orders" not in source
    assert "submit_order" not in source
    assert "place_order" not in source
    assert "send_order" not in source
    assert "TRIGGER_CONFIRMED" not in source
    assert "BUY_SETUP_ACTIVE" not in source
