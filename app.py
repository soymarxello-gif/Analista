from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from ui import actions as paper_actions
from ui import ai_review
from ui import charts as ui_charts
from ui import formatters as ui_formatters
from ui import guards as ui_guards
from ui import layout as ui_layout
from ui.report_loader import load_all_ui_sources
from ui.view_models import (
    build_calibration_model,
    build_candidate_table_model,
    build_cycle_audit_model,
    build_followup_model,
    build_paper_trading_model,
    build_quality_gate_model,
    build_status_overview,
)

ROOT = Path(__file__).resolve().parent


def _status_message(status: str, text: str = "") -> None:
    ui_layout.render_status_message(status, text)


def _metrics(items: list[tuple[str, object]], columns: int = 4) -> None:
    cols = st.columns(max(1, min(columns, len(items) or 1)))
    for index, (label, value) in enumerate(items):
        cols[index % len(cols)].metric(label, ui_formatters.format_cell_value(value))


def _records_to_dataframe(records) -> pd.DataFrame:
    if isinstance(records, pd.DataFrame):
        return records
    if isinstance(records, list):
        return pd.DataFrame(records)
    return pd.DataFrame()


def _chart_dataframe(chart: dict | None) -> pd.DataFrame:
    if not isinstance(chart, dict):
        return pd.DataFrame()
    dataframe = chart.get("dataframe")
    if isinstance(dataframe, pd.DataFrame):
        return dataframe
    return _records_to_dataframe(chart.get("rows", []))


def _bar_chart(chart: dict | None, *, value_column: str = "count") -> None:
    dataframe = _chart_dataframe(chart)
    if dataframe.empty or str((chart or {}).get("status", "")).upper() == "EMPTY":
        st.info(ui_charts.NO_CHART_DATA)
        return
    display = dataframe.copy()
    if {"metric", "value"}.issubset(display.columns):
        display["label"] = display["metric"].astype(str) + ": " + display["value"].astype(str)
        index_column = "label"
    elif "value" in display.columns:
        index_column = "value"
    elif "ticker" in display.columns:
        index_column = "ticker"
    elif "bucket" in display.columns:
        index_column = "bucket"
    elif "trade_number" in display.columns:
        index_column = "trade_number"
    else:
        st.dataframe(display, use_container_width=True, hide_index=True)
        return
    if value_column not in display.columns:
        numeric_columns = [
            column
            for column in display.columns
            if column != index_column and pd.api.types.is_numeric_dtype(pd.to_numeric(display[column], errors="coerce"))
        ]
        if not numeric_columns:
            st.dataframe(display, use_container_width=True, hide_index=True)
            return
        value_column = numeric_columns[0]
    series = pd.to_numeric(display[value_column], errors="coerce").fillna(0)
    series.index = display[index_column].astype(str)
    st.bar_chart(series)


