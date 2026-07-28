from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from ui import formatters, guards


COCKPIT_CSS = """
<style>
#MainMenu,
footer,
[data-testid="stDecoration"],
[data-testid="stToolbar"] {
    visibility: hidden;
    height: 0;
}
.stApp {
    background: #030507;
    color: #E5E7EB;
}
[data-testid="stSidebar"] {
    background: #070B12;
    border-right: 1px solid rgba(148, 163, 184, 0.18);
}
[data-testid="stHeader"] {
    display: none;
    height: 0;
}
.block-container {
    padding-top: 2.25rem;
    padding-bottom: 2.25rem;
    padding-left: clamp(0.8rem, 2vw, 2.4rem);
    padding-right: clamp(0.8rem, 2vw, 2.4rem);
    width: 100%;
    max-width: none;
}
.analista-hero {
    border: 1px solid rgba(56, 189, 248, 0.20);
    background:
        linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(7, 11, 18, 0.98)),
        #070B12;
    border-radius: 8px;
    padding: 0.9rem 1rem;
    margin-bottom: 0.7rem;
    width: 100%;
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.25);
}
.analista-hero .analista-title {
    color: #F8FAFC;
    font-size: 1.45rem !important;
    font-weight: 800;
    letter-spacing: 0;
    line-height: 1.15;
    margin: 0 !important;
    padding: 0 !important;
}
.analista-subtitle {
    color: #A7B0C0;
    font-size: 0.86rem;
    margin-top: 0.35rem;
}
.analista-command {
    display: grid;
    grid-template-columns: minmax(260px, 0.9fr) minmax(420px, 1.4fr);
    gap: 0.75rem;
    align-items: stretch;
}
.analista-system-line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.45rem;
    margin-top: 0.6rem;
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
.analista-action-row {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.55rem;
    margin: -0.25rem 0 0.55rem;
}
.analista-section-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.45rem;
    margin: 0.95rem 0 0.45rem;
}
.analista-section-heading {
    color: #F8FAFC;
    font-size: 1.08rem;
    font-weight: 780;
    line-height: 1.2;
}
.analista-inline-note {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border: 1px solid rgba(148, 163, 184, 0.20);
    border-radius: 8px;
    background: rgba(10, 18, 32, 0.78);
    color: #CBD5E1;
    padding: 0.28rem 0.56rem;
    font-size: 0.78rem;
    font-weight: 650;
    margin: 0.18rem 0 0.42rem;
}
.analista-chip-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));
    gap: 0.42rem;
    margin: 0.38rem 0 0.58rem;
}
.analista-chip {
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 8px;
    background: #070B12;
    padding: 0.42rem 0.55rem;
    min-width: 0;
    min-height: 42px;
}
.analista-chip-label {
    color: #94A3B8;
    font-size: 0.64rem;
    text-transform: uppercase;
    letter-spacing: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.analista-chip-value {
    color: #F8FAFC;
    font-size: 0.88rem;
    font-weight: 780;
    line-height: 1.2;
    margin-top: 0.13rem;
    overflow-wrap: anywhere;
}
.analista-ribbon {
    border: 1px solid rgba(148, 163, 184, 0.20);
    border-radius: 8px;
    padding: 0.55rem 0.75rem;
    margin: 0.55rem 0 0.75rem;
    font-size: 0.88rem;
    font-weight: 650;
}
.analista-ribbon-positive {
    background: rgba(6, 78, 59, 0.26);
    border-color: rgba(52, 211, 153, 0.30);
    color: #86EFAC;
}
.analista-ribbon-warning {
    background: rgba(113, 63, 18, 0.24);
    border-color: rgba(251, 191, 36, 0.32);
    color: #FDE68A;
}
.analista-ribbon-negative {
    background: rgba(127, 29, 29, 0.24);
    border-color: rgba(248, 113, 113, 0.34);
    color: #FCA5A5;
}
.analista-ribbon-neutral {
    background: rgba(15, 23, 42, 0.72);
    border-color: rgba(56, 189, 248, 0.22);
    color: #BAE6FD;
}
.analista-context-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(120px, 1fr));
    gap: 0.55rem;
}
.analista-context-card {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 8px;
    background: rgba(10, 18, 32, 0.78);
    padding: 0.55rem 0.65rem;
    min-width: 0;
}
.analista-context-label {
    color: #94A3B8;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0;
    margin-bottom: 0.18rem;
}
.analista-context-value {
    color: #F8FAFC;
    font-size: 0.94rem;
    font-weight: 780;
    overflow-wrap: anywhere;
}
.analista-section {
    color: #F8FAFC;
    font-size: 1.05rem;
    font-weight: 760;
    margin: 1.00rem 0 0.45rem;
}
.candidate-card {
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: #070B12;
    border-radius: 8px;
    padding: 0.95rem;
    width: 100%;
}
.candidate-header {
    display: grid;
    grid-template-columns: minmax(160px, 0.75fr) minmax(240px, 1.25fr);
    gap: 0.65rem;
    align-items: start;
    border-bottom: 1px solid rgba(148, 163, 184, 0.16);
    padding-bottom: 0.75rem;
    margin-bottom: 0.8rem;
}
.candidate-title {
    color: #F8FAFC;
    font-size: 1.34rem;
    font-weight: 850;
    margin: 0;
}
.candidate-subtitle {
    color: #94A3B8;
    font-size: 0.82rem;
    margin-top: 0.25rem;
}
.candidate-notice {
    border: 1px solid rgba(251, 191, 36, 0.28);
    background: rgba(113, 63, 18, 0.20);
    color: #FDE68A;
    border-radius: 8px;
    padding: 0.55rem 0.7rem;
    font-size: 0.84rem;
}
.candidate-section-title {
    color: #CBD5E1;
    font-size: 0.88rem;
    font-weight: 780;
    text-transform: uppercase;
    letter-spacing: 0;
    margin: 0.95rem 0 0.5rem;
}
.candidate-two-column {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.65rem;
}
.candidate-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 142px), 1fr));
    gap: 0.65rem;
    width: 100%;
}
.candidate-field {
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: #0A101A;
    border-radius: 8px;
    padding: 0.46rem 0.58rem;
    min-height: 54px;
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
.candidate-text-block {
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 8px;
    background: rgba(10, 18, 32, 0.64);
    padding: 0.65rem 0.75rem;
    color: #CBD5E1;
    font-size: 0.86rem;
    line-height: 1.45;
    margin-top: 0.65rem;
}
.watchlist-shell {
    border: 1px solid rgba(56, 189, 248, 0.14);
    background: #070B12;
    border-radius: 8px;
    padding: 0.65rem;
}
.detail-shell {
    border: 1px solid rgba(148, 163, 184, 0.18);
    background: #060A10;
    border-radius: 8px;
    padding: 0.65rem;
}
.value-negative { color: #F87171; font-weight: 800; }
.value-warning { color: #FBBF24; font-weight: 760; }
.value-positive { color: #34D399; font-weight: 760; }
.value-neutral { color: #E5E7EB; font-weight: 700; }
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 8px;
    overflow: hidden;
    width: 100%;
}
div[data-testid="stDataFrame"] [role="columnheader"],
div[data-testid="stDataFrame"] [role="gridcell"] {
    font-size: 0.82rem;
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
div[data-testid="stMetric"] {
    background: #070B12;
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 8px;
    padding: 0.55rem 0.7rem;
}
div[data-testid="stMetric"] label {
    color: #94A3B8;
}
div[data-testid="stMetricValue"] {
    font-size: 1.35rem;
}
.compact-table div[data-testid="stDataFrame"] [role="columnheader"],
.compact-table div[data-testid="stDataFrame"] [role="gridcell"] {
    font-size: 0.76rem;
}
div[data-testid="stSegmentedControl"] {
    margin: 0.25rem 0 0.7rem;
}
div[data-testid="stSegmentedControl"] button {
    min-height: 38px;
}
div[data-testid="stHorizontalBlock"] {
    align-items: stretch;
}
div[data-testid="column"] {
    min-width: 0;
}
div[data-testid="stVegaLiteChart"],
div[data-testid="stVegaLiteChart"] > div {
    width: 100%;
}
@media (max-width: 900px) {
    .analista-command,
    .candidate-header,
    .candidate-two-column {
        grid-template-columns: 1fr;
    }
    .analista-context-grid {
        grid-template-columns: repeat(2, minmax(120px, 1fr));
    }
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        flex: 1 1 min(100%, 420px) !important;
        width: 100% !important;
    }
}
@media (max-width: 560px) {
    .block-container {
        padding-top: 1.3rem;
        padding-left: 0.65rem;
        padding-right: 0.65rem;
    }
    .analista-command { gap: 0.55rem; }
    .analista-system-line {
        gap: 0.32rem;
        margin-top: 0.45rem;
    }
    .analista-badge {
        font-size: 0.68rem;
        padding: 0.18rem 0.42rem;
    }
    .analista-context-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.42rem;
    }
    .analista-context-card {
        padding: 0.48rem 0.5rem;
    }
    .analista-context-label {
        font-size: 0.62rem;
    }
    .analista-context-value {
        font-size: 0.82rem;
    }
    .candidate-grid { grid-template-columns: 1fr; }
    .analista-chip-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .analista-hero .analista-title { font-size: 1.24rem !important; }
    .analista-subtitle { font-size: 0.78rem; }
    .analista-hero { padding: 0.62rem 0.65rem; }
    div[data-testid="stMetric"] {
        min-width: 0;
        width: 100%;
    }
    div[data-testid="stSegmentedControl"] > div {
        flex-wrap: wrap;
    }
    div[data-testid="stSegmentedControl"] button {
        flex: 1 1 44%;
    }
}
</style>
"""


