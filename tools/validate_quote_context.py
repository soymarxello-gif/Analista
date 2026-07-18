from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.quote_context import (
    add_quote_temporal_context,
    normalize_market_session,
    temporal_quote_penalty,
)


def main() -> int:
    now = datetime(2026, 7, 18, 15, 0, tzinfo=timezone.utc)
    row = add_quote_temporal_context(
        {"quote_timestamp": "2026-07-18T14:55:00Z", "market_session": "REGULAR"},
        now=now,
    )
    assert row["quote_age_seconds"] == 300.0
    assert normalize_market_session("REGULAR_MARKET") == "REGULAR"

    config = {"quote_quality": {"max_age_seconds_regular": 900}}
    assert temporal_quote_penalty(row, config) == (None, None)

    stale = add_quote_temporal_context(
        {"quote_timestamp": "2026-07-18T14:30:00Z", "market_session": "REGULAR"},
        now=now,
    )
    assert temporal_quote_penalty(stale, config) == ("STALE_POSSIBLE", "LOW")

    unknown = add_quote_temporal_context({"market_session": "REGULAR"}, now=now)
    assert temporal_quote_penalty(unknown, config) == (None, None)

    print("OK: temporal quote context validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
