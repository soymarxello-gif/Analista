from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd

from data.historical_data_service import load_historical_prices, load_market_data_universe
from engine.data_sources.market_data_engine import (
    MARKET_DATA_ENGINE_SOURCE,
    inspect_market_database,
    load_daily_bars_from_database,
)
from tools.sync_market_data_engine import sync_market_database


def _database(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE assets(ticker TEXT PRIMARY KEY,name TEXT,asset_type TEXT,exchange TEXT,sector TEXT,industry TEXT,is_active INTEGER,data_status TEXT,historical_source TEXT);
            CREATE TABLE daily_bars(ticker TEXT,date TEXT,open REAL,high REAL,low REAL,close REAL,adjusted_close REAL,volume REAL,source TEXT,updated_at TEXT);
            CREATE TABLE daily_indicators(ticker TEXT,date TEXT,close REAL);
            CREATE TABLE fundamentals_snapshot(ticker TEXT,as_of_date TEXT,market_cap REAL,source TEXT);
            CREATE TABLE universe_runs(run_id TEXT,as_of_date TEXT,source TEXT,rows_received INTEGER,rows_eligible INTEGER,is_complete INTEGER,created_at TEXT);
            CREATE TABLE universe_snapshots(run_id TEXT,ticker TEXT,as_of_date TEXT,market_cap REAL,source TEXT);
            INSERT INTO assets VALUES('AAA','Alpha','stock','NASDAQ','Technology','Software',1,'ok','fixture');
            INSERT INTO daily_bars VALUES('AAA','2026-08-03',100,103,99,102,51,1000000,'fixture','2026-08-03T22:00:00Z');
            INSERT INTO daily_indicators VALUES('AAA','2026-08-03',51);
            INSERT INTO fundamentals_snapshot VALUES('AAA','2026-08-03',5000000000,'fixture');
            INSERT INTO universe_runs VALUES('run1','2026-08-03','fixture',1,1,1,'2026-08-03T22:00:00Z');
            INSERT INTO universe_snapshots VALUES('run1','AAA','2026-08-03',5000000000,'fixture');
            """
        )


def _config(db: Path, tmp_path: Path) -> dict:
    return {
        "data_sources": {
            "providers": {
                "market_data_engine": {
                    "enabled": True,
                    "drive_db_path": str(db),
                    "drive_manifest_path": str(tmp_path / "master_manifest.json"),
                    "local_cache_path": str(tmp_path / "local.db"),
                    "local_manifest_path": str(tmp_path / "local_manifest.json"),
                    "max_stale_days": 500,
                }
            }
        }
    }


def test_market_database_loads_adjusted_history_and_universe(tmp_path) -> None:
    db = tmp_path / "market.db"
    _database(db)

    health = inspect_market_database(db, max_stale_days=500)
    prices = load_daily_bars_from_database(db, ["AAA"])
    config = _config(db, tmp_path)
    config["data_sources"]["providers"]["market_data_engine"]["local_cache_path"] = str(db)
    universe, universe_health = load_market_data_universe(config)

    assert health["latest_coverage"] == 1.0
    assert prices["AAA"].attrs["source"] == MARKET_DATA_ENGINE_SOURCE
    assert prices["AAA"].iloc[-1]["adj_close"] == 51
    assert prices["AAA"].iloc[-1]["adj_factor"] == 0.5
    assert universe_health["status"] in {"PASS", "WARN"}
    assert universe.iloc[0]["ticker"] == "AAA"
    assert universe.iloc[0]["exchange"] == "NMS"


def test_historical_service_uses_database_then_yahoo_only_for_missing(tmp_path) -> None:
    source = tmp_path / "market.db"
    _database(source)
    local = tmp_path / "local.db"
    local.write_bytes(source.read_bytes())
    config = _config(source, tmp_path)
    config["data_sources"]["providers"]["market_data_engine"]["local_cache_path"] = str(local)
    calls: list[list[str]] = []

    def yahoo(tickers, **kwargs):
        calls.append(tickers)
        return {"BBB": pd.DataFrame({"close": [20.0]}, index=[pd.Timestamp("2026-08-03")])}

    stats: dict = {}
    result = load_historical_prices(
        ["AAA", "BBB"], config=config, stats=stats, yahoo_fn=yahoo
    )

    assert set(result) == {"AAA", "BBB"}
    assert calls == [["BBB"]]
    assert stats["source_by_ticker"]["AAA"] == MARKET_DATA_ENGINE_SOURCE
    assert stats["source_by_ticker"]["BBB"] == "YAHOO_FINANCE"


def test_sync_validates_checksum_and_replaces_local_atomically(tmp_path) -> None:
    source = tmp_path / "market.db"
    _database(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = tmp_path / "master_manifest.json"
    manifest.write_text(
        json.dumps({"database_sha256": digest, "latest_bar_date": "2026-08-03"}),
        encoding="utf-8",
    )
    config = _config(source, tmp_path)

    report = sync_market_database(config)

    assert report["status"] in {"PASS", "WARN"}
    assert report["updated"] is True
    assert (tmp_path / "local.db").is_file()
    assert not (tmp_path / "local.db.partial").exists()


def test_historical_source_has_no_execution_fields(tmp_path) -> None:
    db = tmp_path / "market.db"
    _database(db)
    frame = load_daily_bars_from_database(db, ["AAA"])["AAA"]

    forbidden = {"signal", "recommendation", "quote_status", "execution_quote_quality"}
    assert forbidden.isdisjoint(frame.columns)
