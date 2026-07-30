from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd


NEW_YORK = ZoneInfo("America/New_York")
DEFAULT_CLOSE_CUTOFF = time(16, 20)


def _as_new_york(now: datetime | None = None) -> datetime:
    current = now or datetime.now(tz=NEW_YORK)
    if current.tzinfo is None:
        return current.replace(tzinfo=NEW_YORK)
    return current.astimezone(NEW_YORK)


def _index_date(value: Any) -> object:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(NEW_YORK).tz_localize(None)
    return timestamp.date()


def derive_technical_prices(
    prices: pd.DataFrame,
    *,
    now: datetime | None = None,
    close_cutoff: time = DEFAULT_CLOSE_CUTOFF,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Return the daily bars that are safe for EOD technical calculations.

    Yahoo can expose the current daily candle while the US session is still
    open. Swing indicators must not treat that partial candle as a completed
    observation. The raw frame remains untouched for quote/context use.
    """
    if prices is None or prices.empty:
        return pd.DataFrame(), {
            "technical_as_of_date": None,
            "technical_bar_policy": "CLOSED_DAILY_AND_WEEKLY_ONLY",
            "daily_bar_complete": False,
            "weekly_bar_complete": False,
            "intraday_bar_excluded": False,
        }

    current = _as_new_york(now)
    technical = prices.sort_index().copy()
    latest_date = _index_date(technical.index[-1])
    current_date = current.date()
    intraday_bar_excluded = bool(
        latest_date == current_date and current.time() < close_cutoff
    )
    if intraday_bar_excluded:
        technical = technical.iloc[:-1].copy()

    technical_as_of = (
        _index_date(technical.index[-1]).isoformat() if not technical.empty else None
    )
    weekly_complete = is_latest_week_complete(
        technical.index[-1] if not technical.empty else None,
        now=current,
        close_cutoff=close_cutoff,
    )
    return technical, {
        "technical_as_of_date": technical_as_of,
        "technical_bar_policy": "CLOSED_DAILY_AND_WEEKLY_ONLY",
        "daily_bar_complete": not technical.empty,
        "weekly_bar_complete": weekly_complete,
        "intraday_bar_excluded": intraday_bar_excluded,
    }


def is_latest_week_complete(
    latest_daily_index: Any,
    *,
    now: datetime | None = None,
    close_cutoff: time = DEFAULT_CLOSE_CUTOFF,
) -> bool:
    if latest_daily_index is None:
        return False
    current = _as_new_york(now)
    latest_date = _index_date(latest_daily_index)
    current_iso = current.isocalendar()
    latest_iso = latest_date.isocalendar()
    if (latest_iso.year, latest_iso.week) < (current_iso.year, current_iso.week):
        return True
    if (latest_iso.year, latest_iso.week) > (current_iso.year, current_iso.week):
        return False
    return bool(current.weekday() >= 4 and current.time() >= close_cutoff)


def closed_weekly_close(
    close: pd.Series,
    *,
    now: datetime | None = None,
    weekly_rule: str = "W-FRI",
    close_cutoff: time = DEFAULT_CLOSE_CUTOFF,
) -> tuple[pd.Series, bool]:
    values = pd.to_numeric(close, errors="coerce").dropna()
    if values.empty or not isinstance(values.index, pd.DatetimeIndex):
        return pd.Series(dtype=float), False

    weekly = values.resample(weekly_rule).last().dropna()
    latest_week_complete = is_latest_week_complete(
        values.index[-1],
        now=now,
        close_cutoff=close_cutoff,
    )
    current = _as_new_york(now)
    latest_date = _index_date(values.index[-1])
    same_current_week = latest_date.isocalendar()[:2] == current.date().isocalendar()[:2]
    if same_current_week and not latest_week_complete and not weekly.empty:
        weekly = weekly.iloc[:-1]
    return weekly, latest_week_complete
