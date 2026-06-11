from scoring.operational_priority import calculate_operational_priority


def base_row():
    return {
        "final_score": 88,
        "data_quality_score": 0.95,
        "data_quality_confidence": "HIGH",
        "liquidity_score": 0.95,
        "source_quality_score": 0.85,
        "options_score": 0.70,
        "options_confidence": "HIGH",
        "bid_ask_valid": True,
        "options_crowded_bullish": False,
        "pre_veto_signal": "TRIGGER_CONFIRMED",
        "signal": "TRIGGER_CONFIRMED",
        "veto_reasons": "",
    }


def test_high_quality_buy_gets_high_priority():
    result = calculate_operational_priority(base_row(), {})
    assert result["operational_priority_score"] >= 70
    assert result["operational_priority_bucket"] in {"A_HIGH_PRIORITY", "B_REVIEW"}


def test_low_quality_reduces_priority():
    good = calculate_operational_priority(base_row(), {})

    row = base_row()
    row["data_quality_score"] = 0.50
    row["data_quality_confidence"] = "LOW"
    row["source_quality_score"] = 0.25
    row["options_confidence"] = "LOW"

    bad = calculate_operational_priority(row, {})

    assert bad["operational_priority_score"] < good["operational_priority_score"]
    assert "data_quality_score bajo" in bad["operational_priority_warning"]


def test_veto_strong_candidate_remains_visible_but_penalized():
    row = base_row()
    row["signal"] = "VETO"
    row["veto_reasons"] = "missing_critical_data"

    result = calculate_operational_priority(row, {})

    assert result["operational_priority_score"] < calculate_operational_priority(base_row(), {})["operational_priority_score"]
    assert result["operational_priority_score"] > 20
    assert "candidato fuerte bloqueado por veto" in result["operational_priority_warning"]


def test_crowded_options_penalty():
    normal = calculate_operational_priority(base_row(), {})

    row = base_row()
    row["options_crowded_bullish"] = True

    crowded = calculate_operational_priority(row, {})

    assert crowded["operational_priority_score"] < normal["operational_priority_score"]
    assert "options crowded bullish" in crowded["operational_priority_warning"]
