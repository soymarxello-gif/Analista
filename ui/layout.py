from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from ui import formatters, guards


COCKPIT_CSS = """
<style>
.stApp {
    background: #080D16;
    color: #E5E7EB;
}
[data-testid="stSidebar"] {
    background: #0B1220;
    border-right: 1px solid rgba(148, 163, 184, 0.18);
}
.block-container {
    padding-top: 1.10rem;
    padding-bottom: 2.25rem;
    max-width: 1560px;
}
.analista-hero {
    border: 1px solid rgba(56, 189, 248, 0.22);
    background: #0D1626;
    border-radius: 8px;
    padding: 1.00rem 1.15rem;
    margin-bottom: 0.80rem;
}
.analista-title {
    color: #F8FAFC;
    font-size: 2.00rem;
    font-weight: 800;
    letter-spacing: 0;
    line-height: 1.15;
    margin: 0;
}
.analista-subtitle {
    color: #A7B0C0;
    font-size: 0.92rem;
    margin-top: 0.35rem;
}
.analista-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 0.75rem;
}
.analista-badge {
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 8px;
    background: #111B2E;
    color: #CBD5E1;
    font-size: 0.76rem;
    padding: 0.22rem 0.52rem;
}
.analista-badge-danger {
    color: #FCA5A5;
    border-color: rgba(248, 113, 113, 0.42);
    background: rgba(127, 29, 29, 0.24);
}
.analista-section {
    color: #F8FAFC;
    font-size: 1.05rem;
    font-weight: 760;
    margin: 1.00rem 0 0.45rem;
}
.candidate-card {
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: #0D1626;
    border-radius: 8px;
    padding: 0.95rem;
}
.candidate-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.65rem;
}
.candidate-field {
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: #0A1220;
    border-radius: 8px;
    padding: 0.55rem 0.65rem;
    min-height: 70px;
}
.candidate-label {
    color: #94A3B8;
    font-size: 0.70rem;
    text-transform: uppercase;
    letter-spacing: 0;
    margin-bottom: 0.28rem;
}
.candidate-value {
    color: #E5E7EB;
    font-size: 0.94rem;
    font-weight: 700;
    overflow-wrap: anywhere;
}
.value-negative { color: #F87171; font-weight: 800; }
.value-warning { color: #FBBF24; font-weight: 760; }
.value-positive { color: #34D399; font-weight: 760; }
.value-neutral { color: #E5E7EB; font-weight: 700; }
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 8px;
    overflow: hidden;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 0.28rem;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    background-color: #0D1626;
    border: 1px solid rgba(148, 163, 184, 0.18);
    color: #CBD5E1;
    padding: 0.35rem 0.72rem;
}
.stTabs [aria-selected="true"] {
    color: #F8FAFC;
    border-color: rgba(56, 189, 248, 0.50);
    background: #10233A;
}
@media (max-width: 900px) {
    .candidate-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 560px) {
    .candidate-grid { grid-template-columns: 1fr; }
}
</style>
"""


def render_cockpit_style() -> None:
    st.markdown(COCKPIT_CSS, unsafe_allow_html=True)


