from __future__ import annotations

from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.express as px


st.set_page_config(
    page_title="Analista | Swing Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
.stApp {
    background:
        radial-gradient(circle at top left, rgba(56, 189, 248, 0.12), transparent 28%),
        radial-gradient(circle at top right, rgba(167, 139, 250, 0.10), transparent 26%),
        linear-gradient(180deg, #070A12 0%, #0B0F19 48%, #0B0F19 100%);
    color: #E5E7EB;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #111827 100%);
    border-right: 1px solid rgba(148, 163, 184, 0.18);
}
.block-container {
    padding-top: 1.1rem;
    padding-bottom: 2.5rem;
}
.main-header {
    padding: 1.20rem 1.35rem;
    border: 1px solid rgba(56, 189, 248, 0.24);
    border-radius: 20px;
    background:
        linear-gradient(135deg, rgba(56, 189, 248, 0.12), rgba(167, 139, 250, 0.08)),
        rgba(17, 24, 39, 0.78);
    box-shadow: 0 18px 45px rgba(0, 0, 0, 0.30);
    margin-bottom: 1.10rem;
}
.main-title {
    font-size: 2.05rem;
    font-weight: 850;
    letter-spacing: -0.035em;
    color: #F9FAFB;
    margin: 0;
}
.main-subtitle {
    color: #9CA3AF;
    font-size: 0.98rem;
    margin-top: 0.30rem;
}
.badge-row {
    display: flex;
    gap: 0.50rem;
    flex-wrap: wrap;
    margin-top: 0.85rem;
}
.badge {
    padding: 0.25rem 0.60rem;
    border-radius: 999px;
    border: 1px solid rgba(148, 163, 184, 0.28);
    color: #CBD5E1;
    background: rgba(15, 23, 42, 0.86);
    font-size: 0.76rem;
}
.kpi-card {
    padding: 1rem;
    border-radius: 18px;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015)),
        rgba(17, 24, 39, 0.88);
    border: 1px solid rgba(148, 163, 184, 0.20);
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.25);
    min-height: 108px;
}
.kpi-label {
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #9CA3AF;
    margin-bottom: 0.35rem;
}
.kpi-value {
    font-size: 1.72rem;
    line-height: 1.10;
    font-weight: 850;
    color: #F9FAFB;
}
.kpi-help {
    font-size: 0.80rem;
    color: #9CA3AF;
    margin-top: 0.45rem;
}
.section-title {
    margin-top: 1.15rem;
    margin-bottom: 0.55rem;
    font-weight: 820;
    letter-spacing: -0.02em;
    color: #F9FAFB;
}
.small-muted {
    color: #9CA3AF;
    font-size: 0.84rem;
}
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 16px;
    overflow: hidden;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 0.35rem;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 999px;
    background-color: rgba(15, 23, 42, 0.82);
    border: 1px solid rgba(148, 163, 184, 0.18);
    color: #CBD5E1;
    padding: 0.35rem 0.85rem;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.24), rgba(167, 139, 250, 0.17));
    color: #F9FAFB;
    border: 1px solid rgba(56, 189, 248, 0.38);
}
hr {
    border: none;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def discover_csv_files() -> list[Path]:
    files = []
    reports = Path("reports")
    history = reports / "history"

    if reports.exists():
        files.extend(sorted(reports.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True))
    if history.exists():
        files.extend(sorted(history.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True))

    seen = set()
    unique = []
    for f in files:
        key = str(f.resolve())
        if key not in seen:
            unique.append(f)
            seen.add(key)
    return unique


def file_label(path: Path) -> str:
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        size_kb = path.stat().st_size / 1024
        return f"{path.as_posix()}  ·  {modified}  ·  {size_kb:,.0f} KB"
    except Exception:
        return path.as_posix()


@st.cache_data(show_spinner=False)
def load_csv(path_str: str) -> pd.DataFrame:
    df = pd.read_csv(path_str)

    for col in ["signal", "setup_type", "sector", "industry", "ticker", "company", "options_bias", "options_confidence"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    for col in df.select_dtypes(include=["number"]).columns:
        df[col] = df[col].round(2)

    return df


def metric_card(label: str, value: str, help_text: str = "", accent: str = "#38BDF8"):
    st.markdown(
        f"""
        <div class="kpi-card" style="border-top: 3px solid {accent};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_column_config(df: pd.DataFrame) -> dict:
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    price_cols = {"price", "entry", "stop", "target", "bid", "ask", "max_call_oi_strike", "max_put_oi_strike", "max_pain_approx"}
    pct_cols = {
        "atr_pct", "spread_pct", "revenue_growth", "earnings_growth",
        "operating_margins", "profit_margins", "gross_margins",
        "return_on_equity", "return_on_assets", "short_percent_float",
        "held_percent_institutions", "atm_implied_volatility",
        "call_volume_share", "call_oi_share", "near_call_oi_share",
    }

    config = {}
    for col in numeric_cols:
        if col in price_cols:
            config[col] = st.column_config.NumberColumn(col, format="$%.2f")
        elif col in pct_cols:
            config[col] = st.column_config.NumberColumn(col, format="%.2f")
        else:
            config[col] = st.column_config.NumberColumn(col, format="%.2f")

    if "reason_summary" in df.columns:
        config["reason_summary"] = st.column_config.TextColumn("reason_summary", width="large")
    if "ticker" in df.columns:
        config["ticker"] = st.column_config.TextColumn("ticker", width="small")

    return config


def make_signal_bar(df: pd.DataFrame):
    if "signal" not in df.columns or df.empty:
        return None

    order = ["BUY_SETUP_ACTIVE", "READY_WAIT_TRIGGER", "WATCHLIST", "AVOID", "VETO"]
    colors = {
        "BUY_SETUP_ACTIVE": "#22C55E",
        "READY_WAIT_TRIGGER": "#38BDF8",
        "WATCHLIST": "#F59E0B",
        "AVOID": "#94A3B8",
        "VETO": "#EF4444",
    }

    counts = df["signal"].value_counts().reindex(order).fillna(0).reset_index()
    counts.columns = ["signal", "count"]

    fig = px.bar(
        counts,
        x="signal",
        y="count",
        color="signal",
        color_discrete_map=colors,
        text="count",
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        height=310,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="",
        yaxis_title="Cantidad",
    )
    fig.update_traces(textposition="outside", marker_line_width=0)
    return fig


def make_sector_chart(df: pd.DataFrame):
    if "sector" not in df.columns or "final_score" not in df.columns or df.empty:
        return None

    sec = (
        df[df["sector"].astype(str).str.strip() != ""]
        .groupby("sector", dropna=False)
        .agg(avg_score=("final_score", "mean"), candidates=("final_score", "count"))
        .reset_index()
        .sort_values("avg_score", ascending=True)
        .tail(12)
    )

    if sec.empty:
        return None

    sec["avg_score"] = sec["avg_score"].round(2)

    fig = px.bar(
        sec,
        x="avg_score",
        y="sector",
        orientation="h",
        text="avg_score",
        color="avg_score",
        color_continuous_scale="Blues",
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=370,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="Score promedio",
        yaxis_title="",
        coloraxis_showscale=False,
    )
    fig.update_traces(textposition="outside")
    return fig


def make_score_scatter(df: pd.DataFrame):
    if not {"final_score", "rr", "ticker"}.issubset(df.columns) or df.empty:
        return None

    plot_df = df.copy()
    if "signal" not in plot_df.columns:
        plot_df["signal"] = ""

    colors = {
        "BUY_SETUP_ACTIVE": "#22C55E",
        "READY_WAIT_TRIGGER": "#38BDF8",
        "WATCHLIST": "#F59E0B",
        "AVOID": "#94A3B8",
        "VETO": "#EF4444",
    }

    hover_cols = [c for c in ["setup_type", "sector", "industry", "options_bias", "reason_summary"] if c in plot_df.columns]
    fig = px.scatter(
        plot_df,
        x="rr",
        y="final_score",
        color="signal",
        color_discrete_map=colors,
        hover_name="ticker",
        hover_data=hover_cols,
    )
    fig.add_hline(y=85, line_dash="dot", line_color="#22C55E", opacity=0.60)
    fig.add_hline(y=80, line_dash="dot", line_color="#38BDF8", opacity=0.55)
    fig.add_vline(x=2.0, line_dash="dot", line_color="#22C55E", opacity=0.55)
    fig.add_vline(x=1.7, line_dash="dot", line_color="#F59E0B", opacity=0.45)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=390,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="R:R",
        yaxis_title="Final Score",
        legend_title="Signal",
    )
    return fig


def make_options_bias_chart(df: pd.DataFrame):
    if "options_bias" not in df.columns or df.empty:
        return None

    order = ["BULLISH", "NEUTRAL", "BEARISH", "NEUTRAL_NO_DATA", "NEUTRAL_DISABLED"]
    colors = {
        "BULLISH": "#22C55E",
        "NEUTRAL": "#94A3B8",
        "BEARISH": "#EF4444",
        "NEUTRAL_NO_DATA": "#64748B",
        "NEUTRAL_DISABLED": "#475569",
    }

    counts = df["options_bias"].replace("", "NO_VALUE").value_counts().reset_index()
    counts.columns = ["options_bias", "count"]
    counts["order"] = counts["options_bias"].apply(lambda x: order.index(x) if x in order else 99)
    counts = counts.sort_values("order")

    fig = px.bar(
        counts,
        x="options_bias",
        y="count",
        color="options_bias",
        color_discrete_map=colors,
        text="count",
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=310,
        margin=dict(l=10, r=10, t=20, b=10),
        showlegend=False,
        xaxis_title="",
        yaxis_title="Cantidad",
    )
    fig.update_traces(textposition="outside")
    return fig


def make_options_score_chart(df: pd.DataFrame):
    required = {"options_score", "put_call_volume_ratio", "ticker"}
    if not required.issubset(df.columns) or df.empty:
        return None

    plot_df = df.copy()
    plot_df = plot_df[plot_df["options_score"].notna()]
    if plot_df.empty:
        return None

    if "options_bias" not in plot_df.columns:
        plot_df["options_bias"] = ""

    colors = {
        "BULLISH": "#22C55E",
        "NEUTRAL": "#94A3B8",
        "BEARISH": "#EF4444",
        "NEUTRAL_NO_DATA": "#64748B",
        "NEUTRAL_DISABLED": "#475569",
    }

    hover_cols = [c for c in ["signal", "setup_type", "final_score", "call_volume_share", "near_call_oi_share"] if c in plot_df.columns]

    fig = px.scatter(
        plot_df,
        x="put_call_volume_ratio",
        y="options_score",
        color="options_bias",
        color_discrete_map=colors,
        hover_name="ticker",
        hover_data=hover_cols,
    )
    fig.add_hline(y=0.65, line_dash="dot", line_color="#22C55E", opacity=0.60)
    fig.add_hline(y=0.40, line_dash="dot", line_color="#EF4444", opacity=0.55)
    fig.add_vline(x=0.35, line_dash="dot", line_color="#F59E0B", opacity=0.55)
    fig.add_vline(x=1.30, line_dash="dot", line_color="#EF4444", opacity=0.45)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=390,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="Put/Call Volume Ratio",
        yaxis_title="Options Score",
        legend_title="Options Bias",
    )
    return fig


def make_options_top_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "rank", "ticker", "signal", "setup_type", "final_score",
        "options_score", "options_bias", "options_confidence",
        "put_call_volume_ratio", "put_call_oi_ratio",
        "call_volume_share", "near_call_oi_share",
        "max_call_oi_strike", "max_put_oi_strike", "max_pain_approx",
        "atm_implied_volatility", "total_option_volume", "total_option_open_interest",
        "reason_summary",
    ]
    cols = [c for c in cols if c in df.columns]
    out = df[cols].copy()
    if "options_score" in out.columns:
        out = out.sort_values("options_score", ascending=False)
    return out


st.markdown(
    """
    <div class="main-header">
        <div class="main-title">Analista</div>
        <div class="main-subtitle">Real-Time Long Swing Setup Scanner · Acciones comunes USA · Long-only · Swing 4–21 días</div>
        <div class="badge-row">
            <span class="badge">Yahoo/yfinance</span>
            <span class="badge">Setup scanner</span>
            <span class="badge">Put/Call Flow</span>
            <span class="badge">2 decimales</span>
            <span class="badge">Selector CSV</span>
            <span class="badge">No ETFs operables</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

csv_files = discover_csv_files()

with st.sidebar:
    st.markdown("## Panel de control")

    if st.button("Actualizar lista de archivos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if not csv_files:
        st.error("No encontré archivos CSV en `reports/` ni `reports/history/`.")
        st.info("Ejecuta primero: `python run_scanner.py --verbose`")
        st.stop()

    default_idx = 0
    for i, p in enumerate(csv_files):
        if p.name == "latest_scan.csv":
            default_idx = i
            break

    selected_file = st.selectbox(
        "Archivo de reporte",
        options=csv_files,
        index=default_idx,
        format_func=file_label,
    )

    if st.button("Recargar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Puedes elegir latest, pruebas o históricos.")
    st.divider()

df = load_csv(str(selected_file))

if df.empty:
    st.warning("El archivo seleccionado está vacío.")
    st.stop()

with st.sidebar:
    st.markdown("### Filtros")

    signal_options = sorted(df["signal"].dropna().unique()) if "signal" in df.columns else []
    default_signals = [s for s in ["BUY_SETUP_ACTIVE", "READY_WAIT_TRIGGER", "WATCHLIST", "AVOID"] if s in signal_options]
    if not default_signals:
        default_signals = signal_options

    selected_signals = st.multiselect("Signal", signal_options, default=default_signals)

    setup_options = sorted(df["setup_type"].dropna().unique()) if "setup_type" in df.columns else []
    selected_setups = st.multiselect("Setup", setup_options, default=setup_options)

    sector_options = sorted([x for x in df["sector"].dropna().unique() if str(x).strip()]) if "sector" in df.columns else []
    selected_sectors = st.multiselect("Sector", sector_options, default=[], placeholder="Todos")

    if "options_bias" in df.columns:
        options_biases = sorted([x for x in df["options_bias"].dropna().unique() if str(x).strip()])
        selected_options_bias = st.multiselect("Options bias", options_biases, default=options_biases)
    else:
        selected_options_bias = []

    if "final_score" in df.columns:
        score_range = st.slider("Final Score", 0.0, 100.0, (0.0, 100.0), step=0.50)
    else:
        score_range = (0.0, 100.0)

    rr_min = st.slider("R:R mínimo", 0.0, 5.0, 0.0, step=0.10) if "rr" in df.columns else 0.0
    opt_score_min = st.slider("Options score mínimo", 0.0, 1.0, 0.0, step=0.05) if "options_score" in df.columns else 0.0
    search = st.text_input("Buscar ticker / empresa", value="", placeholder="Ej: NVDA, Microsoft...")

    st.divider()
    st.markdown("### Archivo activo")
    st.caption(selected_file.as_posix())
    try:
        st.caption(f"Modificado: {datetime.fromtimestamp(selected_file.stat().st_mtime):%Y-%m-%d %H:%M:%S}")
    except Exception:
        pass

view = df.copy()

if selected_signals and "signal" in view.columns:
    view = view[view["signal"].isin(selected_signals)]
if selected_setups and "setup_type" in view.columns:
    view = view[view["setup_type"].isin(selected_setups)]
if selected_sectors and "sector" in view.columns:
    view = view[view["sector"].isin(selected_sectors)]
if selected_options_bias and "options_bias" in view.columns:
    view = view[view["options_bias"].isin(selected_options_bias)]
if "final_score" in view.columns:
    view = view[(view["final_score"] >= score_range[0]) & (view["final_score"] <= score_range[1])]
if "rr" in view.columns:
    view = view[view["rr"].fillna(0) >= rr_min]
if "options_score" in view.columns:
    view = view[view["options_score"].fillna(0) >= opt_score_min]
if search:
    s = search.strip().lower()
    mask = pd.Series(False, index=view.index)
    for col in ["ticker", "company"]:
        if col in view.columns:
            mask = mask | view[col].fillna("").astype(str).str.lower().str.contains(s, regex=False)
    view = view[mask]

counts = df["signal"].value_counts().to_dict() if "signal" in df.columns else {}
active = counts.get("BUY_SETUP_ACTIVE", 0)
ready = counts.get("READY_WAIT_TRIGGER", 0)
watch = counts.get("WATCHLIST", 0)
veto = counts.get("VETO", 0)
avg_score = df["final_score"].mean() if "final_score" in df.columns else 0
best_score = df["final_score"].max() if "final_score" in df.columns else 0
avg_rr = df["rr"].dropna().mean() if "rr" in df.columns else 0

bullish_options = int((df["options_bias"] == "BULLISH").sum()) if "options_bias" in df.columns else 0

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    metric_card("Candidatos", f"{len(df):,.0f}", f"Filtrados: {len(view):,.0f}", "#38BDF8")
with col2:
    metric_card("BUY Active", f"{active:,.0f}", "Setup confirmado", "#22C55E")
with col3:
    metric_card("Ready", f"{ready:,.0f}", "Esperando trigger", "#38BDF8")
with col4:
    metric_card("Watchlist", f"{watch:,.0f}", "Interesante", "#F59E0B")
with col5:
    metric_card("Score máx.", f"{best_score:.2f}", f"Prom: {avg_score:.2f}", "#A78BFA")
with col6:
    metric_card("Opciones Bullish", f"{bullish_options:,.0f}", f"R:R prom: {avg_rr:.2f}", "#22C55E")

tab_overview, tab_opportunities, tab_options, tab_table, tab_diagnostics = st.tabs(
    ["Resumen", "Oportunidades", "Opciones", "Tabla completa", "Diagnóstico"]
)

with tab_overview:
    left, right = st.columns([1.05, 1.0])

    with left:
        st.markdown('<h3 class="section-title">Distribución de señales</h3>', unsafe_allow_html=True)
        fig = make_signal_bar(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos suficientes para graficar señales.")

    with right:
        st.markdown('<h3 class="section-title">Score por sector</h3>', unsafe_allow_html=True)
        fig = make_sector_chart(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos sectoriales suficientes.")

    st.markdown('<h3 class="section-title">Mapa Score vs R:R</h3>', unsafe_allow_html=True)
    fig = make_score_scatter(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay columnas suficientes para el mapa Score vs R:R.")

with tab_opportunities:
    st.markdown('<h3 class="section-title">Candidatos operativos</h3>', unsafe_allow_html=True)

    priority = ["BUY_SETUP_ACTIVE", "READY_WAIT_TRIGGER", "WATCHLIST"]
    opp = df[df["signal"].isin(priority)] if "signal" in df.columns else df.copy()
    if "final_score" in opp.columns:
        opp = opp.sort_values("final_score", ascending=False)

    cols = [
        "rank", "ticker", "company", "sector", "industry", "signal", "setup_type",
        "final_score", "rs_score", "trend_score", "volume_score", "structure_score",
        "options_score", "options_bias", "options_confidence",
        "entry", "stop", "target", "rr", "atr_pct", "relative_volume",
        "earnings_date", "days_to_earnings", "reason_summary",
    ]
    cols = [c for c in cols if c in opp.columns]

    if opp.empty:
        st.warning("No hay oportunidades con señales prioritarias.")
    else:
        st.dataframe(
            opp[cols].head(50),
            use_container_width=True,
            height=520,
            column_config=build_column_config(opp[cols]),
            hide_index=True,
        )

with tab_options:
    st.markdown('<h3 class="section-title">Put/Call Flow y posicionamiento de opciones</h3>', unsafe_allow_html=True)

    if "options_score" not in df.columns:
        st.warning("El archivo seleccionado no contiene columnas de opciones. Ejecuta un scan con options_flow activado.")
    else:
        left, right = st.columns([1.0, 1.0])

        with left:
            st.markdown('<h4 class="section-title">Distribución Options Bias</h4>', unsafe_allow_html=True)
            fig = make_options_bias_chart(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de options_bias.")

        with right:
            st.markdown('<h4 class="section-title">Options Score vs Put/Call Ratio</h4>', unsafe_allow_html=True)
            fig = make_options_score_chart(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Faltan columnas para el gráfico de opciones.")

        st.markdown('<h4 class="section-title">Ranking de flujo de opciones</h4>', unsafe_allow_html=True)
        opt_table = make_options_top_table(df)
        st.dataframe(
            opt_table,
            use_container_width=True,
            height=560,
            column_config=build_column_config(opt_table),
            hide_index=True,
        )

        st.caption(
            "Lectura: options_score confirma o penaliza setups. No genera compra automática. "
            "Put/call extremadamente bajo puede ser señal de crowded trade."
        )

with tab_table:
    st.markdown('<h3 class="section-title">Tabla completa filtrada</h3>', unsafe_allow_html=True)
    st.caption(f"Mostrando {len(view):,.0f} de {len(df):,.0f} filas del archivo seleccionado.")

    preferred_cols = [
        "rank", "ticker", "company", "sector", "industry", "signal", "veto_reasons",
        "setup_type", "final_score", "rs_score", "trend_score", "volume_score",
        "sector_score", "structure_score", "rr_score", "liquidity_pass",
        "liquidity_score", "momentum_score", "fundamental_score",
        "options_score", "options_bias", "options_confidence", "options_data_available",
        "put_call_volume_ratio", "put_call_oi_ratio", "call_volume_share", "near_call_oi_share",
        "max_call_oi_strike", "max_put_oi_strike", "max_pain_approx",
        "atm_implied_volatility", "total_option_volume", "total_option_open_interest",
        "entry", "stop", "target", "rr", "price", "atr_pct", "relative_volume",
        "avg_volume_20d", "dollar_volume_20d", "spread_pct",
        "earnings_date", "days_to_earnings", "revenue_growth", "earnings_growth",
        "operating_margins", "debt_to_equity", "return_on_equity",
        "market_regime", "warnings", "reason_summary",
    ]
    ordered_cols = [c for c in preferred_cols if c in view.columns]
    remaining_cols = [c for c in view.columns if c not in ordered_cols]
    table = view[ordered_cols + remaining_cols]

    st.dataframe(
        table,
        use_container_width=True,
        height=650,
        column_config=build_column_config(table),
        hide_index=True,
    )

    csv_bytes = table.to_csv(index=False, float_format="%.2f").encode("utf-8-sig")
    st.download_button(
        "Descargar tabla filtrada",
        data=csv_bytes,
        file_name=f"analista_filtered_{datetime.now():%Y%m%d_%H%M%S}.csv",
        mime="text/csv",
        use_container_width=True,
    )

with tab_diagnostics:
    st.markdown('<h3 class="section-title">Diagnóstico de calidad de datos</h3>', unsafe_allow_html=True)

    diag_cols = [
        "ticker", "signal", "veto_reasons", "warnings", "liquidity_pass",
        "sector", "industry", "earnings_date", "days_to_earnings",
        "options_data_available", "options_source", "options_confidence",
        "spread_pct", "bid", "ask", "quote_type", "exchange",
    ]
    diag_cols = [c for c in diag_cols if c in df.columns]

    if diag_cols:
        st.dataframe(
            df[diag_cols],
            use_container_width=True,
            height=420,
            column_config=build_column_config(df[diag_cols]),
            hide_index=True,
        )

    if "veto_reasons" in df.columns:
        st.markdown('<h3 class="section-title">Frecuencia de vetos</h3>', unsafe_allow_html=True)

        veto_series = (
            df["veto_reasons"]
            .fillna("")
            .astype(str)
            .str.split(",")
            .explode()
            .str.strip()
        )
        veto_series = veto_series[veto_series != ""]

        if not veto_series.empty:
            veto_df = veto_series.value_counts().reset_index()
            veto_df.columns = ["veto_reason", "count"]

            fig = px.bar(
                veto_df,
                x="count",
                y="veto_reason",
                orientation="h",
                text="count",
                color="count",
                color_continuous_scale="Reds",
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=320,
                margin=dict(l=10, r=10, t=20, b=10),
                coloraxis_showscale=False,
                xaxis_title="Cantidad",
                yaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay vetos en el archivo seleccionado.")

    st.markdown('<h3 class="section-title">Archivo seleccionado</h3>', unsafe_allow_html=True)
    st.code(str(selected_file), language="text")

st.markdown("---")
st.markdown(
    '<div class="small-muted">Analista MVP · Scanner analítico. No ejecuta órdenes ni reemplaza validación manual.</div>',
    unsafe_allow_html=True,
)
