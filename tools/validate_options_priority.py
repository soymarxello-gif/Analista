from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.options_priority import calculate_options_priority, select_options_tickers


def main() -> int:
    candidates = [
        {"ticker": "WEAK", "setup_type": "NO_VALID_SETUP", "trend_score": 0.9},
        {"ticker": "GOOD", "setup_type": "PULLBACK", "trend_score": 0.8, "structure_score": 0.8, "rr_score": 0.8, "momentum_score": 0.7, "volume_score": 0.7, "rs_score": 0.8, "liquidity_score": 0.9, "rr": 2.2},
        {"ticker": "BEST", "setup_type": "BREAKOUT", "trend_score": 0.9, "structure_score": 0.95, "rr_score": 0.9, "momentum_score": 0.85, "volume_score": 0.9, "rs_score": 0.9, "liquidity_score": 0.9, "rr": 3.0, "trigger_confirmed": True},
    ]
    assert calculate_options_priority(candidates[2]) > calculate_options_priority(candidates[1])
    assert calculate_options_priority(candidates[0]) == 0.0
    assert select_options_tickers(candidates, 1) == ["BEST"]
    assert select_options_tickers(candidates, 2) == ["BEST", "GOOD"]
    print("OK: options requests are prioritized by preliminary setup quality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
