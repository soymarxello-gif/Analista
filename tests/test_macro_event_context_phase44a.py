from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tools import macro_event_context as macro


def _fred_csv(series_id: str, values: list[tuple[str, float]]) -> str:
    rows = ["DATE," + series_id]
    rows.extend(f"{day},{value}" for day, value in values)
    return "\n".join(rows)


def _calendar(tmp_path: Path, event_date: str, *, updated_at: str = "2026-06-23") -> Path:
    path = tmp_path / "economic_calendar.csv"
    path.write_text(
        "event_date,event_time,timezone,event_type,event_name,importance,source_url,updated_at\n"
        f"{event_date},08:30,America/New_York,CPI,CPI release,HIGH,https://www.bls.gov/cpi/,{updated_at}\n",
        encoding="utf-8",
    )
    return path


def _request_ok(url: str, timeout_seconds: int) -> tuple[int, str]:
    if "M2SL" in url:
        return 200, _fred_csv("M2SL", [("2026-05-01", 21000), ("2026-06-01", 21210)])
    if "RRPONTSYD" in url:
        return 200, _fred_csv("RRPONTSYD", [("2026-05-25", 100), ("2026-06-22", 80)])
    if "DFF" in url:
        return 200, _fred_csv("DFF", [("2026-05-25", 4.25), ("2026-06-22", 4.25)])
    raise AssertionError(url)


def test_fred_parser_calculates_latest_and_four_week_change() -> None:
    result = macro.parse_fred_csv(
        _fred_csv("M2SL", [("2026-05-01", 20000), ("2026-06-01", 20200)]),
        series_id="M2SL",
        as_of=datetime(2026, 6, 23, tzinfo=timezone.utc).date(),
    )

    assert result["status"] == "PASS"
    assert result["latest_value"] == 20200
    assert round(result["change_4w"], 2) == 1.0
    assert result["stale"] is False


def test_empty_and_stale_fred_data_are_controlled_warn() -> None:
    empty = macro.parse_fred_csv("DATE,M2SL\n", series_id="M2SL")
    stale = macro.parse_fred_csv(
        _fred_csv("RRPONTSYD", [("2025-01-01", 100)]),
        series_id="RRPONTSYD",
        as_of=datetime(2026, 6, 23, tzinfo=timezone.utc).date(),
    )

    assert empty["status"] == "WARN"
    assert empty["issue"] == "fred_empty_or_invalid_series"
    assert stale["status"] == "WARN"
    assert stale["issue"] == "fred_series_stale"


def test_calendar_classifies_today_within_one_three_days_and_clear(tmp_path: Path) -> None:
    as_of = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)
    cases = [
        ("2026-06-23", "TODAY"),
        ("2026-06-24", "WITHIN_1_DAY"),
        ("2026-06-26", "WITHIN_3_DAYS"),
        ("2026-07-02", "CLEAR"),
    ]

    for event_date, expected in cases:
        result = macro.load_economic_calendar(_calendar(tmp_path, event_date), as_of=as_of)
        assert result["event_risk_status"] == expected


def test_missing_or_invalid_calendar_is_warn_without_traceback(tmp_path: Path) -> None:
    missing = macro.load_economic_calendar(tmp_path / "missing.csv")
    invalid = tmp_path / "invalid.csv"
    invalid.write_text("date,name\n2026-07-01,test\n", encoding="utf-8")

    assert missing["status"] == "WARN"
    assert missing["event_risk_status"] == "UNKNOWN"
    assert macro.load_economic_calendar(invalid)["status"] == "WARN"


def test_run_report_combines_events_and_liquidity_without_execution_changes(tmp_path: Path) -> None:
    result = macro.run_report(
        calendar_path=_calendar(tmp_path, "2026-06-24"),
        request_fn=_request_ok,
        as_of=datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc),
    )

    assert result["status"] == "PASS"
    assert result["event_risk_status"] == "WITHIN_1_DAY"
    assert result["liquidity_context"] == "EXPANDING"
    assert result["m2_latest"] == 21210
    assert result["reverse_repo_latest"] == 80
    assert result["guardrails"] == {
        "scanner_rows_modified": False,
        "scoring_modified": False,
        "signals_modified": False,
        "thresholds_modified": False,
        "broker_execution": False,
    }


def test_network_failures_generate_warn_reports(tmp_path: Path) -> None:
    def fail_request(url: str, timeout_seconds: int) -> tuple[int, str]:
        return 503, ""

    result = macro.run_report(
        calendar_path=_calendar(tmp_path, "2026-07-02"),
        request_fn=fail_request,
        as_of=datetime(2026, 6, 23, tzinfo=timezone.utc),
    )
    json_out = tmp_path / "macro.json"
    markdown_out = tmp_path / "macro.md"
    macro.save_reports(result, json_out=json_out, markdown_out=markdown_out)

    assert result["status"] == "WARN"
    assert result["liquidity_context"] == "UNKNOWN"
    assert json.loads(json_out.read_text(encoding="utf-8"))["status"] == "WARN"
    assert "No automatic trading" in markdown_out.read_text(encoding="utf-8")


def test_daily_integrations_reference_macro_event_context() -> None:
    root = Path(__file__).resolve().parents[1]
    daily_validation = (root / "tools" / "daily_validation.py").read_text(encoding="utf-8")
    operator_index = (root / "tools" / "daily_operator_index.py").read_text(encoding="utf-8")
    manifest = (root / "tools" / "daily_run_manifest.py").read_text(encoding="utf-8")

    assert "macro_event_context" in daily_validation
    assert "Macro event and liquidity context" in operator_index
    assert "macro_event_context_latest.json" in manifest