def render_cockpit_header() -> None:
    st.markdown(
        """
        <div class="analista-hero">
            <div class="analista-title">Analista Cockpit</div>
            <div class="analista-subtitle">Scanner long-only para revisión manual. Paper trading only; no real orders.</div>
            <div class="analista-badges">
                <span class="analista-badge analista-badge-danger">Sin compra automática</span>
                <span class="analista-badge">Watchlist seleccionable</span>
                <span class="analista-badge">Validación live quote</span>
                <span class="analista-badge">P0 intacto</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_message(status: Any, text: str = "") -> None:
    status_text = formatters.format_status_badge(status)
    message = text or f"Status: {status_text}"
    level = formatters.status_to_streamlit_level(status_text)
    if level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    elif level == "success":
        st.success(message)
    else:
        st.info(message)


def render_empty_state(message: str = "No data available.") -> None:
    st.info(message)


def render_guardrail_notice() -> None:
    disabled_setup = "_".join(["BUY", "SETUP", "ACTIVE"])
    trigger_state = "_".join(["TRIGGER", "CONFIRMED"])
    st.markdown(
        "\n".join(
            [
                f"- `{disabled_setup}` disabled",
                "- No automatic trading",
                f"- `{trigger_state}` requires quote_status `VALID` and execution_quote_quality `HIGH`",
                "- `RECHECK_LIVE_QUOTE` is not entry",
            ]
        )
    )


def render_no_real_order_notice() -> None:
    st.warning("Manual review only. Paper trading only. No real orders.")
    st.caption(guards.NO_REAL_ORDER_NOTICE)


def _column_config(df: pd.DataFrame) -> dict:
    config = {}
    for column in df.columns:
        lower = str(column).lower()
        if pd.api.types.is_numeric_dtype(df[column]):
            if any(token in lower for token in ["entrada", "stop", "target", "precio", "bid", "ask"]):
                config[column] = st.column_config.NumberColumn(column, format="$%.2f")
            elif any(token in lower for token in ["pct", "%", "spread"]):
                config[column] = st.column_config.NumberColumn(column, format="%.2f")
            else:
                config[column] = st.column_config.NumberColumn(column, format="%.2f")
        elif any(token in lower for token in ["resumen", "alertas", "penalizaciones", "error"]):
            config[column] = st.column_config.TextColumn(column, width="large")
    return config


def render_display_dataframe(
    df: pd.DataFrame,
    *,
    columns: list[str] | None = None,
    key: str | None = None,
    height: int | None = None,
    selectable: bool = False,
):
    display = formatters.prepare_display_dataframe(df, columns=columns)
    if display.empty:
        render_empty_state("No hay datos disponibles.")
        return None, display
    styled = formatters.style_negative_trading_values(display)
    kwargs = {
        "use_container_width": True,
        "hide_index": True,
        "column_config": _column_config(display),
    }
    if height:
        kwargs["height"] = height
    if selectable:
        kwargs.update({"key": key, "on_select": "rerun", "selection_mode": "single-row"})
    event = st.dataframe(styled, **kwargs)
    return event, display


def render_section_title(title: str) -> None:
    st.markdown(f'<div class="analista-section">{escape(title)}</div>', unsafe_allow_html=True)


def _field(label: str, value: Any) -> str:
    text = formatters.format_cell_value(value)
    value_class = formatters.trading_value_class(text)
    return (
        '<div class="candidate-field">'
        f'<div class="candidate-label">{escape(label)}</div>'
        f'<div class="candidate-value value-{value_class}">{escape(str(text))}</div>'
        "</div>"
    )


def render_candidate_detail(row: dict[str, Any]) -> None:
    if not row:
        st.info("Selecciona un ticker para ver su ficha operativa.")
        return
    title = formatters.safe_display_text(row.get("ticker"))
    status = formatters.safe_display_text(row.get("checklist_status") or row.get("signal"))
    st.markdown(
        f'<div class="candidate-card"><h3 style="margin-top:0;color:#F8FAFC;">{escape(title)} · {escape(status)}</h3>'
        '<div class="candidate-grid">'
        + "".join(
            [
                _field("Señal", row.get("signal")),
                _field("Recomendación", row.get("recommendation")),
                _field("Setup", row.get("setup_type")),
                _field("Score operativo", row.get("final_trade_score")),
                _field("Entrada", row.get("actionable_entry")),
                _field("Stop", row.get("actionable_stop")),
                _field("Target", row.get("actionable_target")),
                _field("R/R", row.get("rr")),
                _field("Quote", row.get("quote_status")),
                _field("Calidad ejecución", row.get("execution_quote_quality")),
                _field("Opciones", row.get("options_bias")),
                _field("Confianza opciones", row.get("options_confidence")),
                _field("Escenario", row.get("scenario_status")),
                _field("Confianza escenario", row.get("scenario_confidence")),
                _field("Momentum", row.get("momentum_state")),
                _field("Extensión", row.get("extension_state")),
                _field("Timing entrada", row.get("entry_timing_status")),
                _field("Lectura motor", row.get("engine_recommendation")),
                _field("Sector", row.get("sector")),
                _field("Industria", row.get("industry")),
                _field("Stop vs ATR", row.get("stop_atr_status")),
                _field("Earnings", row.get("next_earnings_date") or row.get("earnings_date")),
            ]
        )
        + "</div>"
        f'<p style="color:#E2E8F0;margin:0.85rem 0 0;">{escape(formatters.safe_display_text(row.get("scenario_thesis")))}</p>'
        f'<p style="color:#FCA5A5;margin:0.55rem 0 0;">Contradicciones: {escape(formatters.compact_reason_list(row.get("scenario_contradictions")))}</p>'
        f'<p style="color:#CBD5E1;margin:0.85rem 0 0;">{escape(formatters.compact_reason_list(row.get("reason_summary") or row.get("penalty_reasons") or row.get("warnings")))}</p>'
        '<p style="color:#94A3B8;margin:0.55rem 0 0;">No comprar automáticamente. Revisar gráfico, volumen, spread, noticia, earnings, macro y sector.</p>'
        "</div>",
        unsafe_allow_html=True,
    )


def render_source_status_table(sources: dict) -> pd.DataFrame:
    report_rows = []
    for source in (sources or {}).get("sources", {}).values():
        report_rows.append(
            {
                "path": source.get("path", ""),
                "status": source.get("status", "UNKNOWN"),
                "exists": source.get("exists", False),
                "size_bytes": source.get("size_bytes", 0),
                "modified": source.get("modified"),
                "error": source.get("error", ""),
            }
        )
    reports_df = pd.DataFrame(report_rows)
    if reports_df.empty:
        render_empty_state("No report sources available.")
        return reports_df
    render_display_dataframe(reports_df)
    missing_invalid = reports_df[reports_df["status"].isin(["MISSING", "INVALID"])]
    if not missing_invalid.empty:
        st.warning("Missing or invalid sources detected.")
        render_display_dataframe(missing_invalid)
    return reports_df
