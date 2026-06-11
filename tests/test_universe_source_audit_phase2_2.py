import pandas as pd

from engine.universe_source_audit import audit_universe_sources


def test_universe_audit_warns_momentum_concentration():
    df = pd.DataFrame(
        [
            {"ticker": f"AAA{i}", "source_channels": "day_gainers", "sector": "Technology", "screener_hit_count": 1}
            for i in range(20)
        ]
    )

    cfg = {
        "screener": {
            "bias_control": {
                "max_momentum_sources_share": 0.60,
                "max_single_source_share": 0.50,
                "max_top_sector_share": 0.50,
            }
        }
    }

    report = audit_universe_sources(df, config=cfg)

    assert report["status"] == "WARN"
    assert any("momentum" in w for w in report["warnings"])


def test_universe_audit_passes_diversified_sources():
    df = pd.DataFrame(
        [
            {"ticker": "AAA", "source_channels": "day_gainers,value", "sector": "Technology", "screener_hit_count": 2},
            {"ticker": "BBB", "source_channels": "quality", "sector": "Healthcare", "screener_hit_count": 1},
            {"ticker": "CCC", "source_channels": "growth", "sector": "Industrials", "screener_hit_count": 1},
            {"ticker": "DDD", "source_channels": "value", "sector": "Financial Services", "screener_hit_count": 1},
        ]
    )

    cfg = {
        "screener": {
            "bias_control": {
                "max_momentum_sources_share": 0.60,
                "max_single_source_share": 0.80,
                "max_top_sector_share": 0.80,
            }
        }
    }

    report = audit_universe_sources(df, config=cfg)
    assert report["status"] == "PASS"
