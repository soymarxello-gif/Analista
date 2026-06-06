from scoring.final_score import calculate_final_score

def test_final_score_range():
    config = {"scoring_weights": {"relative_strength": 11.4, "trend": 11.0}}
    score = calculate_final_score({"rs_score": 1, "trend_score": 1}, config)
    assert score == 22.4
