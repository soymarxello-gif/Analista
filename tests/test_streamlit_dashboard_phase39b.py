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
    assert "build_macro_context_model" in text
    assert "build_calibration_model" in text
    assert "build_paper_trading_model" not in text
    assert "build_cycle_audit_model" not in text

    forbidden = [
        "run_scanner",
        "data/trade_outcomes.csv",
        "to_csv(",
        "write_text(",
        "open(",
    ]
    lower = text.lower()
    assert [item for item in forbidden if item in lower] == []


def test_streamlit_app_has_compact_navigation_and_manual_review_warning():
    text = (ROOT / "app.py").read_text(encoding="utf-8")

    for label in ["Resumen", "Candidatos", "Control"]:
        assert label in text
    assert "Paper trading" not in text
    assert "Estado paper" not in text
    assert "Acciones paper" not in text
    assert "Contexto macro" in text
    assert "Posttest simple 5 / 10 / 15 sesiones" in text
    assert "Actualizar todos los datos" in text
    assert "Ayuda / instrucciones" in text
    assert "Definiciones clave" in text
    assert "Configurar tabla" in text
    assert "Las columnas visibles se guardan automáticamente" in text
    assert "Vista guardada de tabla" not in text
    assert "Buscar ticker" not in text
    assert "Ordenar por" not in text
    assert "Mayor a menor" not in text
    assert "Distribución de señales" not in text
    assert "Consulta puntual por ticker" not in text

    assert 'st.segmented_control(' in text
    assert 'st.tabs(' not in text
    assert "Revisión manual" in (ROOT / "ui" / "layout.py").read_text(encoding="utf-8")
    assert "No automatic trading" in text
    assert "candidate_watchlist" in text
    assert "candidate_watchlist_v3" in text
    assert "Oportunidades operativas" in text
    assert "Radar de investigación" in text
    assert "candidate_research_radar" in text
    assert "No pasan a checklist" in text
    assert '"operational_state"' not in text
    assert "_apply_watchlist_preferences" in text
    assert "selected_candidate = None" in text
    assert "selected_index = int(selected_rows[0]) if selected_rows else 0" not in text
    assert "_".join(["BUY", "SETUP", "ACTIVE"]) not in text
    assert "_".join(["TRIGGER", "CONFIRMED"]) not in text


def test_streamlit_app_uses_compact_cockpit_layout():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    layout_text = (ROOT / "ui" / "layout.py").read_text(encoding="utf-8")

    assert "render_metric_chips" in layout_text
    assert "render_section_heading" in layout_text
    assert "_render_header_actions()" in app_text
    assert "render_no_real_order_notice()" not in app_text
    assert "series_col, calendar_col = st.columns" in app_text
    assert "guardrail_col, quote_col = st.columns" in app_text
    assert "compact=True" in app_text
    assert "Sin órdenes reales" in layout_text


def test_streamlit_header_exposes_separate_operational_freshness():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    layout_text = (ROOT / "ui" / "layout.py").read_text(encoding="utf-8")

    assert "_operational_freshness_items" in app_text
    assert "latest_scan_audited" in app_text
    assert "manual_review_latest" in app_text
    assert "macro_event_context" in app_text
    assert "freshness_items" in layout_text
    assert "Scan" in app_text
    assert "Manual review" in app_text
    assert "Macro" in app_text


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
    assert "macro_event_context" in SOURCE_SPECS
    assert "gui_visuals_audit" in SOURCE_SPECS
    assert "gui_release_audit" in SOURCE_SPECS
    assert "simple_candidate_posttest" in SOURCE_SPECS
    assert "gui_supervised_session" not in SOURCE_SPECS
    assert "gui_weekly_operational_review" not in SOURCE_SPECS
    assert "gui_evidence_collection_window" not in SOURCE_SPECS
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
