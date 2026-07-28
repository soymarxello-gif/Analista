from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.gui_visuals_audit import collect_gui_visuals_audit, save_gui_visuals_audit
from ui import charts

ROOT = Path(__file__).resolve().parents[1]


def _model(rows: list[dict]) -> dict:
    return {"data": {"rows": rows}, "summary": {}}


def test_charts_module_imports_and_empty_models_are_safe():
    builders = [
        charts.build_signal_distribution_chart_data,
        charts.build_recommendation_distribution_chart_data,
        charts.build_quote_quality_chart_data,
        charts.build_candidate_score_chart_data,
        charts.build_r_multiple_chart_data,
        charts.build_calibration_bucket_chart_data,
    ]
    for builder in builders:
        result = builder({})
        assert result["status"] in {"EMPTY", "PASS"}
        assert isinstance(result["dataframe"], pd.DataFrame)


def test_signal_distribution_empty_is_controlled():
    result = charts.build_signal_distribution_chart_data(_model([]))
    assert result["status"] == "EMPTY"
    assert result["message"] == charts.NO_CHART_DATA


def test_quote_quality_missing_columns_does_not_fail():
    result = charts.build_quote_quality_chart_data(_model([{"ticker": "AAA"}]))
    assert result["status"] == "EMPTY"


def test_candidate_score_chart_top_20_sorted_by_final_trade_score():
    rows = [{"ticker": f"T{i:02d}", "final_trade_score": str(i)} for i in range(25)]
    result = charts.build_candidate_score_chart_data(_model(rows))
    frame = result["dataframe"]
    assert len(frame) == 20
    assert frame.iloc[0]["ticker"] == "T24"
    assert frame.iloc[-1]["ticker"] == "T05"


def test_horizontal_chart_uses_nominal_y_and_quantitative_x():
    source = charts.build_signal_distribution_chart_data(
        _model([{"signal": "WATCHLIST"}, {"signal": "VETO"}])
    )
    chart = charts.build_horizontal_bar_chart(source)
    assert chart is not None
    spec = chart.to_dict()
    encoding = spec["layer"][0]["encoding"]
    assert encoding["y"]["type"] == "nominal"
    assert encoding["x"]["type"] == "quantitative"


def test_horizontal_chart_rejects_empty_or_zero_only_data():
    assert charts.build_horizontal_bar_chart({"dataframe": pd.DataFrame()}) is None
    zero_data = {"dataframe": pd.DataFrame([{"value": "EMPTY", "count": 0}])}
    assert charts.build_horizontal_bar_chart(zero_data) is None


def test_app_uses_charts_module_and_has_no_order_execution_terms():
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from ui import charts as ui_charts" in text
    assert "ui_charts." in text
    assert "st.bar_chart" not in text
    assert "build_horizontal_bar_chart" in text
    lower = text.lower()
    assert "shell=true" not in lower
    for term in ["send_order", "place_order", "buy_order", "sell_order"]:
        assert term not in lower


def test_gui_visuals_audit_generates_json_and_markdown(tmp_path: Path):
    reports = tmp_path / "reports"
    result = save_gui_visuals_audit(
        root=ROOT,
        json_out=reports / "gui_visuals_audit_latest.json",
        markdown_out=reports / "gui_visuals_audit_latest.md",
    )
    assert result["status"] in {"PASS", "WARN"}
    assert (reports / "gui_visuals_audit_latest.json").exists()
    assert (reports / "gui_visuals_audit_latest.md").exists()
    data = json.loads((reports / "gui_visuals_audit_latest.json").read_text(encoding="utf-8"))
    assert data["charts_module_exists"] is True
    assert data["app_uses_charts"] is True
    assert data["empty_data_safe"] is True
    assert data["critical_failures"] == 0


def test_current_project_gui_visuals_audit_has_no_critical_failure():
    data = collect_gui_visuals_audit(root=ROOT)
    assert data["critical_failures"] == 0
    assert data["status"] in {"PASS", "WARN"}
