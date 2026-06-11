from data.data_quality import score_data_quality


def test_missing_critical_forces_low_confidence():
    row = {
        "ticker": "ABC",
        "price": 10,
        "sector": "Technology",
        "industry": "Software",
        "market_cap": 1_000_000_000,
        "avg_volume_20d": 1_000_000,
        "dollar_volume_20d": 10_000_000,
        "liquidity_pass": True,
        "trend_score": 0.8,
        "rr": None,
        "setup_type": "BREAKOUT",
    }

    result = score_data_quality(row, {})
    assert result["data_quality_confidence"] == "LOW"
    assert "rr" in result["missing_critical_fields"]


def test_complete_core_row_high_confidence():
    row = {
        "ticker": "ABC",
        "price": 10,
        "sector": "Technology",
        "industry": "Software",
        "market_cap": 1_000_000_000,
        "avg_volume_20d": 1_000_000,
        "dollar_volume_20d": 10_000_000,
        "liquidity_pass": True,
        "trend_score": 0.8,
        "rr": 2.1,
        "setup_type": "BREAKOUT",

        # Phase 11 market quality fields
        "atr": 1.2,
        "atr_pct": 0.03,
        "relative_volume": 1.4,
        "volume_score": 0.8,
        "momentum_score": 0.75,
        "rs_score": 0.82,

        # Fundamental/context fields
        "earnings_date": "2026-08-01",
        "days_to_earnings": 30,
        "revenue_growth": 0.1,
        "earnings_growth": 0.1,
        "operating_margins": 0.2,
        "debt_to_equity": 10,
        "return_on_equity": 0.2,

        # Phase 11 options quality fields
        "options_data_available": True,
        "options_score": 0.7,
        "options_bias": "BULLISH_WITH_DATA",
        "options_confidence": "HIGH",
        "put_call_volume_ratio": 0.6,
        "put_call_oi_ratio": 0.8,
        "call_volume_share": 0.55,
        "near_call_oi_share": 0.50,

        # Phase 11 execution quality fields
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "bid_ask_valid": True,
    }

    result = score_data_quality(row, {})
    assert result["data_quality_confidence"] == "HIGH"
    assert result["core_data_quality_score"] == 1.0
    assert result["market_data_quality_score"] == 1.0
    assert result["execution_data_quality_score"] == 1.0
    assert result["missing_critical_fields"] == ""
