from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from engine.run_trust import DEGRADED, TRUSTED, UNUSABLE, assess_run_trust, attach_run_trust


def health(**statuses):
    return {"sources": {name: {"health_status": status} for name, status in statuses.items()}}


def main() -> int:
    trusted = assess_run_trust(health(screeners="HEALTHY", price_history_yahoo="HEALTHY"), {})
    assert trusted["run_trust_status"] == TRUSTED
    degraded = assess_run_trust(health(screeners="HEALTHY", price_history_yahoo="DEGRADED"), {})
    assert degraded["run_trust_status"] == DEGRADED
    unusable = assess_run_trust(health(screeners="CRITICAL", price_history_yahoo="HEALTHY"), {})
    assert unusable["run_trust_status"] == UNUSABLE
    frame = attach_run_trust(pd.DataFrame([{"ticker": "AAPL"}]), unusable)
    assert frame.loc[0, "run_trust_status"] == UNUSABLE
    print("OK: execution trust contract blocks unreliable essential-source runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
