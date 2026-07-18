from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.scan_schema import assert_scan_schema, validate_scan_schema


def _valid_scan() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "TEST",
                "signal": "TRIGGER_CONFIRMED",
                "final_score": 88.0,
                "final_trade_score": 90.0,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "all_veto_reasons": "",
                "penalty_reasons": "",
                "actionable_entry": 101.0,
                "actionable_stop": 97.0,
                "actionable_target": 113.0,
                "theoretical_entry": 101.0,
                "theoretical_stop": 97.0,
                "theoretical_target": 113.0,
                "legacy_rank": 1,
                "trade_rank": 1,
                "rank_delta": 0,
                "run_trust_status": "TRUSTED",
                "run_trust_reasons": "",
                "critical_essential_sources": "",
                "run_manual_review_required": False,
                "trigger_confirmed": True,
                "rr": 3.0,
            }
        ]
    )


def main() -> int:
    valid = _valid_scan()
    assert_scan_schema(valid)
    missing = valid.drop(columns=["quote_status"])
    assert any(item.code == "missing_columns" for item in validate_scan_schema(missing))
    veto = valid.copy()
    veto.loc[0, "signal"] = "VETO"
    assert any(item.code == "veto_actionable_level" for item in validate_scan_schema(veto))
    low_quote = valid.copy()
    low_quote.loc[0, "execution_quote_quality"] = "LOW"
    assert any(item.code == "trigger_with_low_quote" for item in validate_scan_schema(low_quote))
    ready = valid.copy()
    ready.loc[0, "signal"] = "READY_WAIT_TRIGGER"
    assert any(item.code == "ready_with_confirmed_trigger" for item in validate_scan_schema(ready))
    print("OK: scan schema contract validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
