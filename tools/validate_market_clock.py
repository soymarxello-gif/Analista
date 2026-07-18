from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.market_clock import evaluate_scheduled_slot, is_nyse_session


def main() -> int:
    assert is_nyse_session(datetime(2026, 7, 17).date())
    assert not is_nyse_session(datetime(2026, 7, 4).date())
    summer = evaluate_scheduled_slot("20 13 * * 1-5", datetime(2026, 7, 20, 13, 20, tzinfo=timezone.utc))
    assert summer.should_run and summer.scheduled_for_et.startswith("2026-07-20T09:20")
    wrong_summer = evaluate_scheduled_slot("20 14 * * 1-5", datetime(2026, 7, 20, 14, 20, tzinfo=timezone.utc))
    assert not wrong_summer.should_run and wrong_summer.reason == "inactive_dst_slot"
    winter = evaluate_scheduled_slot("20 14 * * 1-5", datetime(2026, 1, 5, 14, 20, tzinfo=timezone.utc))
    assert winter.should_run and winter.scheduled_for_et.startswith("2026-01-05T09:20")
    holiday = evaluate_scheduled_slot("20 14 * * 1-5", datetime(2026, 12, 25, 14, 20, tzinfo=timezone.utc))
    assert not holiday.should_run and holiday.reason == "nyse_closed"
    print("OK: XNYS calendar, DST slots and 09:20 ET gate validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
