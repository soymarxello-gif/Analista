import pandas as pd

from engine.scan_audit_engine import audit_scan_dataframe


def test_audit_detects_missing_rr_column():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "VETO",
                "final_score": 90,
                "entry": 10,
                "stop": 9,
                "target": 12,
                "setup_type": "BREAKOUT",
                "trend_score": 0.9,
                "liquidity_pass": True,
                "data_quality_score": 0.9,
                "data_quality_confidence": "HIGH",
                "veto_reasons": "rr_below_minimum",
            }
        ]
    )

    report = audit_scan_dataframe(df)
    assert report["status"] == "FAIL"
    assert "rr" in ",".join(report["summary"]["missing_required_columns"])


def test_audit_warns_when_all_veto_rr_below_minimum():
    df = pd.DataFrame(
        [
            {
                "ticker": f"AAA{i}",
                "signal": "VETO",
                "final_score": 80,
                "entry": 10,
                "stop": 9,
                "target": 12,
                "rr": 1.0,
                "setup_type": "BREAKOUT",
                "trend_score": 0.9,
                "liquidity_pass": True,
                "data_quality_score": 0.9,
                "data_quality_confidence": "HIGH",
                "veto_reasons": "rr_below_minimum",
            }
            for i in range(10)
        ]
    )

    report = audit_scan_dataframe(df)
    assert report["status"] == "WARN"
    assert any("todos los candidatos tienen rr_below_minimum" in x for x in report["warnings"])


def test_audit_passes_clean_small_scan():
    df = pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "pre_veto_signal": "TRIGGER_CONFIRMED",
                "signal": "TRIGGER_CONFIRMED",
                "recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
                "manual_quote_check_required": False,
                "quote_recheck_priority": "NONE",
                "quote_recheck_reason": "",
                "final_score": 90,
                "final_trade_score": 88,
                "asset_quality_score": 86,
                "setup_quality_score": 90,
                "context_score": 70,
                "institutional_score": 65,
                "score_breakdown": "{}",
                "entry": 10,
                "stop": 9,
                "target": 12,
                "rr": 2.0,
                "setup_type": "BREAKOUT",
                "trend_score": 0.9,
                "liquidity_pass": True,
                "liquidity_score": 0.95,
                "data_quality_score": 0.95,
                "data_quality_confidence": "HIGH",
                "veto_reasons": "",
                "all_veto_reasons": "",
                "penalty_reasons": "",
                "reason_summary": "BREAKOUT | score 90 | RS 0.9 | trend 0.9 | R:R 2.0",
                "bid_ask_valid": True,
                "bid_ask_warning": "",
                "spread_validated_pct": 0.001,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "options_score": 0.7,
                "options_bias": "BULLISH_WITH_DATA",
                "options_confidence": "HIGH",
                "options_liquidity_score": 1.0,
                "options_crowded_bullish": False,
                "options_crowded_bearish": False,
                "stop_method": "structural:pivot_low",
                "target_method": "pivot_high",
                "risk_pct": 0.10,
                "reward_pct": 0.20,
                "stop_atr_multiple": 1.2,
                "stop_atr_status": "IDEAL",
                "legacy_rank": 1,
                "trade_score_rank": 1,
                "operational_rank": 1,
                "rank_delta_trade_vs_legacy": 0,
                
            }
        ]
    )

    report = audit_scan_dataframe(df)

    assert report["status"] == "PASS"
    assert report["summary"]["missing_required_columns"] == []
    assert report["summary"]["missing_recommended_columns"] == []
