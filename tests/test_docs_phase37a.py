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


def test_docs_cover_single_ticker_deep_dive_and_macro_context():
    operating = (DOCS / "OPERATING_MANUAL.md").read_text(encoding="utf-8")
    workflow = (DOCS / "DAILY_WORKFLOW.md").read_text(encoding="utf-8")
    reports = (DOCS / "REPORTS_REFERENCE.md").read_text(encoding="utf-8")
    safety = (DOCS / "SAFETY_RULES.md").read_text(encoding="utf-8")

    assert "single_ticker_deep_dive.py" in operating
    assert "Consulta puntual por ticker" in workflow
    assert "single_ticker_deep_dive_latest" in reports
    assert "Macro context" in safety or "Macro Context" in safety


def test_docs_clarify_stocks_are_operable_and_etfs_contextual():
    readme = Path("README.md").read_text(encoding="utf-8")
    operating = (DOCS / "OPERATING_MANUAL.md").read_text(encoding="utf-8")
    safety = (DOCS / "SAFETY_RULES.md").read_text(encoding="utf-8")

    combined = "\n".join([readme, operating, safety])
    assert "US-listed stocks" in combined
    assert "ETFs" in combined
    assert "context" in combined.lower()
    assert "automatic tradable candidates" in combined or "automatic operable candidates" in combined
