from __future__ import annotations

import json

import pytest

from institutional.providers import Capability, ProviderPolicy
from institutional.shadow import ShadowRegistry


def test_provider_matrix_contains_no_fictitious_tradingview_source():
    ProviderPolicy.validate()
    assert all(contract.provider != "TRADINGVIEW" for contract in ProviderPolicy.CONTRACTS)
    assert ProviderPolicy.execution_provider(Capability.HISTORICAL_PRICE).feed == "SIP"
    assert ProviderPolicy.execution_provider(Capability.EXECUTION_QUOTE) is None
    assert ProviderPolicy.execution_provider(Capability.OPTIONS).feed == "OPRA"


def test_shadow_registry_rejects_in_place_tuning(tmp_path):
    registry = ShadowRegistry(tmp_path)
    registry.append_run({"run_id": "one", "signal_count": 3}, {"threshold": 70}, "model-1")
    with pytest.raises(RuntimeError, match="locked"):
        registry.append_run({"run_id": "two"}, {"threshold": 71}, "model-1")
    rows = [json.loads(line) for line in (tmp_path / "shadow-runs.jsonl").read_text().splitlines()]
    assert rows[0]["configuration_hash"]
