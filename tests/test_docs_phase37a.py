from __future__ import annotations

from pathlib import Path

DOCS = Path("docs")


def test_phase37a_required_docs_exist():
    required = [
        "OPERATING_MANUAL.md",
        "DAILY_WORKFLOW.md",
        "REPORTS_REFERENCE.md",
        "SAFETY_RULES.md",
        "CALIBRATION_GUIDE.md",
    ]

    for filename in required:
        assert (DOCS / filename).exists()


def test_safety_rules_contains_no_automatic_purchase_rule():
    text = (DOCS / "SAFETY_RULES.md").read_text(encoding="utf-8")

    assert "No compra automática" in text or "No automatic purchase" in text


def test_daily_workflow_contains_daily_validation_command():
    text = (DOCS / "DAILY_WORKFLOW.md").read_text(encoding="utf-8")

    assert "daily_validation.py" in text


def test_reports_reference_contains_trade_candidate_cards_report():
    text = (DOCS / "REPORTS_REFERENCE.md").read_text(encoding="utf-8")

    assert "trade_candidate_cards_latest" in text


def test_calibration_guide_contains_sample_size_warning():
    text = (DOCS / "CALIBRATION_GUIDE.md").read_text(encoding="utf-8")

    assert "sample_size_warning" in text
