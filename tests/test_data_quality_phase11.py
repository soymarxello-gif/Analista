from __future__ import annotations

from data.data_quality import score_data_quality


def base_row() -> dict:
    return {
        "ticker": "AAA",
        "price": 100.0,
        "market_cap": 5_000_000_000,
        "avg_volume_20d": 1_000_000,
        "dollar_volume_20d": 100_000_000,
        "liquidity_pass": True,
        "trend_score": 0.9,
        "rr": 2.0,
        "setup_type": "BREAKOUT",
        "atr": 2.5,
        "atr_pct": 0.025,
        "relative_volume": 1.3,
        "volume_score": 0.8,
        "momentum_score": 0.7,
        "rs_score": 0.85,
        "sector": "Technology",
        "industry": "Software",
        "earnings_date": "2026-07-20",
        "days_to_earnings": 30,
        "revenue_growth": 0.2,
        "earnings_growth": 0.3,
        "operating_margins": 0.2,
        "debt_to_equity": 0.4,
        "return_on_equity": 0.15,
        "options_data_available": False,
        "options_score": 0.5,
        "options_bias": "UNKNOWN_OPTIONS_FLOW",
        "options_confidence": "UNKNOWN",
        "put_call_volume_ratio": None,
        "put_call_oi_ratio": None,
        "call_volume_share": None,
        "near_call_oi_share": None,
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "bid_ask_valid": True,
    }


def test_missing_options_do_not_lower_core_data_quality():
    row = base_row()

    result = score_data_quality(row)

    assert result["core_data_quality_score"] == 1.0
    assert result["data_quality_confidence"] == "HIGH"
    assert result["missing_critical_fields"] == ""
    assert "put_call_volume_ratio" in result["options_missing_fields"]


def test_missing_sector_industry_are_fundamental_not_core():
    row = base_row()
    row["sector"] = None
    row["industry"] = None

    result = score_data_quality(row)

    assert result["core_missing_fields"] == ""
    assert "sector" in result["fundamental_missing_fields"]
    assert "industry" in result["fundamental_missing_fields"]
    assert result["data_quality_confidence"] in {"HIGH", "MEDIUM"}


def test_missing_core_field_forces_low_confidence():
    row = base_row()
    row["rr"] = None

    result = score_data_quality(row)

    assert "rr" in result["core_missing_fields"]
    assert result["data_quality_confidence"] == "LOW"


def test_invalid_execution_quote_reduces_execution_component_only():
    row = base_row()
    row["quote_status"] = "INVALID"
    row["execution_quote_quality"] = "LOW"
    row["bid_ask_valid"] = False

    result = score_data_quality(row)

    assert result["core_data_quality_score"] == 1.0
    assert result["execution_data_quality_score"] < 0.5
    assert result["missing_critical_fields"] == ""