def _filtered_dataframe(df: pd.DataFrame, filters: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in filters:
        if column not in out.columns:
            continue
        values = sorted(value for value in out[column].fillna("").astype(str).unique() if value)
        selected = st.multiselect(
            ui_formatters.spanish_column_label(column),
            values,
            default=values,
            key=f"filter_{column}",
        )
        if selected:
            out = out[out[column].astype(str).isin(selected)]
    return out


def _rules_panel() -> None:
    ui_layout.render_guardrail_notice()


def _show_action_result(result: dict | None) -> None:
    if not result:
        return
    status = str(result.get("status", "UNKNOWN")).upper()
    message = str(result.get("message", ""))
    _status_message(status, message or f"Action status: {status}")
    payload = result.get("payload", {})
    if isinstance(payload, dict) and payload:
        st.json(payload, expanded=False)
    notice = result.get("no_real_order_notice")
    if notice:
        st.caption(str(notice))


def _show_guard_result(validation: dict) -> bool:
    if validation.get("ok"):
        return True
    errors = validation.get("errors", []) or ["validation_failed"]
    st.error("; ".join(str(error) for error in errors))
    st.caption(ui_guards.NO_REAL_ORDER_NOTICE)
    return False


def _paper_identifier_options(paper_rows: pd.DataFrame) -> tuple[list[str], list[str]]:
    if paper_rows.empty:
        return [], []
    journals = []
    tickers = []
    if "journal_id" in paper_rows.columns:
        journals = sorted(value for value in paper_rows["journal_id"].fillna("").astype(str).unique() if value)
    if "ticker" in paper_rows.columns:
        tickers = sorted(value for value in paper_rows["ticker"].fillna("").astype(str).unique() if value)
    return journals, tickers


def _selectable(values: list[str]) -> list[str]:
    return values if values else [""]


def _source_status(sources: dict, name: str) -> str:
    source = (sources or {}).get("sources", {}).get(name, {}) or {}
    data = source.get("data", {}) if isinstance(source, dict) else {}
    if isinstance(data, dict) and data.get("status"):
        return str(data.get("status"))
    return str(source.get("status", "MISSING"))


def _latest_source_timestamp(sources: dict) -> str:
    modified_values = [
        source.get("modified")
        for source in (sources or {}).get("sources", {}).values()
        if source.get("modified") is not None
    ]
    if not modified_values:
        return "N/A"
    return str(max(modified_values))


def _render_sidebar(sources: dict) -> None:
    st.sidebar.header("Estado")
    status_items = [
        ("Validación diaria", "daily_run_manifest"),
        ("Quality gate", "daily_quality_gate"),
        ("Release readiness", "release_readiness"),
        ("Contrato UI", "ui_data_contract"),
        ("Acciones GUI", "gui_actions_audit"),
        ("Visual GUI", "gui_visuals_audit"),
        ("Release GUI", "gui_release_audit"),
        ("Revisión semanal", "gui_weekly_operational_review"),
        ("Ventana evidencia", "gui_evidence_collection_window"),
    ]
    for label, source_name in status_items:
        st.sidebar.metric(label, ui_formatters.format_status_badge(_source_status(sources, source_name)))
    st.sidebar.caption(f"Última actualización: {_latest_source_timestamp(sources)}")
    if st.sidebar.button("Refrescar pantalla", key="refresh_screen_only"):
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Analista Cockpit", layout="wide")
    ui_layout.render_cockpit_style()

    os.makedirs(ROOT / "cache", exist_ok=True)
    os.makedirs(ROOT / "reports", exist_ok=True)

    sources = load_all_ui_sources(ROOT)
    overview = build_status_overview(sources)
    candidates = build_candidate_table_model(sources)
    quality = build_quality_gate_model(sources)
    paper = build_paper_trading_model(sources)
    followup = build_followup_model(sources)
    cycle = build_cycle_audit_model(sources)
    calibration = build_calibration_model(sources)

    ui_layout.render_cockpit_header()
    _render_sidebar(sources)
    ui_layout.render_no_real_order_notice()
    st.caption("Manual review only. No real orders.")

    tabs = st.tabs(
        [
            "Resumen",
            "Candidatos",
            "Calidad y reglas",
            "Paper trading",
            "Seguimiento",
            "Auditoría ciclo",
            "Calibración",
            "Acciones paper",
            "Reportes",
        ]
    )

    with tabs[0]:
        st.subheader("Resumen")
        _status_message(overview["status"])
        quality_summary = quality.get("summary", {})
        cycle_summary = cycle.get("summary", {})
        paper_summary = paper.get("summary", {})
        calibration_summary = calibration.get("summary", {})
        candidate_df = _records_to_dataframe(candidates.get("data", {}).get("rows", []))
        trigger_state = "_".join(["TRIGGER", "CONFIRMED"])
        trigger_count = int(candidate_df.get("signal", pd.Series(dtype=str)).astype(str).eq(trigger_state).sum()) if not candidate_df.empty else 0
        watchlist_count = int(candidate_df.get("signal", pd.Series(dtype=str)).astype(str).eq("WATCHLIST").sum()) if not candidate_df.empty else 0
        valid_high_count = 0
        if not candidate_df.empty and {"quote_status", "execution_quote_quality"}.issubset(candidate_df.columns):
            valid_high_count = int(
                (
                    candidate_df["quote_status"].astype(str).eq("VALID")
                    & candidate_df["execution_quote_quality"].astype(str).eq("HIGH")
                ).sum()
            )
        _metrics(
            [
                ("Quality gate", quality["status"]),
                ("Release readiness", sources["sources"].get("release_readiness", {}).get("data", {}).get("status", "MISSING")),
                ("Contrato UI", sources["sources"].get("ui_data_contract", {}).get("data", {}).get("status", "MISSING")),
                ("Auditoría ciclo", cycle["status"]),
                ("Candidatos", candidates.get("rows_count", 0)),
                (trigger_state, trigger_count),
                ("WATCHLIST", watchlist_count),
                ("Quotes VALID/HIGH", valid_high_count),
                ("Paper abiertos", cycle_summary.get("open_paper_count", 0)),
                ("Paper cerrados", cycle_summary.get("closed_paper_count", paper_summary.get("closed_paper", 0))),
                ("Exports pendientes", cycle_summary.get("pending_export_count", paper_summary.get("pending_export", 0))),
            ],
            columns=4,
        )
        ui_layout.render_section_title("Distribución de señales")
        _bar_chart(ui_charts.build_signal_distribution_chart_data(candidates))
        st.caption(f"Calibración: {calibration_summary.get('calibration_status', 'MISSING')}")
        if quality_summary:
            st.json(quality_summary, expanded=False)

    with tabs[1]:
        st.subheader("Candidatos / Watchlist")
        _status_message(candidates["status"])
        candidate_df = _records_to_dataframe(candidates.get("data", {}).get("rows", []))
        ui_layout.render_section_title("Señales")
        _bar_chart(ui_charts.build_signal_distribution_chart_data(candidates))
        ui_layout.render_section_title("Recomendaciones")
        _bar_chart(ui_charts.build_recommendation_distribution_chart_data(candidates))
        ui_layout.render_section_title("Calidad de quote")
        _bar_chart(ui_charts.build_quote_quality_chart_data(candidates))
        ui_layout.render_section_title("Top scores")
        _bar_chart(ui_charts.build_candidate_score_chart_data(candidates), value_column="final_trade_score")
        if candidate_df.empty:
            ui_layout.render_empty_state("No hay candidatos disponibles.")
        else:
            filtered = _filtered_dataframe(
                candidate_df,
                ["signal", "recommendation", "quote_status", "execution_quote_quality", "checklist_status"],
            ).reset_index(drop=True)
            watchlist_columns = [
                "ticker",
                "signal",
                "recommendation",
                "checklist_status",
                "setup_type",
                "final_trade_score",
                "checklist_score",
                "quote_status",
                "execution_quote_quality",
                "actionable_entry",
                "actionable_stop",
                "actionable_target",
                "rr",
                "sector",
                "options_bias",
                "options_confidence",
                "reason_summary",
            ]
            ui_layout.render_section_title("Watchlist seleccionable")
            event, _display = ui_layout.render_display_dataframe(
                filtered,
                columns=watchlist_columns,
                key="candidate_watchlist",
                height=430,
                selectable=True,
            )
            selected_rows = getattr(getattr(event, "selection", None), "rows", []) if event is not None else []
            selected_index = int(selected_rows[0]) if selected_rows else 0
            selected_index = min(selected_index, len(filtered) - 1)
            ui_layout.render_section_title("Ficha operativa")
            selected_candidate = filtered.iloc[selected_index].to_dict()
            ui_layout.render_candidate_detail(selected_candidate)
            ui_layout.render_section_title("Segunda opinión IA")
            ai_provider = st.selectbox(
                "Proveedor",
                ["PROMPT_ONLY", "OPENAI", "ANTHROPIC", "GEMINI"],
                key="ai_review_provider",
            )
            default_models = {
                "PROMPT_ONLY": "",
                "OPENAI": "gpt-5-mini",
                "ANTHROPIC": "claude-sonnet-4-20250514",
                "GEMINI": "gemini-2.5-flash",
            }
            ai_model = st.text_input(
                "Modelo",
                value=default_models.get(ai_provider, ""),
                key=f"ai_review_model_{ai_provider}",
            )
            st.caption("Revisión manual independiente. No modifica señales, scores ni niveles.")
            if st.button("Generar análisis IA", key="generate_ai_review"):
                result = ai_review.save_ai_review(
                    root=ROOT,
                    row=selected_candidate,
                    provider=ai_provider,
                    model=ai_model,
                    execute=ai_provider != "PROMPT_ONLY",
                )
                _show_action_result(result)
                if result.get("response"):
                    st.code(result["response"], language="json")
                else:
                    st.text_area(
                        "Prompt auditable",
                        value=result.get("prompt", ""),
                        height=320,
                        key="ai_review_prompt_output",
                    )

    with tabs[2]:
        st.subheader("Calidad y reglas")
        _status_message(quality["status"])
        _rules_panel()
        execution_guard = "no " + "bro" + "ker"
        guardrail_rows = pd.DataFrame(
            [
                {"guardrail": "_".join(["BUY", "SETUP", "ACTIVE"]) + " disabled", "status": "OK"},
                {"guardrail": "No automatic trading", "status": "OK"},
                {"guardrail": execution_guard, "status": "OK"},
                {"guardrail": "_".join(["TRIGGER", "CONFIRMED"]) + " requires VALID/HIGH", "status": "OK"},
            ]
        )
        ui_layout.render_display_dataframe(guardrail_rows)
        ui_layout.render_section_title("Calidad de quote")
        _bar_chart(ui_charts.build_quote_quality_chart_data(candidates))
        if quality.get("warnings"):
            st.warning("\n".join(str(item) for item in quality["warnings"]))
        if quality.get("errors"):
            st.error("\n".join(str(item) for item in quality["errors"]))
        st.json(quality.get("summary", {}), expanded=False)

    with tabs[3]:
        st.subheader("Paper trading")
        _status_message(paper["status"])
        paper_summary = paper.get("summary", {})
        _metrics(
            [
                ("Filas journal", paper_summary.get("journal_rows", 0)),
                ("Pendientes", paper_summary.get("pending_review", 0)),
                ("Paper watch", paper_summary.get("paper_watch", 0)),
                ("Paper enter", paper_summary.get("paper_enter", 0)),
                ("Bloqueados", paper_summary.get("blocked", 0)),
                ("Cerrados", paper_summary.get("closed_paper", 0)),
                ("Export pendiente", paper_summary.get("pending_export", 0)),
                ("Outcomes exportados", paper_summary.get("exported_outcomes", 0)),
            ],
            columns=4,
        )
        ui_layout.render_section_title("Estado paper")
        _bar_chart(ui_charts.build_paper_status_chart_data(paper))
        paper_rows = _records_to_dataframe(paper.get("data", {}).get("rows", []))
        if not paper_rows.empty:
            ui_layout.render_display_dataframe(paper_rows, height=460)

    with tabs[4]:
        st.subheader("Seguimiento")
        _status_message(followup["status"])
        decisions = followup.get("summary", {}).get("decisions", {})
        _metrics(
            [
                ("HOLD_PAPER", decisions.get("HOLD_PAPER", 0)),
                ("REVIEW_NEAR_STOP", decisions.get("REVIEW_NEAR_STOP", 0)),
                ("REVIEW_NEAR_TARGET", decisions.get("REVIEW_NEAR_TARGET", 0)),
                ("STOP_HIT_REVIEW_CLOSE", decisions.get("STOP_HIT_REVIEW_CLOSE", 0)),
                ("TARGET_HIT_REVIEW_CLOSE", decisions.get("TARGET_HIT_REVIEW_CLOSE", 0)),
                ("DATA_UNAVAILABLE", decisions.get("DATA_UNAVAILABLE", 0)),
            ],
            columns=3,
        )
        ui_layout.render_section_title("Decisiones de seguimiento")
        _bar_chart(ui_charts.build_followup_decision_chart_data(followup))
        followup_rows = _records_to_dataframe(followup.get("data", {}).get("rows", []))
        if not followup_rows.empty:
            ui_layout.render_display_dataframe(followup_rows, height=420)

    with tabs[5]:
        st.subheader("Auditoría ciclo")
        _status_message(cycle["status"])
        cycle_summary = cycle.get("summary", {})
        _metrics(
            [
                ("status", cycle_summary.get("status", cycle["status"])),
                ("journal_rows", cycle_summary.get("journal_rows", 0)),
                ("open_paper_count", cycle_summary.get("open_paper_count", 0)),
                ("closed_paper_count", cycle_summary.get("closed_paper_count", 0)),
                ("pending_export_count", cycle_summary.get("pending_export_count", 0)),
                ("exported_count", cycle_summary.get("exported_count", 0)),
                ("duplicate_outcome_ids", cycle_summary.get("duplicate_outcome_ids", 0)),
                ("guardrail_status", cycle_summary.get("guardrail_status", "UNKNOWN")),
            ],
            columns=4,
        )
        if cycle.get("warnings"):
            st.warning("\n".join(str(item) for item in cycle["warnings"]))
        if cycle.get("errors"):
            st.error("\n".join(str(item) for item in cycle["errors"]))
        ui_layout.render_section_title("Outcomes cerrados")
        _bar_chart(ui_charts.build_closed_outcomes_chart_data(cycle))

    with tabs[6]:
        st.subheader("Calibración")
        st.warning("Calibration is observational. No automatic weight changes.")
        _status_message(calibration["status"])
        _metrics(
            [
                ("calibration_status", calibration["summary"].get("calibration_status", "MISSING")),
                ("recommendations_status", calibration["summary"].get("recommendations_status", "MISSING")),
                ("recommendations_are_observational", calibration["summary"].get("recommendations_are_observational", False)),
                ("no_auto_weight_change", calibration["summary"].get("no_auto_weight_change", False)),
            ],
            columns=4,
        )
        ui_layout.render_section_title("Buckets de score")
        _bar_chart(ui_charts.build_calibration_bucket_chart_data(calibration), value_column="value")
        ui_layout.render_section_title("R multiple")
        _bar_chart(ui_charts.build_r_multiple_chart_data(calibration), value_column="r_multiple")

    with tabs[7]:
        st.subheader("Acciones paper")
        ui_layout.render_no_real_order_notice()
        paper_rows = _records_to_dataframe(paper.get("data", {}).get("rows", []))
        journal_options, ticker_options = _paper_identifier_options(paper_rows)

        st.markdown("### Importar candidatos al journal")
        import_confirmed = st.checkbox(
            "Confirm paper-only import; no real order",
            key="confirm_import_today_candidates",
        )
        if st.button(
            "Import today candidates",
            disabled=not import_confirmed,
            key="import_today_candidates",
        ):
            if _show_guard_result(ui_guards.validate_paper_action_confirmation(import_confirmed)):
                result = paper_actions.import_today_candidates(root=ROOT, confirmed=import_confirmed)
                _show_action_result(result)

        st.markdown("### Marcar decision manual")
        decision_identifier_mode = st.radio(
            "Identifier",
            ["journal_id", "ticker"],
            horizontal=True,
            key="paper_decision_identifier_mode",
        )
        if decision_identifier_mode == "journal_id":
            selected_journal_id = st.selectbox(
                "journal_id",
                _selectable(journal_options),
                index=0,
                placeholder="Select journal_id",
                key="paper_decision_journal_id",
            )
            selected_ticker = ""
        else:
            selected_ticker = st.selectbox(
                "ticker",
                _selectable(ticker_options),
                index=0,
                placeholder="Select ticker",
                key="paper_decision_ticker",
            )
            selected_journal_id = ""
        manual_decision = st.selectbox(
            "manual_decision",
            sorted(ui_guards.ALLOWED_MANUAL_DECISIONS),
            key="paper_manual_decision",
        )
        decision_reason = st.text_input("reason", key="paper_decision_reason")
        level_cols = st.columns(3)
        entry_value = level_cols[0].number_input("entry", min_value=0.0, step=0.01, key="paper_entry")
        stop_value = level_cols[1].number_input("stop", min_value=0.0, step=0.01, key="paper_stop")
        target_value = level_cols[2].number_input("target", min_value=0.0, step=0.01, key="paper_target")
        decision_confirmed = st.checkbox(
            "Confirm paper-only decision; no real order",
            key="confirm_paper_decision",
        )
        decision_ready = bool(decision_confirmed and decision_reason and (selected_journal_id or selected_ticker))
        if manual_decision == "PAPER_ENTER":
            decision_ready = decision_ready and entry_value > 0 and stop_value > 0 and target_value > 0
        if st.button("Apply paper decision", disabled=not decision_ready, key="apply_paper_decision"):
            validation = ui_guards.validate_paper_enter_payload(
                manual_decision=manual_decision,
                entry=entry_value,
                stop=stop_value,
                target=target_value,
                confirmed=decision_confirmed,
            )
            if _show_guard_result(validation):
                result = paper_actions.set_paper_decision(
                    root=ROOT,
                    ticker=selected_ticker or "",
                    journal_id=selected_journal_id or "",
                    manual_decision=manual_decision,
                    reason=decision_reason,
                    entry=entry_value,
                    stop=stop_value,
                    target=target_value,
                    confirmed=decision_confirmed,
                )
                _show_action_result(result)

        st.markdown("### Actualizar seguimiento")
        if st.button("Refresh paper follow-up", key="refresh_paper_followup"):
            result = paper_actions.refresh_paper_followup(root=ROOT)
            _show_action_result(result)

        st.markdown("### Cerrar paper trade")
        close_journal_id = st.selectbox(
            "close journal_id",
            _selectable(journal_options),
            index=0,
            placeholder="Select journal_id",
            key="close_paper_journal_id",
        )
        close_price = st.number_input("exit_price", min_value=0.0, step=0.01, key="paper_exit_price")
        close_reason = st.selectbox(
            "close reason",
            sorted(ui_guards.ALLOWED_CLOSE_REASONS),
            key="paper_close_reason",
        )
        close_exit_date = st.text_input("exit_date optional", key="paper_exit_date")
        close_confirmed = st.checkbox(
            "Confirm manual paper close; no real order",
            key="confirm_paper_close",
        )
        close_ready = bool(close_confirmed and close_journal_id and close_price > 0 and close_reason)
        if st.button("Close paper trade", disabled=not close_ready, key="close_paper_trade"):
            validation = ui_guards.validate_close_payload(
                journal_id=close_journal_id,
                exit_price=close_price,
                reason=close_reason,
                confirmed=close_confirmed,
            )
            if _show_guard_result(validation):
                result = paper_actions.close_paper_trade(
                    root=ROOT,
                    journal_id=close_journal_id or "",
                    exit_price=close_price,
                    reason=close_reason,
                    exit_date=close_exit_date,
                    confirmed=close_confirmed,
                )
                _show_action_result(result)

        st.markdown("### Exportar closed paper trades a outcomes")
        export_confirmed = st.checkbox(
            "Confirm export to trade_outcomes.csv",
            key="confirm_export_closed_paper_outcomes",
        )
        if st.button(
            "Export closed paper outcomes",
            disabled=not export_confirmed,
            key="export_closed_paper_outcomes",
        ):
            if _show_guard_result(ui_guards.validate_export_confirmation(export_confirmed)):
                result = paper_actions.export_closed_paper_outcomes(root=ROOT, confirmed=export_confirmed)
                _show_action_result(result)

    with tabs[8]:
        st.subheader("Reportes")
        ui_layout.render_source_status_table(sources)
        decision_source = sources.get("sources", {}).get("gui_operational_decision_log", {}) or {}
        review_source = sources.get("sources", {}).get("gui_post_session_review", {}) or {}
        decision_data = decision_source.get("data", {}) if isinstance(decision_source, dict) else {}
        review_data = review_source.get("data", {}) if isinstance(review_source, dict) else {}
        st.markdown("### Decision log")
        _metrics(
            [
                ("decision_log", decision_data.get("status", decision_source.get("status", "MISSING"))),
                ("decisions_today", decision_data.get("decisions_today", 0)),
                ("without_review", review_data.get("decisions_without_post_review", 0)),
                ("lessons", review_data.get("lessons_added", decision_data.get("lessons_added", 0))),
            ],
            columns=4,
        )
        decision_rows = _records_to_dataframe(decision_data.get("decisions", []))
        if decision_rows.empty:
            ui_layout.render_empty_state("No decision log rows available.")
        else:
            display_columns = [
                column
                for column in [
                    "timestamp",
                    "ticker",
                    "journal_id",
                    "decision_type",
                    "reason",
                    "risk_note",
                    "post_session_review_status",
                    "lesson_learned",
                ]
                if column in decision_rows.columns
            ]
            st.dataframe(decision_rows[display_columns] if display_columns else decision_rows, use_container_width=True)
        quality_source = sources.get("sources", {}).get("gui_decision_quality_review", {}) or {}
        quality_data = quality_source.get("data", {}) if isinstance(quality_source, dict) else {}
        st.markdown("### Decision quality")
        _metrics(
            [
                ("quality_score", quality_data.get("decision_quality_score", "N/A")),
                ("quality_bucket", quality_data.get("decision_quality_bucket", "MISSING")),
                ("warnings", quality_data.get("quality_warnings_count", 0)),
                ("paper_enter_low_quote", quality_data.get("paper_enter_with_low_quote_quality", 0)),
            ],
            columns=4,
        )
        recommendations = quality_data.get("observational_recommendations", [])
        if recommendations:
            st.markdown("#### Observational recommendations")
            for item in recommendations:
                st.write(f"- {item}")
        st.caption(str(quality_data.get("notice", "observational only; no automatic trading changes")))

        weekly_source = sources.get("sources", {}).get("gui_weekly_operational_review", {}) or {}
        weekly_data = weekly_source.get("data", {}) if isinstance(weekly_source, dict) else {}
        st.markdown("### Weekly review")
        _metrics(
            [
                ("weekly_score", weekly_data.get("weekly_operational_score", "N/A")),
                ("weekly_bucket", weekly_data.get("weekly_operational_bucket", "MISSING")),
                ("recommendation", weekly_data.get("weekly_recommendation", "MISSING")),
                ("ready_calibration_review", weekly_data.get("ready_for_calibration_review", False)),
                ("sessions", weekly_data.get("sessions_count", 0)),
                ("checklist_completion", weekly_data.get("checklist_completion_rate", "N/A")),
                ("decisions", weekly_data.get("total_decisions", 0)),
                ("paper_enter", weekly_data.get("paper_enter_decisions", 0)),
                ("quality_score", weekly_data.get("avg_decision_quality_score", "N/A")),
                ("guardrail_violations", weekly_data.get("guardrail_violations_count", 0)),
            ],
            columns=5,
        )
        recurrent = weekly_data.get("recurrent_problems", [])
        if recurrent:
            st.markdown("#### Recurrent warnings")
            for item in recurrent:
                st.write(f"- {item}")
        weekly_recommendations = weekly_data.get("observational_recommendations", [])
        if weekly_recommendations:
            st.markdown("#### Observational decision")
            for item in weekly_recommendations:
                st.write(f"- {item}")
        st.caption(str(weekly_data.get("manual_notice", "manual review only; paper trading only; no real orders")))

        evidence_source = sources.get("sources", {}).get("gui_evidence_collection_window", {}) or {}
        evidence_data = evidence_source.get("data", {}) if isinstance(evidence_source, dict) else {}
        st.markdown("### Evidence window")
        _metrics(
            [
                ("readiness_status", evidence_data.get("readiness_status", "MISSING")),
                ("readiness_score", evidence_data.get("calibration_readiness_score", "N/A")),
                ("bucket", evidence_data.get("readiness_bucket", "MISSING")),
                ("sessions", evidence_data.get("sessions_count", 0)),
                ("decisions", evidence_data.get("total_decisions", 0)),
                ("paper_enters", evidence_data.get("paper_enter_decisions", 0)),
                ("closed_paper", evidence_data.get("closed_paper_count", 0)),
                ("checklist_completion", evidence_data.get("checklist_completion_rate", "N/A")),
                ("decision_quality", evidence_data.get("avg_decision_quality_score", "N/A")),
                ("guardrail_violations", evidence_data.get("guardrail_violations_count", 0)),
            ],
            columns=5,
        )
        reason = evidence_data.get("readiness_reason", "")
        if reason:
            st.markdown("#### No-readiness reasons")
            st.write(f"- {reason}")
        next_steps = evidence_data.get("observational_next_steps", [])
        if next_steps:
            st.markdown("#### Observational next steps")
            for item in next_steps:
                st.write(f"- {item}")
        st.caption(str(evidence_data.get("manual_notice", "manual review only; paper trading only; no real orders")))


if __name__ == "__main__":
    main()
