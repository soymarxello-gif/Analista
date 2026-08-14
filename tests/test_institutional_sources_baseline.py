from __future__ import annotations

import json
import sqlite3
import zipfile
from datetime import datetime, timezone

from institutional.baseline import create_baseline_bundle
from institutional.source_adapters import (
    parse_nasdaq_symbol_directory,
    sec_company_fact_as_of,
    validate_market_feed,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=timezone.utc)


def test_nasdaq_directory_parser_excludes_test_issues_and_identifies_etf():
    payload = "Symbol|Security Name|ETF|Test Issue\nAAA|AAA Inc|N|N\nETF1|Index ETF|Y|N\nTEST|Test|N|Y\nFile Creation Time: 07212026|"
    rows = parse_nasdaq_symbol_directory(payload, available_at=NOW, exchange="NASDAQ", source="NASDAQ_TRADER")
    assert [row.symbol for row in rows] == ["AAA", "ETF1"]
    assert rows[1].asset_type.value == "ETF"


def test_sec_fact_selection_respects_filing_availability_not_latest_revision():
    payload = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"end": "2026-03-31", "filed": "2026-05-01", "val": 100, "accn": "old", "form": "10-Q"},
                            {"end": "2026-03-31", "filed": "2026-08-01", "val": 110, "accn": "future", "form": "10-Q/A"},
                        ]
                    }
                }
            }
        }
    }
    fact = sec_company_fact_as_of(payload, "us-gaap", "Revenues", "USD", NOW)
    assert fact.value == 100
    assert fact.accession == "old"


def test_feed_policy_blocks_iex_for_volume_and_non_opra_options():
    assert validate_market_feed("iex", use_case="relative_volume") == "DEGRADED_RESEARCH_ONLY"
    assert validate_market_feed("sip", use_case="trigger_confirmation") == "EXECUTION_GRADE"
    assert validate_market_feed("indicative", use_case="options_execution") == "DEGRADED_RESEARCH_ONLY"


def test_baseline_bundle_contains_consistent_database_snapshot_and_hashes(tmp_path):
    database = tmp_path / "engine.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE values_table(value INTEGER)")
    connection.execute("INSERT INTO values_table VALUES (7)")
    connection.commit()
    connection.close()
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\n", encoding="utf-8")
    output = create_baseline_bundle(database, config, tmp_path / "baseline.zip")
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["database_sha256"]
        assert set(archive.namelist()) == {"institutional.sqlite", "config.yaml", "manifest.json"}
