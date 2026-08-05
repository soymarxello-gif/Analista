from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd

MARKET_DATA_ENGINE_SOURCE = "MARKET_DATA_ENGINE_SQLITE"
REQUIRED_TABLES = {
    "assets",
    "daily_bars",
    "daily_indicators",
    "fundamentals_snapshot",
    "universe_runs",
    "universe_snapshots",
}


def _chunks(values: list[str], size: int = 400) -> Iterator[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


@contextmanager
def readonly_connection(path: str | Path) -> Iterator[sqlite3.Connection]:
    db_path = Path(path).resolve()
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def inspect_market_database(path: str | Path, *, max_stale_days: int = 7) -> dict:
    db_path = Path(path)
    report = {
        "status": "FAIL",
        "source": MARKET_DATA_ENGINE_SOURCE,
        "db_path": str(db_path),
        "errors": [],
        "warnings": [],
    }
    if not db_path.is_file():
        report["errors"].append("database_missing")
        return report
    try:
        with readonly_connection(db_path) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            missing = sorted(REQUIRED_TABLES - tables)
            if missing:
                report["errors"].append("missing_tables:" + ",".join(missing))
                report["tables"] = sorted(tables)
                return report
            scalar = lambda sql, args=(): conn.execute(sql, args).fetchone()[0]
            latest = scalar("SELECT MAX(date) FROM daily_bars")
            latest_ind = scalar("SELECT MAX(date) FROM daily_indicators")
            active = int(scalar("SELECT COUNT(*) FROM assets WHERE is_active=1") or 0)
            latest_count = int(
                scalar("SELECT COUNT(DISTINCT ticker) FROM daily_indicators WHERE date=?", (latest_ind,)) or 0
            )
            age_days = (date.today() - date.fromisoformat(latest)).days if latest else None
            coverage = latest_count / active if active else 0.0
            report.update(
                {
                    "latest_bar_date": latest,
                    "latest_indicator_date": latest_ind,
                    "age_days": age_days,
                    "assets": int(scalar("SELECT COUNT(*) FROM assets") or 0),
                    "active_assets": active,
                    "assets_with_history": int(
                        scalar(
                            """
                            SELECT COUNT(*)
                            FROM assets a
                            WHERE a.is_active=1
                              AND EXISTS (SELECT 1 FROM daily_bars b WHERE b.ticker=a.ticker)
                            """
                        ) or 0
                    ),
                    "latest_assets": latest_count,
                    "latest_coverage": round(coverage, 6),
                    "sectors": int(
                        scalar("SELECT COUNT(DISTINCT sector) FROM assets WHERE sector IS NOT NULL") or 0
                    ),
                    "data_freshness": "EOD",
                    "confidence": "HIGH",
                }
            )
            if age_days is None or age_days > max_stale_days:
                report["warnings"].append("database_stale")
                report["confidence"] = "LOW"
            if coverage < 0.95:
                report["warnings"].append("latest_coverage_below_95pct")
                report["confidence"] = "LOW"
            report["status"] = "PASS" if not report["warnings"] else "WARN"
    except Exception as exc:
        report["errors"].append(f"database_read_failed:{type(exc).__name__}:{exc}")
    return report


def load_daily_bars_from_database(
    path: str | Path,
    tickers: list[str],
    *,
    start: date | None = None,
    end: date | None = None,
) -> dict[str, pd.DataFrame]:
    normalized = list(dict.fromkeys(str(value).upper().strip() for value in tickers if str(value).strip()))
    if not normalized:
        return {}
    rows: list[sqlite3.Row] = []
    with readonly_connection(path) as conn:
        for batch in _chunks(normalized):
            placeholders = ",".join("?" for _ in batch)
            clauses = [f"b.ticker IN ({placeholders})"]
            params: list[object] = list(batch)
            if start:
                clauses.append("b.date >= ?")
                params.append(start.isoformat())
            if end:
                clauses.append("b.date <= ?")
                params.append(end.isoformat())
            rows.extend(
                conn.execute(
                    f"""
                    WITH ranked AS (
                        SELECT b.*,
                               ROW_NUMBER() OVER (
                                   PARTITION BY b.ticker,b.date
                                   ORDER BY CASE WHEN b.source=a.historical_source THEN 0 ELSE 1 END,
                                            b.updated_at DESC,b.source
                               ) AS source_rank
                        FROM daily_bars b JOIN assets a ON a.ticker=b.ticker
                        WHERE {' AND '.join(clauses)}
                    )
                    SELECT ticker,date,open,high,low,close,adjusted_close,volume,source
                    FROM ranked WHERE source_rank=1 ORDER BY ticker,date
                    """,
                    params,
                ).fetchall()
            )
    if not rows:
        return {}
    raw = pd.DataFrame([dict(row) for row in rows])
    output: dict[str, pd.DataFrame] = {}
    for ticker, group in raw.groupby("ticker", sort=False):
        frame = group.copy()
        frame.index = pd.to_datetime(frame.pop("date"), errors="coerce")
        frame = frame.rename(columns={"adjusted_close": "adj_close"})
        close = pd.to_numeric(frame["close"], errors="coerce").replace(0, pd.NA)
        factor = (pd.to_numeric(frame["adj_close"], errors="coerce") / close).fillna(1.0)
        frame["adj_factor"] = factor
        frame["adj_open"] = pd.to_numeric(frame["open"], errors="coerce") * factor
        frame["adj_high"] = pd.to_numeric(frame["high"], errors="coerce") * factor
        frame["adj_low"] = pd.to_numeric(frame["low"], errors="coerce") * factor
        frame.attrs["source"] = MARKET_DATA_ENGINE_SOURCE
        output[str(ticker)] = frame.drop(columns=["ticker", "source"]).sort_index()
    return output


def load_current_universe_from_database(path: str | Path) -> pd.DataFrame:
    exchange_map = {"NASDAQ": "NMS", "NYSE": "NYQ", "AMEX": "ASE"}
    with readonly_connection(path) as conn:
        run = conn.execute(
            "SELECT run_id,as_of_date FROM universe_runs WHERE is_complete=1 ORDER BY as_of_date DESC,created_at DESC LIMIT 1"
        ).fetchone()
        if not run:
            return pd.DataFrame()
        rows = conn.execute(
            """
            WITH latest_bar AS (
                SELECT ticker,MAX(date) AS date FROM daily_bars GROUP BY ticker
            ), latest_fundamental AS (
                SELECT ticker,MAX(as_of_date) AS as_of_date FROM fundamentals_snapshot GROUP BY ticker
            )
            SELECT a.ticker,a.name,a.exchange,a.sector,a.industry,
                   COALESCE(u.market_cap,f.market_cap) AS market_cap,b.close
            FROM universe_snapshots u
            JOIN assets a ON a.ticker=u.ticker AND a.is_active=1
            LEFT JOIN latest_bar lb ON lb.ticker=a.ticker
            LEFT JOIN daily_bars b ON b.ticker=lb.ticker AND b.date=lb.date
            LEFT JOIN latest_fundamental lf ON lf.ticker=a.ticker
            LEFT JOIN fundamentals_snapshot f ON f.ticker=lf.ticker AND f.as_of_date=lf.as_of_date
            WHERE u.run_id=?
              AND EXISTS (SELECT 1 FROM daily_bars history WHERE history.ticker=a.ticker)
            GROUP BY a.ticker
            ORDER BY COALESCE(u.market_cap,f.market_cap) DESC,a.ticker
            """,
            (run["run_id"],),
        ).fetchall()
    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        return frame
    frame["company"] = frame.pop("name")
    frame["price"] = frame.pop("close")
    frame["exchange"] = frame["exchange"].map(exchange_map).fillna(frame["exchange"])
    frame["quote_type"] = "EQUITY"
    frame["source_channel"] = "market_data_engine"
    frame["source_channels"] = "market_data_engine"
    frame["source_rank"] = range(1, len(frame) + 1)
    frame["source_weight"] = 1.0
    frame["screener_hit_count"] = 1
    frame["screener_weighted_hits"] = 1.0
    frame["source_quality_score"] = 1.0
    frame["market_data_as_of_date"] = run["as_of_date"]
    return frame
