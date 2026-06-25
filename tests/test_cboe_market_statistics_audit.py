from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tools import cboe_market_statistics_audit as audit


TODAY = datetime.now(timezone.utc).date().isoformat()

MARKET_SHARE_CSV = f"""Day,Market Participant,Total Option Contracts
{TODAY},Cboe,100000
{TODAY},Other,200000
"""

PUT_CALL_CSV = f"""Disclaimer line
Another note
DATE,CALLS,PUTS,P/C Ratio
2026-06-20,1000000,900000,0.90
{TODAY},1200000,1500000,1.25
"""

EQUITIES_VOLUME_CSV = f"""Day,Market Participant,Total Shares
2026-06-20,Cboe,1000000000
{TODAY},Cboe,1100000000
"""


def test_cboe_parsers_extract_market_statistics() -> None:
    market = audit.parse_market_share_csv(MARKET_SHARE_CSV)
    put_call = audit.parse_put_call_csv(PUT_CALL_CSV)
    equities = audit.parse_equities_market_volume_csv(EQUITIES_VOLUME_CSV)

    assert market["status"] == "PASS"
    assert market["rows"] == 2
    assert market["total_option_contracts"] == 300000
    assert put_call["status"] == "PASS"
    assert put_call["latest_date"] == TODAY
    assert put_call["put_call_ratio"] == 1.25
    assert equities["status"] == "PASS"
    assert equities["rows"] == 1
    assert equities["total_shares"] == 1100000000


def test_cboe_audit_passes_with_mocked_csvs() -> None:
    def fake_request(url: str, timeout_seconds: int):
        if "market_share" in url:
            return 200, MARKET_SHARE_CSV
        if "totalpc" in url:
            return 200, PUT_CALL_CSV
        if "market_history" in url:
            return 200, EQUITIES_VOLUME_CSV
        raise AssertionError(f"unexpected url: {url}")

    result = audit.run_audit(timeout_seconds=3, request_fn=fake_request)

    assert result["status"] == "PASS"
    assert result["datasets_checked"] == 3
    assert result["datasets_available"] == 3
    assert result["provider"]["data_freshness"] == "EOD"
    assert result["execution_enabled"] is False
    assert result["aggregate_options_context"]["status"] == "CURRENT"
    assert result["aggregate_options_context"]["bias"] == "CROWDED_BEARISH_AGGREGATE"


def test_cboe_historical_put_call_is_marked_stale_and_not_usable() -> None:
    historical_put_call = """DATE,CALLS,PUTS,TOTAL,P/C Ratio
2019-10-04,2175006,2289715,4464721,1.05
"""

    def fake_request(url: str, timeout_seconds: int):
        if "market_share" in url:
            return 200, MARKET_SHARE_CSV
        if "totalpc" in url:
            return 200, historical_put_call
        return 200, EQUITIES_VOLUME_CSV

    result = audit.run_audit(timeout_seconds=3, max_age_days=5, request_fn=fake_request)

    assert result["status"] == "WARN"
    assert "cboe_dataset_stale" in result["issues"]
    assert result["aggregate_options_context"]["status"] == "STALE"
    assert result["aggregate_options_context"]["usable"] is False
    assert result["provider"]["fields"]["aggregate_put_call_usable"] is False


def test_cboe_all_sources_missing_is_controlled_warn() -> None:
    def fake_fail(url: str, timeout_seconds: int):
        return 503, ""

    result = audit.run_audit(timeout_seconds=3, request_fn=fake_fail)

    assert result["status"] == "WARN"
    assert result["datasets_available"] == 0
    assert "cboe_http_unavailable" in result["issues"]


def test_cboe_save_reports(tmp_path: Path) -> None:
    def fake_request(url: str, timeout_seconds: int):
        if "market_share" in url:
            return 200, MARKET_SHARE_CSV
        if "totalpc" in url:
            return 200, PUT_CALL_CSV
        return 200, EQUITIES_VOLUME_CSV

    result = audit.run_audit(timeout_seconds=3, request_fn=fake_request)
    json_out = tmp_path / "cboe.json"
    md_out = tmp_path / "cboe.md"
    audit.save_reports(result, json_out=json_out, markdown_out=md_out)

    assert json_out.exists()
    assert md_out.exists()
    assert "Cboe market statistics audit" in md_out.read_text(encoding="utf-8")
