from __future__ import annotations

import pandas as pd

from scoring.volume_score import score_volume


def test_volume_score_handles_pandas_na_without_crashing() -> None:
    df = pd.DataFrame(
        [
            {
                "relative_volume": 1.2,
                "close_location_value": pd.NA,
                "obv_slope": pd.NA,
            }
        ]
    )

    score = score_volume(df)

    assert 0.0 <= score <= 1.0


def test_volume_score_keeps_valid_numeric_behavior() -> None:
    df = pd.DataFrame(
        [
            {
                "relative_volume": 1.5,
                "close_location_value": 0.8,
                "obv_slope": 10.0,
            }
        ]
    )

    assert score_volume(df) == 0.8
