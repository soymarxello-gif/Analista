from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd


FRESH_EARNINGS_CACHE_STATUSES = {"HIT", "REFRESHED", "FRESH_NETWORK"}


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def _as_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def normalize_earnings_context(
    record: dict[str, Any],
    *,
    as_of: Any = None,
    earnings_ttl_minutes: int = 720,
    recent_event_days: int = 2,
) -> dict[str, Any]:
    """Derive all relative earnings fields from the cached absolute date."""
    out = dict(record)
    as_of_date = _as_date(as_of) or datetime.now(timezone.utc).date()
    earnings_date = _as_date(out.get("earnings_date") or out.get("next_earnings_date"))
    cache_status = str(out.get("earnings_cache_status") or "").upper().strip()
    cache_age = _as_float(out.get("earnings_cache_age_minutes"))

    out["earnings_as_of_date"] = as_of_date.isoformat()
    out["earnings_days_recomputed"] = False
    out["earnings_consistency_status"] = "UNKNOWN"

    if earnings_date is None:
        out["days_to_earnings"] = None
        out["earnings_event_status"] = "MISSING"
        out["earnings_data_confidence"] = "UNKNOWN"
        out["earnings_refresh_required"] = True
        out["earnings_operability_block"] = True
        out["earnings_review_reason"] = "earnings_date_missing"
        return out

    days = int((earnings_date - as_of_date).days)
    out["earnings_date"] = earnings_date.isoformat()
    out["days_to_earnings"] = days
    out["earnings_days_recomputed"] = True
    out["earnings_consistency_status"] = "PASS"

    if days > 0:
        event_status = "UPCOMING"
    elif days == 0:
        event_status = "TODAY"
    elif days >= -abs(int(recent_event_days)):
        event_status = "RECENTLY_REPORTED"
    else:
        event_status = "PAST_STALE"
    out["earnings_event_status"] = event_status

    cache_is_fresh = (
        cache_status in FRESH_EARNINGS_CACHE_STATUSES
        and cache_age is not None
        and cache_age <= float(earnings_ttl_minutes)
    )
    if cache_is_fresh:
        confidence = "HIGH"
    elif event_status == "PAST_STALE":
        confidence = "LOW"
    else:
        confidence = "MEDIUM"
    out["earnings_data_confidence"] = confidence

    refresh_required = (
        cache_status not in FRESH_EARNINGS_CACHE_STATUSES
        or cache_age is None
        or cache_age > float(earnings_ttl_minutes)
        or event_status == "PAST_STALE"
        or (0 <= days <= 7 and not cache_is_fresh)
    )
    out["earnings_refresh_required"] = bool(refresh_required)

    stabilization_status = str(
        out.get("post_earnings_stabilization_status") or ""
    ).upper()
    near_event = event_status == "TODAY" or (event_status == "UPCOMING" and days <= 3)
    recent_unstable = (
        event_status == "RECENTLY_REPORTED"
        and stabilization_status != "STABILIZED"
    )
    out["earnings_operability_block"] = bool(near_event or recent_unstable)

    if near_event:
        reason = "earnings_within_3_days"
    elif recent_unstable:
        reason = "post_earnings_stabilization_required"
    elif event_status == "PAST_STALE":
        reason = "past_earnings_date_requires_refresh"
    elif 4 <= days <= 7:
        reason = "earnings_within_7_days"
    else:
        reason = ""
    out["earnings_review_reason"] = reason
    return out


def evaluate_post_earnings_stabilization(
    prices: pd.DataFrame,
    *,
    earnings_date: Any,
    as_of: Any = None,
) -> dict[str, Any]:
    """Score the first closed bars after a recently reported event."""
    empty = {
        "post_earnings_stabilization_score": None,
        "post_earnings_stabilization_status": "NOT_APPLICABLE",
        "post_earnings_closed_bars": 0,
        "post_earnings_gap_atr": None,
        "post_earnings_range_atr": None,
        "post_earnings_close_location": None,
        "post_earnings_stabilization_reason": "",
    }
    event_date = _as_date(earnings_date)
    as_of_date = _as_date(as_of) or datetime.now(timezone.utc).date()
    if event_date is None or prices is None or prices.empty:
        return empty

    frame = prices.copy()
    frame.index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame[frame.index.notna()].sort_index()
    if frame.empty:
        return empty

    bar_dates = pd.Series(frame.index.date, index=frame.index)
    after_event = frame[(bar_dates > event_date) & (bar_dates <= as_of_date)]
    if after_event.empty:
        return {
            **empty,
            "post_earnings_stabilization_status": "INSUFFICIENT_CLOSED_BARS",
            "post_earnings_stabilization_reason": "no_closed_bar_after_earnings",
        }

    first = after_event.iloc[0]
    before_event = frame[bar_dates <= event_date]
    previous_close = (
        _as_float(before_event.iloc[-1].get("close"))
        if not before_event.empty
        else None
    )
    atr = _as_float(first.get("atr"))
    open_price = _as_float(first.get("open"))
    high = _as_float(first.get("high"))
    low = _as_float(first.get("low"))
    close = _as_float(first.get("close"))
    relative_volume = _as_float(first.get("relative_volume"))

    if (
        atr is None
        or atr <= 0
        or open_price is None
        or high is None
        or low is None
        or close is None
        or high <= low
    ):
        return {
            **empty,
            "post_earnings_closed_bars": int(len(after_event)),
            "post_earnings_stabilization_status": "DATA_INSUFFICIENT",
            "post_earnings_stabilization_reason": "post_earnings_ohlcv_or_atr_missing",
        }

    gap_atr = (
        abs(open_price - previous_close) / atr
        if previous_close is not None
        else None
    )
    range_atr = (high - low) / atr
    close_location = (close - low) / (high - low)

    close_score = max(0.0, min(close_location, 1.0)) * 100.0
    gap_score = (
        60.0
        if gap_atr is None
        else max(0.0, min(100.0, 100.0 - max(gap_atr - 1.0, 0.0) * 50.0))
    )
    range_score = max(
        0.0,
        min(100.0, 100.0 - max(range_atr - 1.5, 0.0) * 50.0),
    )
    if relative_volume is None:
        volume_score = 50.0
    elif relative_volume >= 1.2:
        volume_score = 100.0
    elif relative_volume >= 1.0:
        volume_score = 70.0
    else:
        volume_score = 40.0

    score = (
        0.35 * close_score
        + 0.25 * gap_score
        + 0.20 * range_score
        + 0.20 * volume_score
    )
    stabilized = (
        score >= 70.0
        and close_location >= 0.50
        and (gap_atr is None or gap_atr <= 2.5)
    )
    return {
        "post_earnings_stabilization_score": round(float(score), 2),
        "post_earnings_stabilization_status": (
            "STABILIZED" if stabilized else "UNSTABLE"
        ),
        "post_earnings_closed_bars": int(len(after_event)),
        "post_earnings_gap_atr": (
            round(float(gap_atr), 3) if gap_atr is not None else None
        ),
        "post_earnings_range_atr": round(float(range_atr), 3),
        "post_earnings_close_location": round(float(close_location), 3),
        "post_earnings_stabilization_reason": (
            "post_earnings_price_action_stabilized"
            if stabilized
            else "post_earnings_price_action_not_stabilized"
        ),
    }
