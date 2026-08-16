from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scoring.signal_classifier import classify_signal


FIXTURE = (
    ROOT
    / "android"
    / "app"
    / "src"
    / "test"
    / "resources"
    / "signal_semantics_parity.json"
)

CONFIG = {
    "filters": {"min_price": 10, "min_market_cap_usd": 1_500_000_000},
    "risk_reward": {"min_rr_absolute": 1.5},
    "veto_rules": {"thresholds": {"min_trend_score": 0.55}},
    "signal_thresholds": {
        "trigger_confirmed": {"min_score": 80, "min_rr": 2.0},
        "ready_wait_trigger": {"min_score": 80, "min_rr": 1.7},
        "watchlist": {"min_score": 70},
    },
}


def validate() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fixture.get("schemaVersion") != "signal-semantics-parity-1":
        raise AssertionError("unexpected signal semantics fixture version")

    failures: list[tuple[str, str, str, list[str]]] = []
    for case in fixture["cases"]:
        row = {
            "price": case["price"],
            "market_cap": case["marketCap"],
            "quote_type": case["quoteType"],
            "liquidity_pass": case["dataQualityAllowsExecution"],
            "rr": case["rr"],
            "trend_score": case["trendScore"],
            "setup_type": case["setupType"],
            "failed_breakout": case["failedBreakout"],
            "earnings_veto": False,
            "final_trade_score": case["finalTradeScore"],
            "trigger_confirmed": case["triggerConfirmed"],
            "execution_quote_quality": case["executionQuoteQuality"],
        }
        actual, reasons = classify_signal(row, CONFIG)
        expected = case["expectedSignal"]
        if actual != expected:
            failures.append((case["name"], expected, actual, reasons))

    if failures:
        raise AssertionError(f"Android/desktop signal semantics mismatch: {failures}")
    print(f"signal semantics parity OK: {len(fixture['cases'])} cases")


if __name__ == "__main__":
    validate()
