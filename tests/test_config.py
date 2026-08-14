from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.yaml"


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        assert key not in mapping, f"Clave duplicada en config.yaml: {key!r}"
        value = loader.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_mapping,
)


def load_config() -> dict:
    with CONFIG.open("r", encoding="utf-8") as f:
        return yaml.load(f, Loader=UniqueKeyLoader)


def test_config_has_no_duplicate_top_level_keys():
    cfg = load_config()
    assert isinstance(cfg, dict)
    assert "project" in cfg
    assert "scoring_weights" in cfg


def test_scoring_weights_sum_to_100():
    cfg = load_config()
    weights = cfg["scoring_weights"]
    total = sum(float(v) for v in weights.values())
    assert abs(total - 100.0) < 0.01


def test_options_weights_sum_to_1():
    cfg = load_config()
    weights = cfg["options_flow"]["weights"]
    total = sum(float(v) for v in weights.values())
    assert abs(total - 1.0) < 0.01


def test_data_source_cache_has_fundamentals_and_options():
    cfg = load_config()
    ttl = cfg["data_sources"]["cache_ttl_minutes"]
    assert "fundamentals" in ttl
    assert "options" in ttl


def test_operating_constraints_long_only_stocks_and_etfs():
    cfg = load_config()
    assert cfg["project"]["version"] == "1.81.0"
    assert cfg["trading_profile"]["direction"] == "long_only"
    assert cfg["trading_profile"]["holding_period_min_days"] == 4
    assert cfg["trading_profile"]["allow_etfs_as_tradable_assets"] is True
    assert cfg["trading_profile"]["asset_class"] == "common_stocks_and_etfs"
    assert cfg["universe"]["mode"] == "us_listed_common_equities_and_etfs"
    assert cfg["universe"]["allowed_quote_types"] == ["EQUITY", "ETF"]


def test_institutional_discovery_contract_has_no_pre_setup_top_n():
    cfg = load_config()
    engine = cfg["institutional_engine"]
    discovery = engine["discovery_filters"]

    assert cfg["data_sources"]["primary"] == "institutional_point_in_time_store"
    assert engine["enabled"] is True
    assert engine["full_universe_before_setup_filter"] is True
    assert engine["arbitrary_top_n_before_discovery"] is False
    assert discovery == {
        "rsi14_min": 25,
        "rsi14_max": 65,
        "require_rsi6_above_rsi14": True,
    }
    assert engine["feeds"] == {
        "execution_equities": "SIP",
        "options": "OPRA",
        "iex_mode": "degraded_research_only",
    }


def test_context_domains_are_advisory_only_and_missing_data_never_filters():
    cfg = load_config()
    policy = cfg["selection_policy"]
    assert policy["basis"] == "technical_setup_only"
    assert policy["missing_context_policy"] == "warn_never_filter_or_penalize"
    assert set(policy["context_only_components"]) >= {
        "market_regime", "fundamentals", "options_flow"
    }
    assert cfg["fundamentals"]["selection_role"] == "advisory_only"
    assert cfg["options_flow"]["selection_role"] == "advisory_only"
