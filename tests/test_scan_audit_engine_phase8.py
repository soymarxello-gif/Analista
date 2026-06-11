from __future__ import annotations

import pandas as pd

from engine.scan_audit_engine import audit_scan_dataframe


def test_audit_accepts_new_phase8_columns():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "rank": 1,
                "pre_veto_signal": "TRIGGER_CONFIRMED",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "setup_type": "PULLBACK",
                "final_score": 75,
                "final_trade_score": 72,
                "asset_quality_score": 80,
                "setup_quality_score": 70,
                "entry": 100,
                "stop": 95,
                "target": 115,
                "rr": 3.0,
                "liquidity_score": 0.9,
                "data_quality_score": 0.95,
                "data_quality_confidence": "HIGH",
                "veto_reasons": "",
                "all_veto_reasons": "",
                "penalty_reasons": "execution_quote_unconfirmed",
                "reason_summary": "PULLBACK | score 75 | R:R 3.0",
                "bid_ask_valid": False,
                "bid_ask_warning": "stale",
                "spread_validated_pct": None,
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "options_score": 0.5,
                "options_bias": "UNKNOWN_OPTIONS_FLOW",
                "options_confidence": "UNKNOWN",
                "options_liquidity_score": 0.0,
                "options_crowded_bullish": False,
                "options_crowded_bearish": False,
                "stop_atr_multiple": 0.8,
                "stop_atr_status": "AGGRESSIVE_TIGHT",
                "score_breakdown": "{}",
            }
        ]
    )

    report = audit_scan_dataframe(df)

    assert "recommendation" not in report["summary"]["missing_recommended_columns"]
    assert "final_trade_score" not in report["summary"]["missing_recommended_columns"]
    assert "quote_status" not in report["summary"]["missing_recommended_columns"]


def test_audit_detects_new_crowded_options_labels():
    df = pd.DataFrame(
        [
            {
                "ticker": f"AAA{i}",
                "signal": "WATCHLIST",
                "final_score": 70,
                "final_trade_score": 70,
                "entry": 100,
                "stop": 95,
                "target": 110,
                "rr": 2.0,
                "setup_type": "PULLBACK",
                "trigger_confirmed": True,
                "liquidity_score": 0.8,
                "data_quality_score": 0.9,
                "data_quality_confidence": "HIGH",
                "veto_reasons": "",
                "reason_summary": "PULLBACK",
                "bid_ask_valid": True,
                "bid_ask_warning": "",
                "spread_validated_pct": 0.001,
                "options_score": 0.6,
                "options_bias": "CROWDED_BULLISH",
                "options_confidence": "HIGH",
                "options_liquidity_score": 1.0,
                "options_crowded_bullish": True,
            }
            for i in range(10)
        ]
    )

    report = audit_scan_dataframe(df)

    assert any("flujo crowded elevado" in w for w in report["warnings"])