from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.ui_data_contract_audit import save_ui_data_contract_audit
from ui.report_loader import (
    OPTIONAL_SOURCE_NAMES,
    load_all_ui_sources,
    load_csv_report,
    load_json_report,
    load_markdown_report,
)
from ui.view_models import build_status_overview


def test_load_json_report_missing_returns_missing(tmp_path: Path):
    result = load_json_report(tmp_path / "missing.json")

    assert result["status"] == "MISSING"
    assert result["data"] == {}


def test_load_json_report_invalid_returns_invalid(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{not-json", encoding="utf-8")

    result = load_json_report(path)

    assert result["status"] == "INVALID"
    assert result["data"] == {}


def test_load_csv_report_missing_returns_empty_dataframe_and_missing(tmp_path: Path):
    df = load_csv_report(tmp_path / "missing.csv")

    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert df.attrs["status"] == "MISSING"


def test_load_csv_report_valid_returns_available(tmp_path: Path):
    path = tmp_path / "report.csv"
    path.write_text("ticker,signal\nAAA,WATCHLIST\n", encoding="utf-8")

    df = load_csv_report(path)

    assert df.attrs["status"] == "AVAILABLE"
    assert df.loc[0, "ticker"] == "AAA"


def test_load_markdown_report_missing_returns_empty_text(tmp_path: Path):
    assert load_markdown_report(tmp_path / "missing.md") == ""


def test_load_all_ui_sources_empty_reports_does_not_raise(tmp_path: Path):
    sources = load_all_ui_sources(tmp_path)

    assert sources["summary"]["total_sources"] > 0
    assert sources["summary"]["missing_sources"] > 0
    assert sources["summary"]["optional_missing_sources"] == len(OPTIONAL_SOURCE_NAMES)


def test_optional_ai_review_missing_does_not_warn_status_overview() -> None:
    sources = {
        "summary": {
            "available_sources": 1,
            "missing_sources": 0,
            "optional_missing_sources": 1,
            "invalid_sources": 0,
            "empty_sources": 0,
        },
        "sources": {
            "daily_quality_gate": {"status": "AVAILABLE", "optional": False},
            "ai_review_latest": {"status": "MISSING", "optional": True},
        },
    }

    model = build_status_overview(sources)

    assert model["status"] == "PASS"
    assert model["warnings"] == []


def test_ui_data_contract_audit_generates_json_and_markdown(tmp_path: Path):
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "report_loader.py").write_text("# loader\n", encoding="utf-8")
    (tmp_path / "ui" / "view_models.py").write_text("# models\n", encoding="utf-8")
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "manual_review_top.csv").write_text("ticker,signal\nAAA,WATCHLIST\n", encoding="utf-8")
    (reports / "daily_quality_gate_latest.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")

    result = save_ui_data_contract_audit(
        root=tmp_path,
        json_out=reports / "ui_data_contract_audit_latest.json",
        markdown_out=reports / "ui_data_contract_audit_latest.md",
    )

    assert result["status"] in {"PASS", "WARN"}
    assert (reports / "ui_data_contract_audit_latest.json").exists()
    assert (reports / "ui_data_contract_audit_latest.md").exists()


def test_loader_outputs_do_not_contain_disabled_or_trigger_state_names(tmp_path: Path):
    path = tmp_path / "report.csv"
    path.write_text("ticker,signal\nAAA,WATCHLIST\n", encoding="utf-8")

    df = load_csv_report(path)
    rendered = df.to_json()
    disabled_signal = "_".join(["BUY", "SETUP", "ACTIVE"])
    trigger_signal = "_".join(["TRIGGER", "CONFIRMED"])

    assert disabled_signal not in rendered
    assert trigger_signal not in rendered
