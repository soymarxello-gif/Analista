from __future__ import annotations

from engine.data_sources.provider_contract import (
    ProviderResponse,
    disabled_provider_response,
    normalize_provider_response,
)


def test_provider_disabled_response_is_controlled() -> None:
    response = disabled_provider_response("webull", source="WEBULL_OPENAPI")
    data = response.to_dict()

    assert data["provider_name"] == "webull"
    assert data["status"] == "DISABLED"
    assert data["source"] == "WEBULL_OPENAPI"
    assert data["data_freshness"] == "UNKNOWN"
    assert data["confidence"] == "UNKNOWN"
    assert data["notes"]


def test_provider_response_normalizes_invalid_choices() -> None:
    data = ProviderResponse(
        provider_name="custom",
        status="BOGUS",
        data_freshness="STALE",
        confidence="CERTAIN",
    ).to_dict()

    assert data["status"] == "WARN"
    assert data["data_freshness"] == "UNKNOWN"
    assert data["confidence"] == "UNKNOWN"


def test_normalize_provider_response_keeps_fields_and_errors() -> None:
    data = normalize_provider_response(
        {
            "provider_name": "google_sheets_manual",
            "status": "PASS",
            "source": "GOOGLE_SHEETS_MANUAL_CSV",
            "data_freshness": "DELAYED_20_MIN",
            "confidence": "LOW",
            "fields": {"rows": 2},
            "errors": ["stale_rows"],
            "notes": ["manual source"],
        }
    )

    assert data["status"] == "PASS"
    assert data["data_freshness"] == "DELAYED_20_MIN"
    assert data["confidence"] == "LOW"
    assert data["fields"]["rows"] == 2
    assert data["errors"] == ["stale_rows"]
