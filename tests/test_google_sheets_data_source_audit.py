from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tools import google_sheets_data_source_audit as audit


def test_missing_google_sheets_url_returns_warn() -> None:
    result = audit.run_audit(csv_url="")

    assert result["status"] == "WARN"
    assert result["csv_url_present"] is False
    assert "missing_google_sheets_csv_url" in result["issues"]
    assert result["execution_enabled"] is False


def test_valid_google_sheets_csv_normalizes_fields() -> None:
    updated_at = datetime.now(timezone.utc).isoformat()
    text = (
        "ticker,source,updated_at,confidence,price,bid,ask,put_call_ratio,notes\n"
        f"AAPL,GOOGLEFINANCE,{updated_at},LOW,200.123,200.1,200.2,0.8,manual\n"
    )

    parsed = audit.parse_published_csv(text, max_stale_minutes=1440)

    assert parsed["status"] == "PASS"
    assert parsed["rows"] == 1
    assert parsed["valid_rows"] == 1
    assert "price" in parsed["optional_columns_present"]
    assert parsed["sample_rows"][0]["ticker"] == "AAPL"


def test_google_sheets_csv_detects_contract_header_after_preamble() -> None:
    updated_at = datetime.now(timezone.utc).isoformat()
    text = (
        "Publicar_CSV - contrato de datos para Analista,,,,\n"
        "No renombrar columnas.,,,,\n"
        ",,,,\n"
        "ticker,source,updated_at,confidence,price\n"
        f"AAPL,GOOGLEFINANCE,{updated_at},LOW,200.25\n"
    )

    parsed = audit.parse_published_csv(text)

    assert parsed["status"] == "PASS"
    assert parsed["header_row"] == 4
    assert parsed["ignored_preamble_rows"] == 3
    assert parsed["header_detected"] is True
    assert parsed["valid_rows"] == 1
    assert parsed["sample_rows"][0]["ticker"] == "AAPL"


def test_google_sheets_stale_rows_mark_warn() -> None:
    text = (
        "ticker,source,updated_at,confidence,price\n"
        "AAPL,IMPORTXML,2020-01-01T00:00:00+00:00,LOW,200\n"
    )

    result = audit.parse_published_csv(text, max_stale_minutes=60)

    assert result["status"] == "WARN"
    assert result["stale_rows"] == 1
    assert "stale_rows" in result["issues"]


def test_google_sheets_schema_errors_are_controlled() -> None:
    text = "ticker,price\nAAPL,200\n"

    result = audit.parse_published_csv(text)

    assert result["status"] == "WARN"
    assert "schema_missing_columns" in result["issues"]
    assert set(result["missing_columns"]) == {"confidence", "source", "updated_at"}


def test_google_sheets_run_audit_with_mocked_csv() -> None:
    updated_at = datetime.now(timezone.utc).isoformat()
    text = (
        "ticker,source,updated_at,confidence,sector,industry\n"
        f"MSFT,GOOGLE_SHEETS_MANUAL,{updated_at},LOW,Technology,Software\n"
    )

    def fake_request(url: str, timeout_seconds: int):
        assert url == "https://docs.google.com/spreadsheets/d/example/pub?output=csv"
        return 200, text

    result = audit.run_audit(
        csv_url="https://docs.google.com/spreadsheets/d/example/pub?output=csv",
        timeout_seconds=3,
        request_fn=fake_request,
    )

    assert result["status"] == "PASS"
    assert result["rows"] == 1
    assert result["valid_rows"] == 1
    assert result["header_row"] == 1
    assert result["schema"]["header_detected"] is True
    assert result["provider"]["data_freshness"] == "DELAYED_20_MIN"
    assert result["execution_enabled"] is False


def test_google_sheets_save_reports(tmp_path: Path) -> None:
    result = audit.run_audit(csv_url="")
    json_out = tmp_path / "sheets.json"
    md_out = tmp_path / "sheets.md"
    audit.save_reports(result, json_out=json_out, markdown_out=md_out)

    assert json_out.exists()
    assert md_out.exists()
    assert "Google Sheets data source audit" in md_out.read_text(encoding="utf-8")
