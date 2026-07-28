from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from scoring.execution_review import evaluate_execution_review

SUMMARY_COLUMNS = [
    "rank",
    "ticker",
    "company",
    "sector",
    "signal",
    "recommendation",
    "manual_quote_check_required",
    "quote_recheck_priority",
    "quote_recheck_reason",
    "setup_type",
    "final_trade_score",
    "asset_quality_score",
    "setup_quality_score",
    "final_score",
    "rr",
    "actionable_entry",
    "actionable_stop",
    "actionable_target",
    "theoretical_entry",
    "theoretical_stop",
    "theoretical_target",
    "stop_atr_multiple",
    "stop_atr_status",
    "quote_status",
    "execution_quote_quality",
    "options_bias",
    "options_confidence",
    "all_veto_reasons",
    "penalty_reasons",
    "reason_summary",
]

SCAN_JSON_SUMMARY_COUNT_COLUMNS = [
    "signal",
    "recommendation",
    "execution_readiness_status",
    "quote_status",
    "execution_quote_quality",
    "setup_type",
    "scenario_status",
    "technical_prefilter_status",
    "daily_macd_prefilter_status",
    "weekly_macd_prefilter_status",
    "ema20_extension_prefilter_status",
    "sector_weekly_macd_state",
    "sector_weekly_macd_acceleration_state",
    "sector_context_status",
    "momentum_state",
    "extension_state",
    "sector",
]

SCAN_JSON_TOP_COLUMNS = [
    "rank",
    "ticker",
    "company",
    "sector",
    "industry",
    "signal",
    "recommendation",
    "execution_readiness_status",
    "operational_readiness_score",
    "final_trade_score",
    "setup_type",
    "scenario_status",
    "technical_prefilter_status",
    "technical_prefilter_reason",
    "daily_macd_prefilter_status",
    "weekly_macd_prefilter_status",
    "ema20_extension_prefilter_status",
    "sector_benchmark_symbol",
    "sector_weekly_macd_state",
    "sector_weekly_macd_acceleration_state",
    "sector_context_status",
    "sector_context_reason",
    "momentum_state",
    "extension_state",
    "ema20_extension_status",
    "weekly_macd_histogram_state",
    "quote_status",
    "execution_quote_quality",
    "actionable_entry",
    "actionable_stop",
    "actionable_target",
    "rr",
    "reason_summary",
]


def format_numeric_columns(df: pd.DataFrame, decimals: int = 2) -> pd.DataFrame:
    """
    Round every numeric column for user-facing outputs.
    Internal calculations can keep higher precision before this step.
    """
    out = df.copy()

    numeric_cols = out.select_dtypes(include=["number"]).columns.tolist()
    for col in numeric_cols:
        out[col] = out[col].round(decimals)

    return out


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def _has_text(value) -> bool:
    if value is None:
        return False

    text = str(value).strip()
    return text.lower() not in {"", "none", "nan", "null"}


def recommendation_for_row(row: pd.Series | dict) -> str:
    """
    Operational internal recommendation.

    This is not a financial recommendation or order instruction.
    It classifies what the scanner thinks the human reviewer should do next.
    """
    signal = str(row.get("signal") or "").upper().strip()
    quote_quality = str(row.get("execution_quote_quality") or "").upper().strip()
    quote_status = str(row.get("quote_status") or "").upper().strip()
    setup_type = str(row.get("setup_type") or "").upper().strip()
    trigger_confirmed = _as_bool(row.get("trigger_confirmed"))

    if signal == "VETO":
        return "DO_NOT_TRADE"

    if signal == "AVOID":
        return "AVOID_FOR_NOW"

    if quote_quality == "LOW" or quote_status in {
        "INVALID",
        "STALE_POSSIBLE",
        "MISSING",
        "WIDE_OR_INCOHERENT",
    }:
        if trigger_confirmed:
            return "RECHECK_LIVE_QUOTE"
        return "WATCHLIST_MONITOR_QUOTE"

    if signal == "TRIGGER_CONFIRMED":
        return "MANUAL_REVIEW_TRIGGER_CONFIRMED"

    if signal == "READY_WAIT_TRIGGER":
        return "WAIT_FOR_TRIGGER"

    if signal == "WATCHLIST":
        if setup_type and setup_type != "NO_VALID_SETUP":
            return "WATCHLIST_MONITOR"
        return "WATCHLIST_NO_VALID_SETUP"

    return "REVIEW_MANUALLY"


