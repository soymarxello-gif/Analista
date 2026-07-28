import pandas as pd
import yaml

from data import screener_client
from data.screener_client import _aggregate_rows, run_screeners


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


def test_custom_liquid_universe_uses_paged_equity_query(monkeypatch, tmp_path):
    calls = []

    def fake_screen(query, **kwargs):
        calls.append(kwargs)
        offset = kwargs.get("offset")
        if offset == 0:
            return {
                "quotes": [
                    {
                        "symbol": "AAA",
                        "shortName": "AAA Inc",
                        "exchange": "NMS",
                        "quoteType": "EQUITY",
                        "regularMarketPrice": 20,
                        "marketCap": 3_000_000_000,
                    },
                    {
                        "symbol": "BBB",
                        "shortName": "BBB Inc",
                        "exchange": "NYQ",
                        "quoteType": "EQUITY",
                        "regularMarketPrice": 30,
                        "marketCap": 4_000_000_000,
                    },
                ]
            }
        if offset == 2:
            return {
                "quotes": [
                    {
                        "symbol": "CCC",
                        "shortName": "CCC Inc",
                        "exchange": "ASE",
                        "quoteType": "EQUITY",
                        "regularMarketPrice": 40,
                        "marketCap": 5_000_000_000,
                    }
                ]
            }
        raise AssertionError(offset)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(screener_client.yf, "screen", fake_screen)

    result = run_screeners(
        {
            "screener": {
                "target_size": 3,
                "page_size": 2,
                "sort_field": "avgdailyvol3m",
                "sort_asc": False,
                "custom_queries": {
                    "custom_liquid_universe": {
                        "enabled": True,
                        "min_market_cap_usd": 2_500_000_000,
                        "min_price": 10,
                        "min_avg_volume_3m": 500_000,
                        "exchanges": ["NMS", "NYQ", "ASE"],
                        "target_size": 3,
                        "page_size": 2,
                    }
                },
                "channels": {},
                "channel_source_weights": {"custom_liquid_universe": 1.0},
            }
        }
    )

    assert result.used_fallback is False
    assert set(result.dataframe["ticker"]) == {"AAA", "BBB", "CCC"}
    assert set(result.dataframe["source_channel"]) == {"custom_liquid_universe"}
    assert calls == [
        {"offset": 0, "size": 2, "sortField": "avgdailyvol3m", "sortAsc": False},
        {"offset": 2, "size": 1, "sortField": "avgdailyvol3m", "sortAsc": False},
    ]


def test_custom_liquid_universe_can_page_until_exhausted_without_target_cap(monkeypatch, tmp_path):
    calls = []

    def fake_screen(query, **kwargs):
        calls.append(kwargs)
        offset = kwargs.get("offset")
        symbols = {
            0: ["AAA", "BBB"],
            2: ["CCC", "DDD"],
            4: ["EEE"],
        }.get(offset)
        if symbols is None:
            raise AssertionError(offset)
        return {
            "quotes": [
                {
                    "symbol": symbol,
                    "shortName": f"{symbol} Inc",
                    "exchange": "NMS",
                    "quoteType": "EQUITY",
                    "regularMarketPrice": 20,
                    "marketCap": 3_000_000_000,
                }
                for symbol in symbols
            ]
        }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(screener_client.yf, "screen", fake_screen)

    result = run_screeners(
        {
            "screener": {
                "target_size": 0,
                "page_size": 2,
                "max_pages_per_custom_query": 5,
                "sort_field": "avgdailyvol3m",
                "sort_asc": False,
                "custom_queries": {
                    "custom_liquid_universe": {
                        "enabled": True,
                        "target_size": 0,
                        "page_size": 2,
                    }
                },
                "channels": {},
                "channel_source_weights": {"custom_liquid_universe": 1.0},
            }
        }
    )

    assert result.used_fallback is False
    assert result.dataframe["ticker"].tolist() == ["AAA", "BBB", "CCC", "DDD", "EEE"]
    assert calls == [
        {"offset": 0, "size": 2, "sortField": "avgdailyvol3m", "sortAsc": False},
        {"offset": 2, "size": 2, "sortField": "avgdailyvol3m", "sortAsc": False},
        {"offset": 4, "size": 2, "sortField": "avgdailyvol3m", "sortAsc": False},
    ]


def test_productive_config_uses_custom_liquid_yahoo_screener_first():
    with open("config.yaml", "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    screener = config["screener"]
    custom = screener["custom_queries"]["custom_liquid_universe"]
    assert screener["target_size"] == 0
    assert screener["max_universe_after_dedupe"] == 0
    assert custom["enabled"] is True
    assert custom["min_market_cap_usd"] == 2_500_000_000
    assert custom["min_avg_volume_3m"] <= 250_000
    assert custom["exchanges"] == ["NMS", "NYQ", "ASE"]
    assert custom["target_size"] == 0
    assert custom["page_size"] == 250
    assert custom["sort_field"] == "avgdailyvol3m"
    assert screener["channels"]["day_gainers"]["enabled"] is False
    assert screener["channels"]["most_actives"]["enabled"] is False
