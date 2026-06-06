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


def test_operating_constraints_long_only_no_etfs():
    cfg = load_config()
    assert cfg["trading_profile"]["direction"] == "long_only"
    assert cfg["trading_profile"]["allow_etfs_as_tradable_assets"] is False
    assert cfg["trading_profile"]["asset_class"] == "common_stocks"
