from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from .models import AssetType, DecisionState, Outcome, PriceBar, SecurityRecord, SignalEvent


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


class InstitutionalStore:
    """SQLite reference store with explicit event-time and availability-time semantics."""

    SCHEMA_VERSION = "institutional-store-1"

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(self.path, timeout=30.0, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA busy_timeout = 30000")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS security_master (
                symbol TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                available_at TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                exchange TEXT NOT NULL,
                currency TEXT NOT NULL,
                active INTEGER NOT NULL,
                market_cap_usd REAL,
                sector TEXT,
                industry TEXT,
                name TEXT,
                source TEXT NOT NULL,
                PRIMARY KEY(symbol, valid_from, available_at)
            );
            CREATE TABLE IF NOT EXISTS price_bars (
                symbol TEXT NOT NULL,
                session TEXT NOT NULL,
                available_at TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                source TEXT NOT NULL,
                feed TEXT NOT NULL,
                adjusted INTEGER NOT NULL,
                PRIMARY KEY(symbol, session, available_at, source, feed)
            );
            CREATE TABLE IF NOT EXISTS signal_events (
                signal_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                decision_time TEXT NOT NULL,
                available_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS outcomes (
                signal_id TEXT PRIMARY KEY,
                evaluated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_health (
                source TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                status TEXT NOT NULL,
                coverage_pct REAL NOT NULL,
                age_seconds REAL,
                detail TEXT,
                PRIMARY KEY(source, checked_at)
            );
            CREATE TABLE IF NOT EXISTS shadow_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                configuration_hash TEXT NOT NULL,
                universe_hash TEXT NOT NULL,
                signal_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS context_observations (
                source TEXT NOT NULL,
                series TEXT NOT NULL,
                event_time TEXT NOT NULL,
                available_at TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY(source, series, event_time, available_at)
            );
            CREATE INDEX IF NOT EXISTS idx_security_asof
                ON security_master(symbol, valid_from, valid_to, available_at);
            CREATE INDEX IF NOT EXISTS idx_bars_asof
                ON price_bars(symbol, session, available_at);
            CREATE INDEX IF NOT EXISTS idx_signals_symbol_time
                ON signal_events(symbol, decision_time);
            """
        )
        self.connection.commit()

    def put_security_records(self, records: Iterable[SecurityRecord]) -> None:
        rows = [
            (
                r.symbol.upper(),
                _iso(r.valid_from),
                _iso(r.valid_to) if r.valid_to else None,
                _iso(r.available_at),
                r.asset_type.value,
                r.exchange.upper(),
                r.currency.upper(),
                int(r.active),
                r.market_cap_usd,
                r.sector,
                r.industry,
                r.name,
                r.source,
            )
            for r in records
        ]
        with self._lock:
            self.connection.executemany(
                """INSERT OR REPLACE INTO security_master
                (symbol,valid_from,valid_to,available_at,asset_type,exchange,currency,active,
                 market_cap_usd,sector,industry,name,source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            self.connection.commit()

    def securities_as_of(self, as_of: datetime) -> list[SecurityRecord]:
        stamp = _iso(as_of)
        with self._lock:
            rows = self.connection.execute(
                """
                WITH ranked AS (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY symbol ORDER BY valid_from DESC, available_at DESC
                    ) AS row_number
                    FROM security_master
                    WHERE valid_from <= ? AND (valid_to IS NULL OR valid_to > ?) AND available_at <= ?
                )
                SELECT * FROM ranked WHERE row_number = 1 ORDER BY symbol
                """,
                (stamp, stamp, stamp),
            ).fetchall()
        return [
            SecurityRecord(
                symbol=row["symbol"],
                asset_type=AssetType(row["asset_type"]),
                exchange=row["exchange"],
                currency=row["currency"],
                active=bool(row["active"]),
                valid_from=_dt(row["valid_from"]),
                valid_to=_dt(row["valid_to"]) if row["valid_to"] else None,
                available_at=_dt(row["available_at"]),
                market_cap_usd=row["market_cap_usd"],
                sector=row["sector"],
                industry=row["industry"],
                name=row["name"],
                source=row["source"],
            )
            for row in rows
        ]

    def put_price_bars(self, bars: Iterable[PriceBar]) -> None:
        rows = [
            (
                b.symbol.upper(),
                _iso(b.session),
                _iso(b.available_at),
                b.open,
                b.high,
                b.low,
                b.close,
                b.volume,
                b.source,
                b.feed,
                int(b.adjusted),
            )
            for b in bars
        ]
        with self._lock:
            self.connection.executemany(
                """INSERT OR REPLACE INTO price_bars
                (symbol,session,available_at,open,high,low,close,volume,source,feed,adjusted)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            self.connection.commit()

    def bars_as_of(
        self,
        symbol: str,
        as_of: datetime,
        *,
        start: datetime | None = None,
        limit: int | None = None,
    ) -> list[PriceBar]:
        clauses = ["symbol = ?", "session <= ?", "available_at <= ?"]
        params: list[object] = [symbol.upper(), _iso(as_of), _iso(as_of)]
        if start is not None:
            clauses.append("session >= ?")
            params.append(_iso(start))
        query = f"""
            WITH ranked AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY symbol, session ORDER BY available_at DESC
                ) AS row_number
                FROM price_bars WHERE {' AND '.join(clauses)}
            )
            SELECT * FROM ranked WHERE row_number = 1 ORDER BY session
        """
        with self._lock:
            rows = self.connection.execute(query, params).fetchall()
        if limit is not None:
            rows = rows[-limit:]
        return [self._bar(row) for row in rows]

    def bars_after(self, symbol: str, after: datetime, *, limit: int) -> list[PriceBar]:
        with self._lock:
            rows = self.connection.execute(
                """
                WITH ranked AS (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY symbol, session ORDER BY available_at DESC
                    ) AS row_number
                    FROM price_bars WHERE symbol = ? AND session > ?
                )
                SELECT * FROM ranked WHERE row_number = 1 ORDER BY session LIMIT ?
                """,
                (symbol.upper(), _iso(after), limit),
            ).fetchall()
        return [self._bar(row) for row in rows]

    def latest_bar_sessions(self, symbols: Iterable[str]) -> dict[str, datetime]:
        normalized = sorted({symbol.upper() for symbol in symbols})
        if not normalized:
            return {}
        placeholders = ",".join("?" for _ in normalized)
        with self._lock:
            rows = self.connection.execute(
                f"SELECT symbol, MAX(session) AS session FROM price_bars "
                f"WHERE symbol IN ({placeholders}) GROUP BY symbol",
                normalized,
            ).fetchall()
        return {row["symbol"]: _dt(row["session"]) for row in rows if row["session"]}

    @staticmethod
    def _bar(row: sqlite3.Row) -> PriceBar:
        return PriceBar(
            symbol=row["symbol"],
            session=_dt(row["session"]),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            available_at=_dt(row["available_at"]),
            source=row["source"],
            feed=row["feed"],
            adjusted=bool(row["adjusted"]),
        )

    def put_signal(self, signal: SignalEvent) -> None:
        payload = {
            **signal.__dict__,
            "decision_time": _iso(signal.decision_time),
            "available_at": _iso(signal.available_at),
            "state": signal.state.value,
            "reasons": list(signal.reasons),
            "hard_vetoes": list(signal.hard_vetoes),
        }
        with self._lock:
            self.connection.execute(
                "INSERT OR REPLACE INTO signal_events VALUES (?,?,?,?,?)",
                (signal.signal_id, signal.symbol, _iso(signal.decision_time), _iso(signal.available_at), json.dumps(payload, sort_keys=True)),
            )
            self.connection.commit()

    def latest_signal_time(self) -> datetime | None:
        with self._lock:
            row = self.connection.execute("SELECT MAX(decision_time) FROM signal_events").fetchone()
        return _dt(row[0]) if row and row[0] else None

    def table_counts(self) -> dict[str, int]:
        """Return operational counts without exposing SQLite internals to API callers."""
        tables = {
            "securities": "security_master",
            "bars": "price_bars",
            "signals": "signal_events",
            "outcomes": "outcomes",
            "source_health": "source_health",
            "shadow_runs": "shadow_runs",
            "context_observations": "context_observations",
        }
        with self._lock:
            return {
                label: int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for label, table in tables.items()
            }

    def record_shadow_run(
        self,
        run_id: str,
        started_at: datetime,
        configuration_hash: str,
        universe_hash: str,
        signal_count: int,
        status: str,
        payload: dict[str, object],
    ) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT OR REPLACE INTO shadow_runs VALUES (?,?,?,?,?,?,?)",
                (
                    run_id,
                    _iso(started_at),
                    configuration_hash,
                    universe_hash,
                    signal_count,
                    status,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            self.connection.commit()

    def shadow_runs(self, limit: int = 50) -> list[dict[str, object]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM shadow_runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def put_context_observation(
        self,
        source: str,
        series: str,
        event_time: datetime,
        available_at: datetime,
        status: str,
        payload: dict[str, object],
    ) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT OR REPLACE INTO context_observations VALUES (?,?,?,?,?,?)",
                (source, series, _iso(event_time), _iso(available_at), status, json.dumps(payload, sort_keys=True)),
            )
            self.connection.commit()

    def context_as_of(self, as_of: datetime, source: str | None = None) -> list[dict[str, object]]:
        clauses = ["available_at <= ?"]
        params: list[object] = [_iso(as_of)]
        if source:
            clauses.append("source = ?")
            params.append(source)
        with self._lock:
            rows = self.connection.execute(
                f"SELECT * FROM context_observations WHERE {' AND '.join(clauses)} "
                "ORDER BY source, series, event_time",
                params,
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def signals(self) -> list[SignalEvent]:
        with self._lock:
            rows = self.connection.execute("SELECT payload_json FROM signal_events ORDER BY decision_time, signal_id").fetchall()
        return [self._signal(json.loads(row[0])) for row in rows]

    @staticmethod
    def _signal(payload: dict[str, object]) -> SignalEvent:
        payload = dict(payload)
        payload["decision_time"] = _dt(str(payload["decision_time"]))
        payload["available_at"] = _dt(str(payload["available_at"]))
        payload["state"] = DecisionState(payload["state"])
        payload["reasons"] = tuple(payload.get("reasons", []))
        payload["hard_vetoes"] = tuple(payload.get("hard_vetoes", []))
        return SignalEvent(**payload)

    def put_outcome(self, outcome: Outcome) -> None:
        payload = {**outcome.__dict__, "evaluated_at": _iso(outcome.evaluated_at)}
        with self._lock:
            self.connection.execute(
                "INSERT OR REPLACE INTO outcomes VALUES (?,?,?)",
                (outcome.signal_id, _iso(outcome.evaluated_at), json.dumps(payload, sort_keys=True)),
            )
            self.connection.commit()

    def outcomes(self) -> list[Outcome]:
        with self._lock:
            rows = self.connection.execute("SELECT payload_json FROM outcomes ORDER BY evaluated_at, signal_id").fetchall()
        result = []
        for row in rows:
            payload = json.loads(row[0])
            payload["evaluated_at"] = _dt(payload["evaluated_at"])
            result.append(Outcome(**payload))
        return result

    def record_source_health(
        self,
        source: str,
        checked_at: datetime,
        status: str,
        coverage_pct: float,
        age_seconds: float | None,
        detail: str | None = None,
    ) -> None:
        if not 0 <= coverage_pct <= 100:
            raise ValueError("coverage_pct must be between 0 and 100")
        with self._lock:
            self.connection.execute(
                "INSERT OR REPLACE INTO source_health VALUES (?,?,?,?,?,?)",
                (source, _iso(checked_at), status, coverage_pct, age_seconds, detail),
            )
            self.connection.commit()

    def source_health(self) -> list[dict[str, object]]:
        with self._lock:
            return [dict(row) for row in self.connection.execute("SELECT * FROM source_health ORDER BY source, checked_at")]