def add_recommendations(df):
    out = df.copy()

    out["recommendation"] = out.apply(
        lambda row: recommendation_for_row(row.to_dict()),
        axis=1,
    )

    execution_review = out.apply(
        lambda row: evaluate_execution_review(row.to_dict()),
        axis=1,
        result_type="expand",
    )

    for col in execution_review.columns:
        out[col] = execution_review[col]

    return out

def _summary_df(df: pd.DataFrame, max_rows: int = 50) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    cols = [c for c in SUMMARY_COLUMNS if c in df.columns]
    out = df[cols].copy()

    if "signal" in out.columns:
        # Hide pure VETO rows from the compact daily summary unless the scan has no other rows.
        non_veto = out[out["signal"].astype(str).str.upper() != "VETO"]
        if not non_veto.empty:
            out = non_veto

    return out.head(max_rows)

def _df_to_markdown_table(df: pd.DataFrame) -> str:
    """
    Build a simple Markdown table without requiring pandas[tabulate].
    """
    if df.empty:
        return ""

    safe = df.copy()
    safe = safe.fillna("")

    columns = [str(c) for c in safe.columns]

    lines = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")

    for _, row in safe.iterrows():
        values = []
        for col in safe.columns:
            value = str(row[col])
            value = value.replace("\n", " ").replace("|", "\\|")
            values.append(value)
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)