def render_cockpit_style() -> None:
    st.markdown(COCKPIT_CSS, unsafe_allow_html=True)


def render_cockpit_header(
    *,
    quality_status: Any = "UNKNOWN",
    release_status: Any = "UNKNOWN",
    updated_at: Any = "N/A",
    freshness_items: list[tuple[str, Any, Any]] | None = None,
    context_items: list[tuple[str, Any, Any]] | None = None,
) -> None:
    quality_class = formatters.trading_value_class(quality_status)
    release_class = formatters.trading_value_class(release_status)
    freshness_badges = ""
    for label, value, status in freshness_items or []:
        value_class = formatters.trading_value_class(status)
        freshness_badges += (
            f'<span class="analista-badge value-{value_class}">'
            f'{escape(str(label))}: {escape(formatters.safe_display_text(value))}'
            "</span>"
        )
    context_cards = ""
    for label, value, status in context_items or []:
        value_class = formatters.trading_value_class(status if status not in (None, "") else value)
        context_cards += (
            '<div class="analista-context-card">'
            f'<div class="analista-context-label">{escape(str(label))}</div>'
            f'<div class="analista-context-value value-{value_class}">{escape(formatters.safe_display_text(value))}</div>'
            "</div>"
        )
    st.markdown(
        f"""
        <section class="analista-hero" aria-label="Resumen operativo del cockpit">
            <div class="analista-command">
                <div>
                    <div class="analista-title" role="heading" aria-level="1">Analista Cockpit</div>
                    <div class="analista-subtitle">Watchlist profesional para evaluación long-only y revisión manual.</div>
                    <div class="analista-system-line">
                        <span class="analista-badge value-{quality_class}">Quality gate: {escape(formatters.display_status_label(quality_status))}</span>
                        <span class="analista-badge value-{release_class}">Release: {escape(formatters.display_status_label(release_status))}</span>
                        <span class="analista-badge analista-badge-danger">Sin órdenes reales</span>
                    </div>
                </div>
                <div class="analista-context-grid">
                    {context_cards or f'<div class="analista-context-card"><div class="analista-context-label">Reportes</div><div class="analista-context-value">{escape(formatters.safe_display_text(updated_at))}</div></div>'}
                </div>
            </div>
            <div class="analista-system-line">
                {freshness_badges or f'<span class="analista-badge">Reportes: {escape(formatters.safe_display_text(updated_at))}</span>'}
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_status_message(status: Any, text: str = "") -> None:
    status_text = formatters.format_status_badge(status)
    message = text or f"Status: {status_text}"
    value_class = formatters.trading_value_class(status_text)
    st.markdown(
        f'<div class="analista-ribbon analista-ribbon-{escape(value_class)}">{escape(message)}</div>',
        unsafe_allow_html=True,
    )


def render_section_heading(title: str, status: Any | None = None, note: str = "") -> None:
    status_html = ""
    if status not in (None, ""):
        value_class = formatters.trading_value_class(status)
        status_html = (
            f'<span class="analista-badge value-{value_class}">'
            f'{escape(formatters.display_status_label(status))}'
            "</span>"
        )
    note_html = (
        f'<span class="analista-inline-note">{escape(str(note))}</span>'
        if note
        else ""
    )
    st.markdown(
        f"""
        <div class="analista-section-header">
            <div class="analista-section-heading">{escape(title)}</div>
            {status_html}
            {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_inline_note(text: str, status: Any = "INFO") -> None:
    value_class = formatters.trading_value_class(status)
    st.markdown(
        f'<span class="analista-inline-note value-{value_class}">{escape(str(text))}</span>',
        unsafe_allow_html=True,
    )


def render_metric_chips(items: list[tuple[str, Any]], columns: int | None = None) -> None:
    visible = [(str(label), value) for label, value in items if label not in (None, "")]
    if not visible:
        return
    style = ""
    if columns:
        style = f' style="grid-template-columns: repeat({max(1, int(columns))}, minmax(0, 1fr));"'
    chips = []
    for label, value in visible:
        formatted = formatters.format_metric_value(label, value)
        value_class = formatters.trading_value_class(formatted)
        chips.append(
            '<div class="analista-chip">'
            f'<div class="analista-chip-label">{escape(label)}</div>'
            f'<div class="analista-chip-value value-{value_class}">{escape(str(formatted))}</div>'
            "</div>"
        )
    st.markdown(
        f'<div class="analista-chip-grid"{style}>{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )


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
    st.markdown(
        '<div class="analista-ribbon analista-ribbon-warning">'
        "Revisión manual y diagnóstico automático solamente. No se envían órdenes reales."
        "</div>",
        unsafe_allow_html=True,
    )


def _column_config(df: pd.DataFrame, *, compact: bool = False) -> dict:
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
            if lower in {"score operativo", "r/r"}:
                config[column] = st.column_config.NumberColumn(column, format="%.2f", width="small")
        elif lower in {"ticker", "r/r"}:
            config[column] = st.column_config.TextColumn(column, width="small")
        elif lower in {
            "estado",
            "estado operativo",
            "diagnóstico escenario",
            "estado quote",
            "calidad ejecución",
            "señal interna",
            "revisión sugerida",
            "checklist",
            "setup",
        }:
            config[column] = st.column_config.TextColumn(column, width="small" if compact else "medium")
        elif any(token in lower for token in ["resumen", "alertas", "penalizaciones", "error"]):
            config[column] = st.column_config.TextColumn(column, width="medium" if compact else "large")
        elif compact:
            config[column] = st.column_config.TextColumn(column, width="small")
    return config


def render_display_dataframe(
    df: pd.DataFrame,
    *,
    columns: list[str] | None = None,
    key: str | None = None,
    height: int | None = None,
    selectable: bool = False,
    compact: bool = False,
):
    display = formatters.prepare_display_dataframe(df, columns=columns)
    if display.empty:
        render_empty_state("No hay datos disponibles.")
        return None, display
    styled = formatters.style_negative_trading_values(display)
    kwargs = {
        "width": "stretch",
        "hide_index": True,
        "column_config": _column_config(display, compact=compact),
    }
    if height:
        kwargs["height"] = height
    if selectable:
        kwargs.update({"key": key, "on_select": "rerun", "selection_mode": "single-row"})
    event = st.dataframe(styled, **kwargs)
    return event, display


def render_section_title(title: str) -> None:
    st.markdown(f'<div class="analista-section">{escape(title)}</div>', unsafe_allow_html=True)


def render_panel_start(panel_class: str = "detail-shell") -> None:
    st.markdown(f'<div class="{escape(panel_class)}">', unsafe_allow_html=True)


def render_panel_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def _field(label: str, value: Any) -> str:
    text = (
        formatters.display_status_with_code(value)
        if formatters.format_status_badge(value) in formatters.STATUS_LABELS_ES
        else formatters.format_cell_value(value)
    )
    value_class = formatters.trading_value_class(text)
    return (
        '<div class="candidate-field">'
        f'<div class="candidate-label">{escape(label)}</div>'
        f'<div class="candidate-value value-{value_class}">{escape(str(text))}</div>'
        "</div>"
    )


def _section(title: str, fields: list[tuple[str, Any]]) -> str:
    visible_fields = fields or []
    return (
        f'<div class="candidate-section-title">{escape(title)}</div>'
        '<div class="candidate-grid">'
        + "".join(_field(label, value) for label, value in visible_fields)
        + "</div>"
    )


def render_candidate_detail(row: dict[str, Any]) -> None:
    if not row:
        st.markdown(
            '<div class="analista-ribbon analista-ribbon-neutral">'
            "Selecciona un ticker para ver su ficha operativa."
            "</div>",
            unsafe_allow_html=True,
        )
        return
    title = formatters.safe_display_text(row.get("ticker"))
    status = formatters.safe_display_text(
        row.get("checklist_status")
        or row.get("manual_deep_dive_decision")
        or row.get("scenario_status")
        or row.get("signal")
    )
    status_class = formatters.trading_value_class(status)
    st.markdown(
        '<article class="candidate-card" aria-label="Ficha operativa del candidato">'
        '<div class="candidate-header">'
        "<div>"
        f'<h3 class="candidate-title">{escape(title)}</h3>'
        f'<div class="candidate-subtitle value-{status_class}">{escape(formatters.display_status_with_code(status))}</div>'
        "</div>"
        '<div class="candidate-notice">Ficha operativa para revisión manual. No comprar automáticamente; validar gráfico, volumen, spread, noticia, earnings, macro y sector.</div>'
        "</div>"
        + _section(
            "Prioridad operativa",
            [
                ("Señal", row.get("signal")),
                ("Recomendación", row.get("recommendation")),
                ("Setup", row.get("setup_type")),
                ("Readiness", row.get("operational_readiness_score")),
                ("Bucket", row.get("operational_readiness_bucket")),
                ("Score activo", row.get("asset_attractiveness_score") or row.get("asset_quality_score")),
                ("Score timing", row.get("timing_quality_score")),
                ("Score momentum", row.get("momentum_confirmation_score")),
                ("Estado operativo", row.get("execution_readiness_status")),
                ("Score operativo", row.get("final_trade_score")),
            ],
        )
        + '<div class="candidate-two-column">'
        + "<div>"
        + _section(
            "Niveles operativos",
            [
                ("Entrada", row.get("actionable_entry")),
                ("Stop", row.get("actionable_stop")),
                ("Target", row.get("actionable_target")),
                ("R/R", row.get("rr")),
            ],
        )
        + "</div><div>"
        + _section(
            "Niveles diagnósticos",
            [
                ("Entrada shadow", row.get("shadow_entry")),
                ("Stop shadow", row.get("shadow_stop")),
                ("Target shadow", row.get("shadow_target")),
                ("R/R shadow", row.get("shadow_rr")),
                ("Estado shadow", row.get("shadow_level_status")),
            ],
        )
        + "</div></div>"
        + _section(
            "Ejecución, escenario y contexto",
            [
                ("Prefiltro técnico", row.get("technical_prefilter_status")),
                ("MACD diario prefiltro", row.get("daily_macd_prefilter_status")),
                ("MACD semanal prefiltro", row.get("weekly_macd_prefilter_status")),
                ("EMA20 prefiltro", row.get("ema20_extension_prefilter_status")),
                ("Referencia EMA20", row.get("ema20_extension_reference_source")),
                ("Quote", row.get("quote_status")),
                ("Calidad ejecución", row.get("execution_quote_quality")),
                ("Escenario", row.get("scenario_status")),
                ("Confianza escenario", row.get("scenario_confidence")),
                ("Momentum", row.get("momentum_state")),
                ("Extensión", row.get("extension_state")),
                ("Extensión EMA20", row.get("ema20_extension_status")),
                ("Timing entrada", row.get("entry_timing_status")),
                ("MACD diario", row.get("macd_histogram_state")),
                ("MACD semanal", row.get("weekly_macd_histogram_state")),
                ("MACD semanal 1s", row.get("weekly_macd_hist_change_1w")),
                ("ETF sector", row.get("sector_benchmark_symbol")),
                ("MACD semanal sector", row.get("sector_weekly_macd_state")),
                ("Aceleración sector", row.get("sector_weekly_macd_acceleration_state")),
                ("Pendiente sector", row.get("sector_weekly_macd_slope_1w")),
                ("Contexto sector", row.get("sector_context_status")),
                ("Dist. EMA20 ATR", row.get("technical_distance_ema20_atr")),
                ("Dist. EMA20 %", row.get("technical_distance_ema20_pct")),
                ("Opciones", row.get("options_bias")),
                ("Confianza opciones", row.get("options_confidence")),
                ("Macro", row.get("macro_regime_mode") or row.get("macro_risk_flag")),
                ("Sector", row.get("sector")),
                ("Industria", row.get("industry")),
                ("Stop vs ATR", row.get("stop_atr_status")),
                ("Earnings", row.get("next_earnings_date") or row.get("earnings_date")),
            ],
        )
        + _section(
            "Invalidación y advertencias",
            [
                ("Penalización timing", row.get("timing_penalty_reason")),
                ("Penalización momentum", row.get("momentum_penalty_reason")),
                ("Bloqueo motor", row.get("engine_block_reason")),
                ("Razón sector", row.get("sector_context_reason")),
                ("Lectura motor", row.get("engine_recommendation")),
                ("Confirmación requerida", row.get("required_confirmation")),
            ],
        )
        + f'<div class="candidate-text-block"><strong>Tesis:</strong> {escape(formatters.safe_display_text(row.get("scenario_thesis")))}</div>'
        + f'<div class="candidate-text-block value-negative"><strong>Contradicciones:</strong> {escape(formatters.compact_reason_list(row.get("scenario_contradictions")))}</div>'
        + f'<div class="candidate-text-block"><strong>Notas:</strong> {escape(formatters.compact_reason_list(row.get("reason_summary") or row.get("penalty_reasons") or row.get("warnings")))}</div>'
        "</article>",
        unsafe_allow_html=True,
    )


def render_single_ticker_diagnostic_detail(row: dict[str, Any]) -> None:
    if not row:
        st.info("Ejecuta una consulta puntual para ver la ficha diagnóstica.")
        return
    title = formatters.safe_display_text(row.get("ticker"))
    status = formatters.safe_display_text(
        row.get("manual_deep_dive_decision")
        or row.get("scenario_status")
        or "INVESTIGACION_MANUAL"
    )
    st.markdown(
        f'<article class="candidate-card" aria-label="Ficha diagnóstica de consulta puntual"><h3 style="margin-top:0;color:#F8FAFC;">Consulta puntual · investigación manual · {escape(title)} · {escape(status)}</h3>'
        '<p style="color:#FBBF24;margin:0 0 0.85rem;">No pasó por screener completo ni filtro macro; no es señal operativa.</p>'
        '<div class="candidate-grid">'
        + "".join(
            [
                _field("Decisión manual", row.get("manual_deep_dive_decision")),
                _field("Setup", row.get("setup_type")),
                _field("Score diagnóstico", row.get("final_trade_score")),
                _field("Entrada diagnóstica", row.get("actionable_entry")),
                _field("Stop diagnóstico", row.get("actionable_stop")),
                _field("Target diagnóstico", row.get("actionable_target")),
                _field("R/R diagnóstico", row.get("rr")),
                _field("Quote", row.get("quote_status")),
                _field("Calidad ejecución", row.get("execution_quote_quality")),
                _field("Fuente quote", row.get("analysis_quote_source") or row.get("quote_source")),
                _field("Frescura quote", row.get("analysis_quote_freshness")),
                _field("Escenario", row.get("scenario_status")),
                _field("Momentum", row.get("momentum_state")),
                _field("Extensión", row.get("extension_state")),
                _field("Timing entrada", row.get("entry_timing_status")),
                _field("MACD semanal", row.get("weekly_macd_histogram_state")),
                _field("Stop vs ATR", row.get("stop_atr_status")),
            ]
        )
        + "</div>"
        f'<p style="color:#E2E8F0;margin:0.85rem 0 0;">{escape(formatters.safe_display_text(row.get("scenario_thesis")))}</p>'
        f'<p style="color:#FCA5A5;margin:0.55rem 0 0;">Alertas: {escape(formatters.compact_reason_list(row.get("warnings")))}</p>'
        f'<p style="color:#CBD5E1;margin:0.55rem 0 0;">Acciones requeridas: {escape(formatters.compact_reason_list(row.get("required_actions")))}</p>'
        '<p style="color:#94A3B8;margin:0.55rem 0 0;">Investigación manual solamente. No comprar automáticamente; validar gráfico, volumen, spread, noticias, earnings, macro y sector.</p>'
        "</article>",
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
