from __future__ import annotations

from pathlib import Path

RUNBOOK = Path("docs/operator_runbook.md")


def test_operator_runbook_exists():
    assert RUNBOOK.exists()


def test_operator_runbook_contains_core_sections():
    text = RUNBOOK.read_text(encoding="utf-8")

    required_sections = [
        "# Analista - Operator Runbook",
        "## 1. Propósito",
        "## 2. Comando diario principal",
        "## 3. Archivos que se deben abrir primero",
        "## 4. Interpretación de estados",
        "## 5. Quality gate",
        "## 6. Señales operativas",
        "## 7. Reglas para RECHECK_LIVE_QUOTE",
        "## 8. Checklist manual antes de operar",
        "## 17. Definición de release MVP v1.0",
        "## 20. Regla final",
    ]

    for section in required_sections:
        assert section in text


def test_operator_runbook_contains_safety_rules():
    text = RUNBOOK.read_text(encoding="utf-8")

    required_phrases = [
        "No ejecuta órdenes",
        "No operar",
        "RECHECK_LIVE_QUOTE no es entrada",
        "VETO",
        "AVOID",
        "WATCHLIST es monitoreo",
        "TRIGGER_CONFIRMED requiere revisión manual final",
        "Analista no coloca órdenes",
        "manual_review_allowed = False",
        "manual_review_mode = BLOCKED",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_operator_runbook_contains_validation_commands():
    text = RUNBOOK.read_text(encoding="utf-8")

    required_commands = [
        "python .\\tools\\daily_validation.py",
        "python -m pytest -q",
        "python .\\tools\\project_consistency_audit.py",
        "python .\\tools\\release_readiness_check.py",
    ]

    for command in required_commands:
        assert command in text