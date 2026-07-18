from __future__ import annotations

import pandas as pd
import pytest

from contracts.scan_schema import assert_scan_schema, validate_scan_schema


def valid_scan() -> pd.DataFrame:
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
                "trigger_confirmed": True,
                "rr": 3.0,
            }
        ]
    )


def test_valid_scan_passes_contract():
    assert validate_scan_schema(valid_scan()) == []
    assert_scan_schema(valid_scan())


def test_missing_required_column_fails():
    df = valid_scan().drop(columns=["quote_status"])
    with pytest.raises(ValueError, match="missing_columns"):
        assert_scan_schema(df)


def test_veto_cannot_expose_actionable_levels():
    df = valid_scan()
    df.loc[0, "signal"] = "VETO"
    violations = validate_scan_schema(df)
    assert any(item.code == "veto_actionable_level" for item in violations)


def test_trigger_cannot_use_low_quote():
    df = valid_scan()
    df.loc[0, "execution_quote_quality"] = "LOW"
    violations = validate_scan_schema(df)
    assert any(item.code == "trigger_with_low_quote" for item in violations)


def test_ready_wait_trigger_cannot_be_confirmed():
    df = valid_scan()
    df.loc[0, "signal"] = "READY_WAIT_TRIGGER"
    violations = validate_scan_schema(df)
    assert any(item.code == "ready_with_confirmed_trigger" for item in violations)
