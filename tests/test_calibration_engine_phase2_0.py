from pathlib import Path

import pandas as pd

from engine.calibration_engine import calibrate_weights_from_posttest, summarize_posttest


def make_posttest_csv(path: Path):
    rows = []
    for i in range(40):
        rows.append(
            {
                "ticker": f"AAA{i}",
                "horizon_days": 10,
                "return_close_pct": i / 1000,
                "mfe_pct": i / 800,
                "mae_pct": -i / 2000,
                "signal": "BUY_SETUP_ACTIVE" if i >= 20 else "WATCHLIST",
                "pre_veto_signal": "BUY_SETUP_ACTIVE" if i >= 20 else "WATCHLIST",
                "setup_type": "BREAKOUT" if i >= 20 else "PULLBACK",
                "options_bias": "BULLISH" if i >= 20 else "NEUTRAL",
                "options_confidence": "HIGH",
                "data_quality_confidence": "HIGH",
                "sector": "Technology",
                "rs_score": i / 40,
                "trend_score": i / 40,
                "volume_score": i / 40,
                "rr_score": i / 40,
                "liquidity_score": 1.0,
                "options_score": i / 40,
                "fundamental_score": 0.5,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_summarize_posttest(tmp_path: Path):
    file = tmp_path / "posttest.csv"
    make_posttest_csv(file)

    report = summarize_posttest([file], min_samples=3)

    assert report["status"] == "OK"
    assert report["summary"]["rows"] == 40
    assert "signal_ALL" in report["group_summaries"]


def test_calibrate_weights_from_posttest(tmp_path: Path):
    file = tmp_path / "posttest.csv"
    make_posttest_csv(file)

    config = {
        "scoring_weights": {
            "relative_strength": 11.4,
            "trend": 11.0,
            "volume_accumulation": 10.3,
            "risk_reward_atr": 8.4,
            "liquidity": 7.6,
            "options_flow": 6.1,
            "fundamentals": 5.1,
        }
    }

    report = calibrate_weights_from_posttest(
        [file],
        config=config,
        horizon=10,
        min_samples=20,
        max_delta_pct=0.20,
    )

    assert report["status"] == "OK"
    assert abs(sum(report["proposed_weights"].values()) - 100.0) < 0.05
    assert report["details"]
