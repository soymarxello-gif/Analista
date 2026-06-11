from __future__ import annotations

from tools.project_consistency_audit import audit_config


def test_config_core_rules_are_consistent():
    issues = audit_config()

    assert issues == []