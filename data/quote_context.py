from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


VALID_SESSIONS = {"PRE", "REGULAR", "POST", "CLOSED", "UNKNOWN"}


def _as_utc(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def normalize_market_session(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper()
    aliases = {
        "PREPRE": "PRE",
        "PREMARKET": "PRE",
        "REGULARMARKET": "REGULAR",
        "POSTPOST": "POST",
        "POSTMARKET": "POST",
        "CLOSED": "CLOSED",
    }
    text = aliases.get(text.replace("_", "").replace("-", ""), text)
    return text if text in VALID_SESSIONS else "UNKNOWN"


def add_quote_temporal_context(
    row: dict,
    *,
    now: datetime | None = None,
) -> dict:
    """Return a copy with normalized quote timestamp, age and session fields."""
    out = dict(row)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    raw_timestamp = (
        out.get("quote_timestamp")
        or out.get("regular_market_time")
        or out.get("regularMarketTime")
        or out.get("metadata_fetched_at")
    )
    timestamp = _as_utc(raw_timestamp)
    out["quote_timestamp"] = timestamp.isoformat() if timestamp else None
    out["market_session"] = normalize_market_session(
        out.get("market_session") or out.get("market_state")
    )

    if timestamp is None:
        out["quote_age_seconds"] = None
        out["quote_temporal_status"] = "UNKNOWN"
        return out

    age = max(0.0, (current - timestamp).total_seconds())
    out["quote_age_seconds"] = round(age, 2)
    out["quote_temporal_status"] = "KNOWN"
    return out


def temporal_quote_penalty(row: dict, config: dict) -> tuple[str | None, str | None]:
    """Return optional quote status and execution quality overrides."""
    age = row.get("quote_age_seconds")
    session = normalize_market_session(row.get("market_session"))
    if age is None:
        return None, None

    quote_cfg = config.get("quote_quality", {})
    regular_max = float(quote_cfg.get("max_age_seconds_regular", 900))
    extended_max = float(quote_cfg.get("max_age_seconds_extended", 3600))
    closed_max = float(quote_cfg.get("max_age_seconds_closed", 86400))

    if session == "REGULAR":
        limit = regular_max
    elif session in {"PRE", "POST"}:
        limit = extended_max
    else:
        limit = closed_max

    if float(age) > limit:
        return "STALE_POSSIBLE", "LOW"
    return None, None


def _append_reason(value: Any, reason: str) -> str:
    existing = [part.strip() for part in str(value or "").split(",") if part.strip()]
    if reason not in existing:
        existing.append(reason)
    return ", ".join(existing)


def normalize_scan_with_quote_context(
    df: pd.DataFrame,
    config: dict,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    """Normalize a scan and enforce temporal quote quality without breaking legacy rows."""
    if df.empty:
        return df.copy()

    from engine.audit_postprocessor import normalize_scan

    contextual = pd.DataFrame(
        [add_quote_temporal_context(row, now=now) for row in df.to_dict(orient="records")]
    )
    out = normalize_scan(contextual, config)

    for idx, row in out.iterrows():
        status, quality = temporal_quote_penalty(row.to_dict(), config)
        if status is None:
            continue

        out.at[idx, "quote_status"] = status
        out.at[idx, "execution_quote_quality"] = quality
        out.at[idx, "penalty_reasons"] = _append_reason(
            row.get("penalty_reasons"), "stale_quote_timestamp"
        )

        if row.get("signal") == "TRIGGER_CONFIRMED":
            out.at[idx, "signal"] = "WATCHLIST"
            out.at[idx, "actionable_entry"] = None
            out.at[idx, "actionable_stop"] = None
            out.at[idx, "actionable_target"] = None

    return out
