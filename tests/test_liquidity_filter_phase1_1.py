import pandas as pd

from universe.liquidity_filter import compute_liquidity


def make_df():
    return pd.DataFrame(
        {
            "close": [20.0] * 80,
            "volume": [1_000_000] * 80,
        }
    )


def test_invalid_bid_ask_does_not_auto_fail_but_reduces_score():
    cfg = {
        "liquidity": {
            "min_price": 5,
            "min_dollar_volume_20d": 20000000,
            "min_dollar_volume_60d": 15000000,
            "min_median_to_mean_volume_ratio": 0.5,
            "max_bid_ask_spread_pct": 0.01,
        }
    }
    metadata = {"bid": 19.0, "ask": 0.0}
    result = compute_liquidity("ABC", make_df(), cfg, metadata)

    assert result["liquidity_pass"] is True
    assert result["bid_ask_valid"] is False
    assert result["liquidity_score"] < 1.0
    assert "bid/ask inválido" in result["liquidity_warning"]


def test_valid_wide_spread_can_fail_if_configured():
    cfg = {
        "liquidity": {
            "min_price": 5,
            "min_dollar_volume_20d": 20000000,
            "min_dollar_volume_60d": 15000000,
            "min_median_to_mean_volume_ratio": 0.5,
            "max_bid_ask_spread_pct": 0.001,
        }
    }
    metadata = {"bid": 19.95, "ask": 20.05}
    result = compute_liquidity("ABC", make_df(), cfg, metadata)

    assert result["bid_ask_valid"] is True
    assert result["liquidity_pass"] is False


def test_nominal_share_volume_is_not_a_hard_filter_when_dollar_volume_passes():
    df = pd.DataFrame(
        {
            "close": [200.0] * 80,
            "volume": [125_000] * 80,
        }
    )
    cfg = {
        "liquidity": {
            "min_price": 10,
            "min_dollar_volume_20d": 20_000_000,
            "min_dollar_volume_60d": 15_000_000,
            "min_median_to_mean_volume_ratio": 0.5,
        }
    }

    result = compute_liquidity("HIGH_PRICE", df, cfg, {})

    assert result["avg_volume_20d"] < 300_000
    assert result["dollar_volume_20d"] == 25_000_000
    assert result["dollar_volume_60d"] == 25_000_000
    assert result["liquidity_pass"] is True


def test_long_term_dollar_volume_below_floor_fails():
    df = pd.DataFrame(
        {
            "close": [20.0] * 80,
            "volume": [700_000] * 60 + [1_100_000] * 20,
        }
    )
    cfg = {
        "liquidity": {
            "min_price": 10,
            "min_dollar_volume_20d": 20_000_000,
            "min_dollar_volume_60d": 18_000_000,
            "min_median_to_mean_volume_ratio": 0.5,
        }
    }

    result = compute_liquidity("RECENT_SPIKE", df, cfg, {})

    assert result["dollar_volume_20d"] >= 20_000_000
    assert result["dollar_volume_60d"] < 18_000_000
    assert result["liquidity_pass"] is False
    assert "dollar_volume_60d" in result["liquidity_warning"]
