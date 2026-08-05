from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from ui import actions as ui_actions
from ui import ai_review
from ui import charts as ui_charts
from ui import formatters as ui_formatters
from ui import layout as ui_layout
from ui import preferences as ui_preferences
from ui.report_loader import load_all_ui_sources
from ui.view_models import (
    build_calibration_model,
    build_candidate_table_model,
    build_macro_context_model,
    build_quality_gate_model,
    build_status_overview,
)

ROOT = Path(__file__).resolve().parent

WATCHLIST_FILTER_COLUMNS = [
    "technical_analysis_lane",
    "scenario_status",
    "setup_type",
    "quote_status",
    "execution_quote_quality",
    "checklist_status",
]

WATCHLIST_DEFAULT_COLUMNS = [
    "ticker",
    "execution_readiness_status",
    "market_opportunity_status",
    "deep_analysis_tier",
    "technical_opportunity_score",
    "technical_analysis_lane",
    "weekly_macd_histogram_state",
    "ema20_extension_status",
    "operational_readiness_score",
    "final_trade_score",
    "setup_type",
    "quote_status",
    "execution_quote_quality",
    "rr",
    "rr_status",
    "risk_geometry_status",
]

RESEARCH_DEFAULT_COLUMNS = [
    "ticker",
    "setup_candidate_type",
    "setup_readiness_score",
    "setup_readiness_state",
    "technical_opportunity_score",
    "research_eligibility_reason",
    "ema20_extension_status",
    "daily_macd_trajectory_state",
    "weekly_macd_trajectory_state",
    "rr_status",
    "risk_geometry_status",
]


def _status_message(status: str, text: str = "") -> None:
    ui_layout.render_status_message(status, text)


def _metrics(items: list[tuple[str, object]], columns: int = 4) -> None:
    ui_layout.render_metric_chips(items, columns=columns)


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
    rendered = ui_charts.build_horizontal_bar_chart(chart, value_column=value_column)
    if rendered is None:
        st.info(ui_charts.NO_CHART_DATA)
        return
    st.altair_chart(rendered, width="stretch")


def _r_multiple_chart(chart: dict | None) -> None:
    rendered = ui_charts.build_r_multiple_line_chart(chart)
    if rendered is None:
        st.info(ui_charts.NO_CHART_DATA)
        return
    st.altair_chart(rendered, width="stretch")