def _save_markdown_summary(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    summary = _summary_df(df)
    lines = [
        "# Analista — resumen operativo",
        "",
        f"Generado: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "Este reporte es un resumen para revisión manual. No ejecuta órdenes ni reemplaza validación operativa.",
        "",
    ]

    if df.empty:
        lines.append("Sin candidatos.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    if "signal" in df.columns:
        lines.append("## Distribución de señales")
        lines.append("")
        for signal, count in df["signal"].fillna("MISSING").astype(str).value_counts().items():
            lines.append(f"- {signal}: {count}")
        lines.append("")

    lines.append("## Candidatos resumidos")
    lines.append("")

    if summary.empty:
        lines.append("Sin candidatos no vetados.")
    else:
        lines.append(_df_to_markdown_table(summary))

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")

def _save_html_summary(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    summary = _summary_df(df)
    generated = html.escape(f"{datetime.now():%Y-%m-%d %H:%M:%S}")

    if summary.empty:
        table_html = "<p>Sin candidatos no vetados.</p>"
    else:
        table_html = summary.to_html(index=False, escape=True)

    signal_html = ""
    if "signal" in df.columns and not df.empty:
        counts = df["signal"].fillna("MISSING").astype(str).value_counts()
        items = "\n".join(
            f"<li><strong>{html.escape(str(k))}</strong>: {int(v)}</li>"
            for k, v in counts.items()
        )
        signal_html = f"<h2>Distribución de señales</h2><ul>{items}</ul>"

    content = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Analista — resumen operativo</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 24px;
      color: #111827;
      background: #ffffff;
    }}
    h1, h2 {{
      color: #0f172a;
    }}
    .muted {{
      color: #64748b;
      font-size: 13px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      font-size: 13px;
    }}
    th, td {{
      border: 1px solid #e5e7eb;
      padding: 6px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f8fafc;
    }}
  </style>
</head>
<body>
  <h1>Analista — resumen operativo</h1>
  <p class="muted">Generado: {generated}</p>
  <p class="muted">Este reporte es un resumen para revisión manual. No ejecuta órdenes ni reemplaza validación operativa.</p>
  {signal_html}
  <h2>Candidatos resumidos</h2>
  {table_html}
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")


def _value_counts(df: pd.DataFrame, column: str) -> dict[str, int]:
    if df.empty or column not in df.columns:
        return {}
    return {
        str(key): int(value)
        for key, value in df[column].fillna("MISSING").astype(str).value_counts().items()
    }


def _compact_scan_payload(
    df: pd.DataFrame,
    *,
    csv_path: Path,
    markdown_path: Path,
    html_path: Path,
    top_rows: int = 150,
) -> dict:
    top_columns = [column for column in SCAN_JSON_TOP_COLUMNS if column in df.columns]
    top = df[top_columns].head(top_rows).copy() if top_columns else pd.DataFrame()
    return {
        "schema_version": "compact_scan_summary_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rows": int(len(df)),
        "columns": list(df.columns),
        "full_detail_csv": str(csv_path),
        "markdown_summary": str(markdown_path),
        "html_summary": str(html_path),
        "json_is_compact": True,
        "csv_is_full_audit_source": True,
        "top_rows_limit": int(top_rows),
        "counts": {
            column: _value_counts(df, column)
            for column in SCAN_JSON_SUMMARY_COUNT_COLUMNS
            if column in df.columns
        },
        "top_candidates": top.to_dict(orient="records"),
    }


def _save_compact_json_summary(
    df: pd.DataFrame,
    path: Path,
    *,
    csv_path: Path,
    markdown_path: Path,
    html_path: Path,
) -> None:
    payload = _compact_scan_payload(
        df,
        csv_path=csv_path,
        markdown_path=markdown_path,
        html_path=html_path,
    )
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def save_reports(
    df: pd.DataFrame,
    config: dict,
    json_out: str | None = None,
    csv_out: str | None = None,
    markdown_out: str | None = None,
    html_out: str | None = None,
) -> None:
    if df is None:
        raise ValueError("save_reports recibió df=None. run_scan() debe devolver un DataFrame.")
    
    files = config.get("outputs", {}).get("files", {})

    json_path = Path(json_out or files.get("latest_scan", "reports/latest_scan.json"))
    csv_path = Path(csv_out or files.get("latest_csv", "reports/latest_scan.csv"))
    hist_dir = Path(files.get("history_dir", "reports/history"))

    markdown_path = Path(
        markdown_out
        or files.get("latest_markdown", str(csv_path.with_suffix(".md")))
    )
    html_path = Path(
        html_out
        or files.get("latest_html", str(csv_path.with_suffix(".html")))
    )

    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    hist_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    history_json = hist_dir / f"scan_{stamp}.json"
    history_csv = hist_dir / f"scan_{stamp}.csv"
    history_md = hist_dir / f"scan_{stamp}.md"
    history_html = hist_dir / f"scan_{stamp}.html"

    output_df = add_recommendations(df)
    output_df = format_numeric_columns(output_df, decimals=2)

    # Always save historical outputs first. CSV keeps the full auditable detail;
    # JSON is intentionally compact so the UI and manifests do not carry the
    # whole universe twice.
    _save_compact_json_summary(
        output_df,
        history_json,
        csv_path=history_csv,
        markdown_path=history_md,
        html_path=history_html,
    )
    output_df.to_csv(history_csv, index=False, float_format="%.2f")
    _save_markdown_summary(output_df, history_md)
    _save_html_summary(output_df, history_html)

    # Try updating latest JSON.
    try:
        _save_compact_json_summary(
            output_df,
            json_path,
            csv_path=csv_path,
            markdown_path=markdown_path,
            html_path=html_path,
        )
    except PermissionError:
        logger.warning(
            f"No se pudo sobrescribir {json_path}. "
            f"El archivo puede estar abierto. Histórico guardado en {history_json}."
        )

    # Try updating latest CSV.
    try:
        output_df.to_csv(csv_path, index=False, float_format="%.2f")
    except PermissionError:
        logger.warning(
            f"No se pudo sobrescribir {csv_path}. "
            f"El archivo puede estar abierto en Excel/Streamlit. "
            f"Histórico guardado en {history_csv}."
        )

    # Try updating latest Markdown.
    try:
        _save_markdown_summary(output_df, markdown_path)
    except PermissionError:
        logger.warning(
            f"No se pudo sobrescribir {markdown_path}. "
            f"Histórico guardado en {history_md}."
        )

    # Try updating latest HTML.
    try:
        _save_html_summary(output_df, html_path)
    except PermissionError:
        logger.warning(
            f"No se pudo sobrescribir {html_path}. "
            f"Histórico guardado en {history_html}."
        )
