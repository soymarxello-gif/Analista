import pandas as pd

from data.screener_client import _aggregate_rows


def test_aggregate_rows_preserves_multi_source_signal():
    df = pd.DataFrame(
        [
            {"ticker": "AAA", "company": "AAA Inc", "source_channel": "day_gainers", "source_rank": 1, "source_weight": 0.7},
            {"ticker": "AAA", "company": "AAA Inc", "source_channel": "most_actives", "source_rank": 10, "source_weight": 0.6},
            {"ticker": "BBB", "company": "BBB Inc", "source_channel": "day_gainers", "source_rank": 2, "source_weight": 0.7},
        ]
    )

    out = _aggregate_rows(df, {})

    aaa = out[out["ticker"] == "AAA"].iloc[0]
    assert aaa["screener_hit_count"] == 2
    assert "day_gainers" in aaa["source_channels"]
    assert "most_actives" in aaa["source_channels"]
    assert aaa["source_quality_score"] > 0


def test_aggregate_rows_dedupes_ticker():
    df = pd.DataFrame(
        [
            {"ticker": "AAA", "company": "AAA Inc", "source_channel": "x", "source_rank": 1, "source_weight": 1.0},
            {"ticker": "AAA", "company": "AAA Inc", "source_channel": "x", "source_rank": 2, "source_weight": 1.0},
        ]
    )
    out = _aggregate_rows(df, {})
    assert len(out) == 1
    assert out.iloc[0]["screener_hit_count"] == 1