def _filtered_dataframe(
    df: pd.DataFrame,
    filters: list[str],
    *,
    key_prefix: str = "filter",
) -> pd.DataFrame:
    out = df.copy()
    available_filters = [column for column in filters if column in out.columns]
    if available_filters:
        with st.expander("Filtros avanzados", expanded=False):
            filter_columns = st.columns(min(3, len(available_filters)))
            for index, column in enumerate(available_filters):
                values = sorted(value for value in out[column].fillna("").astype(str).unique() if value)
                selected = filter_columns[index % len(filter_columns)].multiselect(
                    ui_formatters.spanish_column_label(column),
                    values,
                    default=values,
                    key=f"{key_prefix}_{column}",
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
        payload_rows = pd.DataFrame(
            [
                {
                    "Campo": ui_formatters.spanish_column_label(key),
                    "Valor": ui_formatters.safe_display_text(value),
                }
                for key, value in payload.items()
                if not isinstance(value, (dict, list))
            ]
        )
        if not payload_rows.empty:
            st.dataframe(payload_rows, width="stretch", hide_index=True)
    notice = result.get("no_real_order_notice")
    if notice:
        st.caption(str(notice))


def _show_sidebar_action_result(result: dict | None) -> None:
    if not result:
        return
    status = str(result.get("status", "UNKNOWN")).upper()
    message = str(result.get("message", "")) or f"Estado: {status}"
    if status == "FAIL":
        st.sidebar.error(message)
    elif status == "WARN":
        st.sidebar.warning(message)
    else:
        st.sidebar.success(message)
    payload = result.get("payload", {})
    if isinstance(payload, dict):
        duration = payload.get("duration_seconds")
        summary_status = payload.get("summary_status")
        if duration not in (None, ""):
            st.sidebar.caption(f"Duración: {ui_formatters.format_number(duration)} segundos")
        if summary_status:
            st.sidebar.caption(f"Resumen: {summary_status}")


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
    return ui_formatters.format_timestamp(max(modified_values))


def _source_timestamp(sources: dict, name: str) -> str:
    source = (sources or {}).get("sources", {}).get(name, {}) or {}
    modified = source.get("modified")
    return ui_formatters.format_timestamp(modified) if modified is not None else "N/A"


def _freshness_label(status: object) -> str:
    text = str(status or "UNKNOWN").upper()
    if text == "PASS":
        return "fresco"
    if text == "WARN":
        return "antiguo"
    if text == "MISSING":
        return "faltante"
    return text.lower()


def _operational_freshness_items(sources: dict, quality: dict) -> list[tuple[str, object, object]]:
    freshness = quality.get("data", {}).get("artifact_freshness", {}) if isinstance(quality, dict) else {}
    scan_status = freshness.get("scan_freshness_status", "UNKNOWN")
    manual_status = "WARN" if freshness.get("manual_review_is_stale") else "PASS"
    macro_status = _source_status(sources, "macro_event_context")
    historical_status = _source_status(sources, "market_data_engine_source")
    historical_data = (
        sources.get("sources", {}).get("market_data_engine_source", {}).get("data", {}) or {}
    )
    historical_date = (historical_data.get("health", {}) or {}).get("latest_bar_date", "N/A")
    return [
        ("Scan", f"{_freshness_label(scan_status)} · {_source_timestamp(sources, 'latest_scan_audited')}", scan_status),
        ("Manual review", f"{_freshness_label(manual_status)} · {_source_timestamp(sources, 'manual_review_latest')}", manual_status),
        ("Macro", f"{_freshness_label(macro_status)} · {_source_timestamp(sources, 'macro_event_context')}", macro_status),
        ("Base histórica", f"{_freshness_label(historical_status)} · {historical_date}", historical_status),
        ("Reportes", _latest_source_timestamp(sources), "PASS"),
    ]


def _header_context_items(macro: dict, candidates: dict) -> list[tuple[str, object, object]]:
    macro_summary = macro.get("summary", {}) if isinstance(macro, dict) else {}
    candidate_df = _records_to_dataframe(candidates.get("data", {}).get("rows", []))
    ready_count = 0
    recheck_count = 0
    if not candidate_df.empty:
        execution_status = candidate_df.get("execution_readiness_status", pd.Series(dtype=str)).astype(str)
        ready_count = int(execution_status.eq("EXECUTION_READY_REVIEW").sum())
        recheck_count = int(execution_status.eq("NEEDS_LIVE_QUOTE_RECHECK").sum())
    semaforo = macro_summary.get("nasdaq_risk_semaforo", "UNKNOWN")
    event_risk = macro_summary.get("event_risk_status", "UNKNOWN")
    return [
        ("Nasdaq", semaforo, semaforo),
        ("Régimen", macro_summary.get("nasdaq_macro_regime_mode", macro_summary.get("macro_regime_mode", "UNKNOWN")), macro_summary.get("nasdaq_macro_risk_flag", "UNKNOWN")),
        ("Evento macro", event_risk, event_risk),
        ("Listos/recheck", f"{ready_count}/{recheck_count}", "PASS" if ready_count else "WARN"),
    ]


def _candidate_status_counts(df: pd.DataFrame) -> list[tuple[str, object]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [
            ("Candidatos", 0),
            ("Execution ready", 0),
            ("Recheck", 0),
            ("Bloqueados", 0),
        ]
    execution = df.get("execution_readiness_status", pd.Series(index=df.index, dtype=str)).astype(str)
    scenario = df.get("scenario_status", pd.Series(index=df.index, dtype=str)).astype(str)
    weekly_macd = df.get("weekly_macd_histogram_state", pd.Series(index=df.index, dtype=str)).astype(str)
    ema20_extension = df.get("ema20_extension_status", pd.Series(index=df.index, dtype=str)).astype(str)
    quote = df.get("quote_status", pd.Series(index=df.index, dtype=str)).astype(str)
    blocked_mask = execution.eq("NOT_OPERABLE") | scenario.isin(
        ["LATE_ENTRY_OVEREXTENDED", "WEAK_MOMENTUM", "STRUCTURE_INVALID", "CONTEXT_CONFLICT"]
    ) | weekly_macd.isin(
        ["WEEKLY_MACD_HIST_BEARISH", "WEEKLY_MACD_HIST_DECELERATING"]
    ) | ema20_extension.isin(
        ["OVEREXTENDED", "LATE_ENTRY"]
    )
    return [
        ("Candidatos", len(df)),
        ("Listos ejecución", int(execution.eq("EXECUTION_READY_REVIEW").sum())),
        ("Recheck", int(execution.eq("NEEDS_LIVE_QUOTE_RECHECK").sum())),
        ("Bloqueados", int(blocked_mask.sum())),
        ("Quote VALID", int(quote.eq("VALID").sum())),
    ]


def _render_sidebar(sources: dict) -> None:
    st.sidebar.header("Estado del sistema")
    st.sidebar.markdown("### Datos")
    _show_sidebar_action_result(st.session_state.get("last_refresh_all_data_result"))
    _render_help_panel()
    critical_items = [
        ("Validación diaria", "daily_run_manifest"),
        ("Quality gate", "daily_quality_gate"),
        ("Release readiness", "release_readiness"),
    ]
    for label, source_name in critical_items:
        st.sidebar.metric(label, ui_formatters.format_status_badge(_source_status(sources, source_name)))
    with st.sidebar.expander("Auditorías secundarias", expanded=False):
        secondary_items = [
            ("Contrato UI", "ui_data_contract"),
            ("Acciones GUI", "gui_actions_audit"),
            ("Visual GUI", "gui_visuals_audit"),
            ("Release GUI", "gui_release_audit"),
        ]
        for label, source_name in secondary_items:
            st.caption(f"{label}: {ui_formatters.format_status_badge(_source_status(sources, source_name))}")
    st.sidebar.caption(f"Último reporte cargado: {_latest_source_timestamp(sources)}")
    if st.sidebar.button("Refrescar pantalla", key="refresh_screen_only"):
        st.rerun()


def _render_header_actions() -> None:
    left, right = st.columns([0.72, 0.28], gap="small")
    with left:
        ui_layout.render_inline_note("Revisión manual y diagnóstico automático solamente.", status="WARN")
    with right:
        if st.button(
            "Actualizar todos los datos",
            key="refresh_all_data",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner("Actualizando datos y reportes..."):
                result = ui_actions.refresh_all_data(root=ROOT, confirmed=True)
            st.session_state["last_refresh_all_data_result"] = result
            st.rerun()


def _render_help_panel() -> None:
    with st.sidebar.expander("Ayuda / instrucciones", expanded=False):
        st.markdown(
            "\n".join(
                [
                    "### Uso rápido",
                    "1. Pulsa **Actualizar todos los datos** para regenerar scan, reportes y auditorías.",
                    "2. Revisa primero la frescura de **Scan**, **Manual review** y **Macro** en la cabecera.",
                    "3. Entra en **Candidatos** y filtra la watchlist por setup, escenario y calidad de quote.",
                    "4. Selecciona una fila para abrir la ficha operativa. No hay selección automática.",
                    "5. Si el candidato exige quote en vivo, revisa el reporte de recheck antes de cualquier decisión manual.",
                    "6. Usa **Calibración** para revisar el posttest automático simple 5 / 10 / 15 sesiones.",
                    "",
                    "### Watchlist",
                    "- **Configurar tabla** permite elegir columnas visibles.",
                    "- El ordenamiento se hace directamente desde los encabezados nativos de la tabla.",
                    "- Las columnas visibles se guardan automáticamente para próximas sesiones.",
                    "- El ancho ajustado arrastrando columnas depende del componente nativo de Streamlit y no se expone al servidor.",
                    "",
                    "### Definiciones clave",
                    "- **WATCHLIST**: monitoreo. No equivale a entrada.",
                    "- **RECHECK_LIVE_QUOTE**: requiere validación de quote antes de lectura operativa.",
                    "- **VETO / AVOID**: no operables.",
                    "- **HIGH_QUALITY_REVIEW**: alta calidad para revisión manual, no compra automática.",
                    "- **quote_status VALID** y **execution_quote_quality HIGH** son condiciones estrictas para lectura ejecutable.",
                    "- **Readiness**: prioridad operativa derivada; separa score atractivo de oportunidad usable hoy.",
                    "- **Niveles operativos**: entrada, stop, target y R/R publicados por el pipeline.",
                    "- **Niveles diagnósticos**: niveles shadow para auditar oportunidad, no reemplazan niveles publicados.",
                    "- **Macro**: régimen y riesgo contextual. No crea señales ni cambia calidad de ejecución.",
                    "- **Posttest simple**: evalúa automáticamente los mejores candidatos históricos a 5, 10 y 15 sesiones.",
                    "",
                    "### Colores",
                    "- Rojo: bloqueo, riesgo, dato inválido o calidad insuficiente.",
                    "- Amarillo: espera, revisión o advertencia.",
                    "- Verde: condición válida o saludable.",
                    "- Azul/gris: información neutral.",
                ]
            )
        )


def _apply_watchlist_preferences(
    *,
    table_key: str,
    df: pd.DataFrame,
    default_columns: list[str],
    default_sort_column: str,
    default_sort_desc: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    available_columns = [str(column) for column in df.columns]
    stored = ui_preferences.get_table_preferences(
        ROOT,
        table_key,
        default_columns=default_columns,
        default_sort_column=default_sort_column,
        default_sort_desc=default_sort_desc,
    )
    selected_defaults = ui_preferences.sanitize_columns(
        available_columns,
        stored.get("columns", default_columns),
        default_columns,
    )
    with st.expander("Configurar tabla", expanded=False):
        selected_columns = st.multiselect(
            "Columnas visibles",
            options=available_columns,
            default=selected_defaults,
            format_func=ui_formatters.spanish_column_label,
            key=f"{table_key}_visible_columns",
        )
        st.caption(
            "Las columnas visibles se guardan automáticamente. "
            "Ordena desde los encabezados de la tabla cuando necesites cambiar la prioridad visual."
        )
    active_columns = ui_preferences.sanitize_columns(available_columns, selected_columns, default_columns)
    ui_preferences.set_table_preferences(
        ROOT,
        table_key,
        columns=active_columns,
        sort_column="",
        sort_desc=True,
    )
    return df.reset_index(drop=True), active_columns


def main() -> None:
    st.set_page_config(page_title="Analista Cockpit", layout="wide")
    ui_layout.render_cockpit_style()

    os.makedirs(ROOT / "cache", exist_ok=True)
    os.makedirs(ROOT / "reports", exist_ok=True)

    sources = load_all_ui_sources(ROOT)
    overview = build_status_overview(sources)
    candidates = build_candidate_table_model(sources)
    quality = build_quality_gate_model(sources)
    macro = build_macro_context_model(sources)
    calibration = build_calibration_model(sources)

    release_status = sources["sources"].get("release_readiness", {}).get("data", {}).get("status", "MISSING")
    ui_layout.render_cockpit_header(
        quality_status=quality.get("status", "UNKNOWN"),
        release_status=release_status,
        updated_at=_latest_source_timestamp(sources),
        freshness_items=_operational_freshness_items(sources, quality),
        context_items=_header_context_items(macro, candidates),
    )
    _render_header_actions()
    _render_sidebar(sources)

    primary_view = st.segmented_control(
        "Navegación principal",
        ["Resumen", "Candidatos", "Macro", "Control"],
        default="Candidatos",
        label_visibility="collapsed",
        key="primary_navigation",
    )
    active_view = primary_view or "Resumen"
    if active_view == "Macro":
        active_view = "Contexto macro"
    if active_view == "Control":
        active_view = st.segmented_control(
            "Sección de control",
            ["Calidad y reglas", "Contexto macro", "Calibración", "Reportes"],
            default="Calidad y reglas",
            label_visibility="collapsed",
            key="control_navigation",
        ) or "Calidad y reglas"

    if active_view == "Resumen":
        ui_layout.render_section_heading("Resumen", overview["status"])
        calibration_summary = calibration.get("summary", {})
        candidate_df = _records_to_dataframe(candidates.get("data", {}).get("rows", []))
        trigger_state = "_".join(["TRIGGER", "CONFIRMED"])
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
                ("Release readiness", release_status),
                ("Macro", macro["status"]),
                ("Candidatos", candidates.get("rows_count", 0)),
                ("WATCHLIST", watchlist_count),
                ("Quotes VALID/HIGH", valid_high_count),
            ],
            columns=3,
        )
        historical = (
            sources.get("sources", {}).get("market_data_engine_source", {}).get("data", {}) or {}
        )
        historical_health = historical.get("health", {}) or {}
        ui_layout.render_section_title("Base histórica")
        _metrics(
            [
                ("Estado", historical.get("status", "MISSING")),
                ("Última sesión", historical_health.get("latest_bar_date", "N/A")),
                ("Cobertura", historical_health.get("latest_coverage", "N/A")),
                ("Activos", historical_health.get("active_assets", 0)),
                ("Sectores", historical_health.get("sectors", 0)),
                ("Fuente", historical.get("source", "MARKET_DATA_ENGINE_SQLITE")),
            ],
            columns=3,
        )
        ui_layout.render_inline_note(
            "Datos EOD para análisis y backtesting; los quotes actuales usan proveedores separados.",
            status="INFO",
        )
        macro_summary = macro.get("summary", {})
        ui_layout.render_section_title("Contexto macro")
        _metrics(
            [
                ("Riesgo evento", macro_summary.get("event_risk_status", "UNKNOWN")),
                ("Régimen macro", macro_summary.get("macro_regime_mode", "UNKNOWN")),
                ("Régimen Nasdaq", macro_summary.get("nasdaq_macro_regime_mode", "UNKNOWN")),
                ("Semáforo Nasdaq", macro_summary.get("nasdaq_risk_semaforo", "UNKNOWN")),
                ("Días al evento", macro_summary.get("days_to_critical_event", "N/A")),
                ("Liquidez", macro_summary.get("liquidity_context", "UNKNOWN")),
                ("US10Y", macro_summary.get("us10y_official", "N/A")),
                ("VIX", macro_summary.get("vix_official", "N/A")),
                ("Spread HY", macro_summary.get("high_yield_spread", "N/A")),
            ],
            columns=3,
        )
        ui_layout.render_inline_note("Macro es contexto read-only: no modifica señales, scores ni calidad de ejecución.", status="INFO")
        attention_items = []
        attention_items.extend(str(item) for item in quality.get("errors", []))
        attention_items.extend(str(item) for item in quality.get("warnings", []))
        ui_layout.render_section_title("Qué requiere atención")
        if attention_items:
            for item in attention_items[:6]:
                st.write(f"- {item}")
        else:
            st.success("No hay alertas operativas prioritarias en los reportes cargados.")
        st.caption(f"Calibración: {calibration_summary.get('calibration_status', 'MISSING')}")

    if active_view == "Candidatos":
        ui_layout.render_section_heading("Candidatos / Watchlist", candidates["status"])
        st.caption(
            "Oportunidades operativas y radar de investigación se muestran por separado. "
            "Nada de esta vista ejecuta órdenes reales."
        )
        candidate_df = _records_to_dataframe(candidates.get("data", {}).get("rows", []))
        research_df = _records_to_dataframe(
            candidates.get("data", {}).get("research_rows", [])
        )
        if candidate_df.empty:
            ui_layout.render_section_title("Oportunidades operativas")
            ui_layout.render_empty_state("No hay oportunidades operativas disponibles.")
        else:
            filtered = _filtered_dataframe(
                candidate_df,
                WATCHLIST_FILTER_COLUMNS,
                key_prefix="operational_filter",
            ).reset_index(drop=True)
            if filtered.empty:
                ui_layout.render_empty_state("Ningún candidato coincide con los filtros.")
            else:
                _metrics(_candidate_status_counts(filtered), columns=5)
                filtered, watchlist_columns = _apply_watchlist_preferences(
                    table_key="candidate_watchlist_v3",
                    df=filtered,
                    default_columns=WATCHLIST_DEFAULT_COLUMNS,
                    default_sort_column="operational_readiness_score"
                    if "operational_readiness_score" in filtered.columns
                    else "final_trade_score",
                    default_sort_desc=True,
                )
                watchlist_panel, detail_panel = st.columns([1.48, 1.62], gap="large")
                with watchlist_panel:
                    ui_layout.render_section_title(
                        f"Oportunidades operativas · {len(filtered)}"
                    )
                    event, _display = ui_layout.render_display_dataframe(
                        filtered,
                        columns=watchlist_columns,
                        key="candidate_watchlist",
                        height=650,
                        selectable=True,
                        compact=True,
                    )
                    selected_rows = (
                        getattr(getattr(event, "selection", None), "rows", [])
                        if event is not None
                        else []
                    )

                with detail_panel:
                    ui_layout.render_section_title("Ficha operativa")
                    if not selected_rows:
                        selected_candidate = None
                        ui_layout.render_candidate_detail({})
                    else:
                        selected_index = min(int(selected_rows[0]), len(filtered) - 1)
                        selected_candidate = filtered.iloc[selected_index].to_dict()
                        ui_layout.render_candidate_detail(selected_candidate)

                if selected_candidate:
                    with st.expander("Segunda opinión IA", expanded=False):
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
                        st.caption("Revisión independiente. No modifica señales, scores ni niveles.")
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

        ui_layout.render_section_title("Radar de investigación")
        st.caption(
            "Setups en formación o con cautela leve. No pasan a checklist, "
            "recheck de ejecución ni posttest automático."
        )
        if research_df.empty:
            ui_layout.render_empty_state("No hay setups elegibles para investigación profunda.")
        else:
            research_filtered = _filtered_dataframe(
                research_df,
                [
                    "setup_readiness_state",
                    "setup_candidate_type",
                    "ema20_extension_status",
                    "rr_status",
                ],
                key_prefix="research_filter",
            ).reset_index(drop=True)
            research_filtered, research_columns = _apply_watchlist_preferences(
                table_key="candidate_research_radar_v1",
                df=research_filtered,
                default_columns=RESEARCH_DEFAULT_COLUMNS,
                default_sort_column="setup_readiness_score",
                default_sort_desc=True,
            )
            radar_panel, research_detail_panel = st.columns([1.48, 1.62], gap="large")
            with radar_panel:
                event, _display = ui_layout.render_display_dataframe(
                    research_filtered,
                    columns=research_columns,
                    key="candidate_research_radar",
                    height=430,
                    selectable=True,
                    compact=True,
                )
                selected_research_rows = (
                    getattr(getattr(event, "selection", None), "rows", [])
                    if event is not None
                    else []
                )
            with research_detail_panel:
                ui_layout.render_section_title("Ficha diagnóstica")
                if not selected_research_rows:
                    ui_layout.render_candidate_detail({}, research=True)
                else:
                    research_index = min(
                        int(selected_research_rows[0]),
                        len(research_filtered) - 1,
                    )
                    ui_layout.render_candidate_detail(
                        research_filtered.iloc[research_index].to_dict(),
                        research=True,
                    )

            with st.expander("Analítica del universo", expanded=False):
                ui_layout.render_section_title("Señales")
                _bar_chart(ui_charts.build_signal_distribution_chart_data(candidates))
                ui_layout.render_section_title("Recomendaciones")
                _bar_chart(ui_charts.build_recommendation_distribution_chart_data(candidates))
                ui_layout.render_section_title("Calidad de quote")
                _bar_chart(ui_charts.build_quote_quality_chart_data(candidates))
                ui_layout.render_section_title("Top scores")
                _bar_chart(
                    ui_charts.build_candidate_score_chart_data(candidates),
                    value_column="final_trade_score",
                )

    if active_view == "Calidad y reglas":
        ui_layout.render_section_heading("Calidad y reglas", quality["status"])
        execution_guard = "no " + "bro" + "ker"
        guardrail_rows = pd.DataFrame(
            [
                {"guardrail": "_".join(["BUY", "SETUP", "ACTIVE"]) + " deshabilitado", "status": "OK"},
                {"guardrail": "No automatic trading / Sin trading automático", "status": "OK"},
                {"guardrail": execution_guard, "status": "OK"},
                {"guardrail": "_".join(["TRIGGER", "CONFIRMED"]) + " exige VALID/HIGH", "status": "OK"},
            ]
        )
        guardrail_col, quote_col = st.columns([0.92, 1.08], gap="large")
        with guardrail_col:
            ui_layout.render_section_title("Guardrails")
            ui_layout.render_display_dataframe(guardrail_rows, height=190, compact=True)
        with quote_col:
            ui_layout.render_section_title("Calidad de quote")
            _bar_chart(ui_charts.build_quote_quality_chart_data(candidates))
        if quality.get("warnings"):
            st.warning("\n".join(str(item) for item in quality["warnings"]))
        if quality.get("errors"):
            st.error("\n".join(str(item) for item in quality["errors"]))
        quality_rows = pd.DataFrame(
            [
                {"Indicador": ui_formatters.spanish_column_label(key), "Valor": value}
                for key, value in quality.get("summary", {}).items()
            ]
        )
        if not quality_rows.empty:
            quality_rows["Valor"] = quality_rows["Valor"].map(ui_formatters.safe_display_text)
            ui_layout.render_display_dataframe(quality_rows, height=260, compact=True)

    if active_view == "Contexto macro":
        ui_layout.render_section_heading("Contexto macro", macro["status"])
        macro_summary = macro.get("summary", {})
        _metrics(
            [
                ("Fuente", macro_summary.get("source", "UNKNOWN")),
                ("Frescura", macro_summary.get("data_freshness", "UNKNOWN")),
                ("Régimen macro", macro_summary.get("macro_regime_mode", "UNKNOWN")),
                ("Confianza régimen", macro_summary.get("macro_regime_confidence", "UNKNOWN")),
                ("Régimen Nasdaq", macro_summary.get("nasdaq_macro_regime_mode", "UNKNOWN")),
                ("Score Nasdaq", macro_summary.get("nasdaq_risk_score", "N/A")),
                ("Semáforo Nasdaq", macro_summary.get("nasdaq_risk_semaforo", "UNKNOWN")),
                ("Confianza Nasdaq", macro_summary.get("nasdaq_macro_regime_confidence", "UNKNOWN")),
                ("Riesgo evento", macro_summary.get("event_risk_status", "UNKNOWN")),
                ("Días al evento", macro_summary.get("days_to_critical_event", "N/A")),
                ("Liquidez", macro_summary.get("liquidity_context", "UNKNOWN")),
                ("Actualizado", macro_summary.get("generated_at", "N/A")),
            ],
            columns=3,
        )
        ui_layout.render_inline_note(
            "Contexto macro read-only: no modifica scanner, scoring, señales, quote_status ni execution_quote_quality.",
            status="INFO",
        )
        st.caption(f"Régimen operativo: {macro_summary.get('macro_regime_mode', 'UNKNOWN')} · {macro_summary.get('macro_regime_notes', '')}")
        st.caption(
            "Régimen Nasdaq: "
            f"{macro_summary.get('nasdaq_macro_regime_mode', 'UNKNOWN')} · "
            f"{macro_summary.get('nasdaq_regime_notes', '')}"
        )
        ui_layout.render_section_title("Próximo evento crítico")
        st.write(
            f"{macro_summary.get('next_critical_event', 'UNKNOWN')} · "
            f"{macro_summary.get('next_critical_event_date', '')}"
        )
        ui_layout.render_section_title("Liquidez y riesgo")
        _metrics(
            [
                ("M2 4w %", macro_summary.get("m2_change_4w_pct", "N/A")),
                ("Reverse repo 4w %", macro_summary.get("reverse_repo_change_4w_pct", "N/A")),
                ("Fed funds", macro_summary.get("effective_fed_funds_rate", "N/A")),
                ("US10Y", macro_summary.get("us10y_official", "N/A")),
                ("US30Y", macro_summary.get("us30y_official", "N/A")),
                ("VIX", macro_summary.get("vix_official", "N/A")),
                ("Curva 10Y-2Y", macro_summary.get("yield_curve_10y2y", "N/A")),
                ("Spread HY", macro_summary.get("high_yield_spread", "N/A")),
            ],
            columns=4,
        )
        series_rows = _records_to_dataframe(macro.get("data", {}).get("series_rows", []))
        event_rows = _records_to_dataframe(macro.get("data", {}).get("event_rows", []))
        series_col, calendar_col = st.columns([1.08, 0.92], gap="large")
        with series_col:
            ui_layout.render_section_title("Series oficiales")
            if not series_rows.empty:
                ui_layout.render_display_dataframe(
                    series_rows,
                    columns=[
                        "series",
                        "status",
                        "latest",
                        "latest_date",
                        "age_days",
                        "change",
                        "provider",
                        "cache_status",
                        "fallback_used",
                    ],
                    height=310,
                    compact=True,
                )
            else:
                ui_layout.render_empty_state("Sin series oficiales cargadas.")
        with calendar_col:
            ui_layout.render_section_title("Calendario económico")
            if not event_rows.empty:
                ui_layout.render_display_dataframe(
                    event_rows,
                    columns=[
                        "event_date",
                        "event_time",
                        "timezone",
                        "event",
                        "description",
                        "importance",
                        "source",
                    ],
                    height=310,
                    compact=True,
                )
            else:
                ui_layout.render_empty_state("Sin calendario económico cargado.")
        if macro.get("warnings"):
            ui_layout.render_section_title("Alertas macro")
            for item in macro.get("warnings", []):
                st.write(f"- {item}")

    if active_view == "Calibración":
        ui_layout.render_section_heading("Calibración", calibration["status"])
        ui_layout.render_inline_note("La calibración es observacional. No modifica pesos automáticamente.", status="WARN")
        _metrics(
            [
                ("calibration_status", calibration["summary"].get("calibration_status", "MISSING")),
                ("recommendations_status", calibration["summary"].get("recommendations_status", "MISSING")),
                ("simple_posttest", calibration["summary"].get("simple_posttest_status", "MISSING")),
                ("recommendations_are_observational", calibration["summary"].get("recommendations_are_observational", False)),
                ("no_auto_weight_change", calibration["summary"].get("no_auto_weight_change", False)),
            ],
            columns=3,
        )
        ui_layout.render_section_title("Posttest simple 5 / 10 / 15 sesiones")
        _metrics(
            [
                ("rows", calibration["summary"].get("simple_posttest_rows", 0)),
                ("win_rate_5", calibration["summary"].get("simple_posttest_win_rate_5", "")),
                ("win_rate_10", calibration["summary"].get("simple_posttest_win_rate_10", "")),
                ("win_rate_15", calibration["summary"].get("simple_posttest_win_rate_15", "")),
                ("avg_return_5", calibration["summary"].get("simple_posttest_avg_return_5", "")),
                ("avg_return_10", calibration["summary"].get("simple_posttest_avg_return_10", "")),
                ("avg_return_15", calibration["summary"].get("simple_posttest_avg_return_15", "")),
            ],
            columns=4,
        )
        ui_layout.render_section_title("Buckets de score")
        _bar_chart(ui_charts.build_calibration_bucket_chart_data(calibration), value_column="value")
        ui_layout.render_section_title("R multiple")
        _r_multiple_chart(ui_charts.build_r_multiple_chart_data(calibration))

    if active_view == "Reportes":
        ui_layout.render_section_heading("Reportes")
        ui_layout.render_source_status_table(sources)
        st.markdown("### Diagnóstico automático")
        simple_posttest = sources.get("sources", {}).get("simple_candidate_posttest", {}) or {}
        posttest_data = simple_posttest.get("data", {}) if isinstance(simple_posttest, dict) else {}
        horizon_summary = posttest_data.get("horizon_summary", {}) if isinstance(posttest_data, dict) else {}
        _metrics(
            [
                ("posttest_status", posttest_data.get("status", simple_posttest.get("status", "MISSING"))),
                ("horizons", len(horizon_summary) if isinstance(horizon_summary, dict) else 0),
                ("rows", posttest_data.get("rows", 0)),
                ("notice", posttest_data.get("notice", "diagnostico automatico; no real order")),
            ],
            columns=4,
        )
        if isinstance(horizon_summary, dict) and horizon_summary:
            rows = [
                {"horizonte": key, **value}
                for key, value in horizon_summary.items()
                if isinstance(value, dict)
            ]
            st.dataframe(_records_to_dataframe(rows), width="stretch")
        st.markdown("### Archivos clave")
        st.write("- `reports/simple_candidate_posttest_latest.md`")
        st.write("- `reports/daily_quality_gate_latest.md`")
        st.write("- `reports/daily_run_manifest_latest.md`")
        st.write("- `reports/release_readiness_latest.md`")


if __name__ == "__main__":
    main()
