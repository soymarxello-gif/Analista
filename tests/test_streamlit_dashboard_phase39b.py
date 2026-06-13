from __future__ import annotations

import json
import shutil
from pathlib import Path

from tools.streamlit_smoke_test import collect_streamlit_smoke_test, save_streamlit_smoke_test
from ui.report_loader import SOURCE_SPECS, load_all_ui_sources


ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_app_imports_and_smoke_test_passes():
    data = collect_streamlit_smoke_test(root=ROOT)

    assert data["status"] == "PASS"
    assert data["app_exists"] is True
    assert data["import_ok"] is True
    assert data["view_models_ok"] is True
    assert data["read_only"] is True
    assert data["guardrails"]["forbidden_hits"] == []


def test_streamlit_app_uses_loader_and_view_models_only_for_data_boundary():
    text = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "load_all_ui_sources(ROOT)" in text
    assert "build_candidate_table_model" in text
    assert "build_quality_gate_model" in text
    assert "build_paper_trading_model" in text
    assert "build_cycle_audit_model" in text
    assert "build_calibration_model" in text

    forbidden = [
        "run_scanner",
        "data/paper_trading_journal.csv",
        "data/trade_outcomes.csv",
        "to_csv(",
        "write_text(",
        "open(",
    ]
    lower = text.lower()
    assert [item for item in forbidden if item in lower] == []


def test_streamlit_app_has_expected_manual_review_tabs_and_warning():
    text = (ROOT / "app.py").read_text(encoding="utf-8")

    for label in [
        "Overview",
        "Candidates",
        "Quality & guardrails",
        "Paper trading",
        "Follow-up",
        "Cycle audit",
        "Calibration",
        "Paper actions",
        "Reports status",
    ]:
        assert label in text

    assert "Manual review only. No real orders." in text
    assert "No automatic trading" in text
    assert "_".join(["BUY", "SETUP", "ACTIVE"]) not in text
    assert "_".join(["TRIGGER", "CONFIRMED"]) not in text


def test_report_loader_exposes_streamlit_smoke_source(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "streamlit_smoke_test_latest.json").write_text(
        json.dumps({"status": "PASS", "read_only": True}),
        encoding="utf-8",
    )

    sources = load_all_ui_sources(tmp_path)
    streamlit_source = sources["sources"]["streamlit_smoke_test"]

    assert "streamlit_smoke_test" in SOURCE_SPECS
    assert "gui_visuals_audit" in SOURCE_SPECS
    assert streamlit_source["status"] == "AVAILABLE"
    assert streamlit_source["exists"] is True
    assert streamlit_source["data"]["read_only"] is True


def test_streamlit_smoke_test_writes_json_and_markdown(tmp_path: Path):
    shutil.copy2(ROOT / "app.py", tmp_path / "app.py")
    reports = tmp_path / "reports"

    result = save_streamlit_smoke_test(
        root=tmp_path,
        json_out=reports / "streamlit_smoke_test_latest.json",
        markdown_out=reports / "streamlit_smoke_test_latest.md",
    )

    assert result["status"] == "PASS"
    assert (reports / "streamlit_smoke_test_latest.json").exists()
    assert (reports / "streamlit_smoke_test_latest.md").exists()

    data = json.loads((reports / "streamlit_smoke_test_latest.json").read_text(encoding="utf-8"))
    text = (reports / "streamlit_smoke_test_latest.md").read_text(encoding="utf-8")

    assert data["read_only"] is True
    assert "Streamlit smoke test" in text
    assert "read_only: True" in text
