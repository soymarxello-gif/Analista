from datetime import datetime, timedelta, timezone

from institutional.api import RunRequest, create_app
from institutional.models import AssetType, PriceBar, SecurityRecord


def test_api_exposes_health_and_versioned_read_contracts(tmp_path):
    app = create_app(tmp_path / "api.db", api_token="secret")
    paths = {route.path for route in app.routes}
    assert {
        "/health",
        "/v1/status",
        "/v1/ingest/live",
        "/v1/runs",
        "/v1/universe",
        "/v1/signals",
        "/v1/outcomes",
        "/v1/source-health",
        "/v1/context",
    } <= paths
    protected = [route for route in app.routes if route.path.startswith("/v1/")]
    assert all(route.dependencies for route in protected)
    app.state.institutional_store.close()


def test_run_api_returns_technical_selection_with_explicit_missing_context_warnings(tmp_path):
    now = datetime(2026, 7, 21, 20, tzinfo=timezone.utc)
    app = create_app(tmp_path / "api-context.db", api_token="secret")
    store = app.state.institutional_store
    store.put_security_records([
        SecurityRecord(
            "AAA", AssetType.COMMON_STOCK, "NASDAQ", "USD", True,
            now - timedelta(days=500), None, now - timedelta(days=500),
            None, "Technology", "Software", "AAA", "TEST",
        )
    ])
    bars = []
    for index in range(240):
        session = now - timedelta(days=239 - index)
        close = 100 + index * 0.035 + ((index % 12) - 6) * 0.35
        bars.append(PriceBar(
            "AAA", session, close - 0.3, close + 0.8, close - 0.8, close,
            1_000_000 + index * 1000, session + timedelta(hours=4), "TEST", "SIP", True,
        ))
    store.put_price_bars(bars)
    endpoint = next(route.endpoint for route in app.routes if route.path == "/v1/runs")

    payload = endpoint(RunRequest(as_of=now, refresh=False))

    assert payload["selection_policy"] == "TECHNICAL_SETUP_ONLY_CONTEXT_ADVISORY"
    assert payload["signal_count"] == 1
    signal = payload["signals"][0]
    assert signal["metadata"]["context_warnings"] == [
        "Sin datos macro", "Sin datos fundamentales", "Sin datos de opciones"
    ]
    assert signal["metadata"]["eligibility_warnings"] == ["stock_market_cap_unavailable"]
    assert signal["state"] != "DATA_BLOCKED"
    store.close()
