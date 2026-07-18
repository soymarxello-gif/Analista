from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

NEW_YORK_TZ = ZoneInfo("America/New_York")
UTC = timezone.utc
XNYS = xcals.get_calendar("XNYS")


@dataclass(frozen=True)
class ScheduledGate:
    should_run: bool
    reason: str
    market_date: str
    scheduled_for_et: str


def is_nyse_session(day: date) -> bool:
    return bool(XNYS.is_session(pd.Timestamp(day)))


def scheduled_time_et(day: date, hour: int = 9, minute: int = 20) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=NEW_YORK_TZ)


def evaluate_scheduled_slot(
    slot: str | None,
    now_utc: datetime | None = None,
    *,
    target_hour: int = 9,
    target_minute: int = 20,
) -> ScheduledGate:
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    market_day = now.astimezone(NEW_YORK_TZ).date()
    target = scheduled_time_et(market_day, target_hour, target_minute)
    target_utc = target.astimezone(UTC)
    if not is_nyse_session(market_day):
        return ScheduledGate(False, "nyse_closed", market_day.isoformat(), target.isoformat())
    expected_slot = f"{target_utc.minute} {target_utc.hour} * * 1-5"
    if slot and slot.strip() != expected_slot:
        return ScheduledGate(False, "inactive_dst_slot", market_day.isoformat(), target.isoformat())
    return ScheduledGate(True, "scheduled_nyse_premarket_run", market_day.isoformat(), target.isoformat())
