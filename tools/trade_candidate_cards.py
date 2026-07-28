from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


STATUS_ORDER = {
    "HIGH_QUALITY_REVIEW": 0,
    "REVIEW_MANUALLY": 1,
    "NEEDS_LIVE_QUOTE_RECHECK": 2,
    "BLOCKED": 3,
}

STATUS_LABELS = {
    "BLOCKED": "NO OPERABLE",
    "NEEDS_LIVE_QUOTE_RECHECK": "REQUIERE LIVE QUOTE",
    "REVIEW_MANUALLY": "REVISION MANUAL",
    "HIGH_QUALITY_REVIEW": "ALTA CALIDAD PARA REVISION MANUAL",
}

CARD_FIELDS = [
    "ticker",
    "checklist_status",
    "signal",
    "recommendation",
    "setup_type",
    "sector",
    "industry",
    "final_trade_score",
    "asset_attractiveness_score",
    "operational_readiness_score",
    "operational_readiness_bucket",
    "timing_quality_score",
    "momentum_confirmation_score",
    "scenario_quality_adjustment",
    "timing_penalty_reason",
    "momentum_penalty_reason",
    "engine_block_reason",
    "execution_readiness_status",
    "technical_prefilter_status",
    "technical_prefilter_reason",
    "daily_macd_prefilter_status",
    "weekly_macd_prefilter_status",
    "ema20_extension_prefilter_status",
    "ema20_extension_reference_source",
    "checklist_score",
    "setup_quality_score",
    "asset_quality_score",
    "institutional_score",
    "options_score",
    "options_bias",
    "options_confidence",
    "options_scoring_status",
    "quote_status",
    "execution_quote_quality",
    "actionable_entry",
    "actionable_stop",
    "actionable_target",
    "rr",
    "stop_atr_status",
    "earnings_date",
    "next_earnings_date",
    "checklist_blockers",
    "checklist_warnings",
    "checklist_required_actions",
    "manual_decision_note",
    "scenario_status",
    "scenario_confidence",
    "scenario_operability",
    "scenario_eligible_for_backtest",
    "scenario_guardrail_applied",
    "scenario_guardrail_reason",
    "momentum_state",
    "extension_state",
    "ema20_extension_status",
    "entry_timing_status",
    "macd_histogram_state",
    "weekly_macd_histogram_state",
    "weekly_macd_hist_improving",
    "weekly_macd_hist",
    "weekly_macd_hist_change_1w",
    "weekly_macd_hist_change_2w",
    "sector_benchmark_symbol",
    "sector_weekly_macd_hist",
    "sector_weekly_macd_slope_1w",
    "sector_weekly_macd_prev_slope_1w",
    "sector_weekly_macd_acceleration",
    "sector_weekly_macd_state",
    "sector_weekly_macd_acceleration_state",
    "sector_context_status",
    "sector_context_reason",
    "required_confirmation",
    "engine_recommendation",
    "shadow_entry",
    "shadow_stop",
    "shadow_target",
    "shadow_rr",
    "shadow_stop_atr_multiple",
    "shadow_level_status",
    "technical_ema20",
    "technical_distance_ema20_pct",
    "technical_distance_ema20_atr",
    "technical_ema20_slope_5d_pct",
    "technical_macd_hist",
    "technical_macd_hist_change_1d",
    "technical_macd_hist_change_3d",
]


def _safe_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _display(value, default: str = "MISSING") -> str:
    text = _safe_text(value)
    return text if text else default


def _first_value(row: dict, keys: list[str]):
    for key in keys:
        value = row.get(key)
        if _safe_text(value):
            return value
    return ""


def resolve_default_input(root: Path = ROOT) -> tuple[Path, str]:
    reports = root / "reports"
    checklist = reports / "trade_decision_checklist_latest.csv"
    manual_top = reports / "manual_review_top.csv"

    if checklist.exists():
        return checklist, ""
    return manual_top, "trade_decision_checklist_missing_using_manual_review_top"


def _load_csv(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        return pd.DataFrame(), "input_csv_not_found"
    try:
        return pd.read_csv(path), ""
    except Exception as exc:
        return pd.DataFrame(), f"input_csv_read_failed:{exc}"


def _prepare_cards_dataframe(input_df: pd.DataFrame) -> pd.DataFrame:
    if input_df.empty:
        return pd.DataFrame(columns=CARD_FIELDS)

    out = input_df.copy()

    for col in CARD_FIELDS:
        if col not in out.columns:
            out[col] = ""

    out["ticker"] = out["ticker"].apply(lambda value: _display(value, "UNKNOWN").upper())
    out["checklist_status"] = out["checklist_status"].apply(
        lambda value: _display(value, "REVIEW_MANUALLY").upper()
    )
    out["signal"] = out["signal"].apply(lambda value: _display(value, "UNKNOWN").upper())
    out["recommendation"] = out["recommendation"].apply(
        lambda value: _display(value, "UNKNOWN").upper()
    )

    out["_status_rank"] = out["checklist_status"].map(STATUS_ORDER).fillna(99).astype(int)
    out["_checklist_score_sort"] = out["checklist_score"].apply(_safe_float)
    out["_final_trade_score_sort"] = out["final_trade_score"].apply(_safe_float)

    out = out.sort_values(
        by=[
            "_status_rank",
            "_checklist_score_sort",
            "_final_trade_score_sort",
            "ticker",
        ],
        ascending=[True, False, False, True],
    )

    return out[CARD_FIELDS].copy()


def _contrarian_reading(row: dict) -> str:
    bias = _safe_text(row.get("options_bias")).upper()
    confidence = _safe_text(row.get("options_confidence")).upper()

    if bias == "CROWDED_BULLISH":
        return "Sentimiento alcista saturado; lectura contrarian defensiva."
    if bias == "CROWDED_BEARISH":
        return "Sentimiento bajista saturado; lectura contrarian neutral o levemente favorable."
    if bias == "BULLISH_WITH_DATA":
        return f"Sesgo bullish con datos; ponderar segun confianza {confidence or 'UNKNOWN'}."
    if bias == "BEARISH_WITH_DATA":
        return f"Sesgo bearish con datos; ponderar segun confianza {confidence or 'UNKNOWN'}."
    if bias == "NEUTRAL_WITH_DATA":
        return "Datos disponibles sin extremo direccional."
    if bias in {"UNKNOWN_OPTIONS_FLOW", ""}:
        return "Flujo de opciones desconocido; no usar como gatillo."
    if bias == "NO_OPTIONS_AVAILABLE":
        return "Sin mercado de opciones util; no penalizar por ausencia."
    return "Lectura contextual; opciones no son gatillo automatico."


def _live_recheck_text(row: dict) -> str:
    status = _safe_text(row.get("checklist_status")).upper()
    actions = _safe_text(row.get("checklist_required_actions")).lower()
    if status == "NEEDS_LIVE_QUOTE_RECHECK" or "live_quote_recheck" in actions:
        return "requerido"
    return "no requerido por checklist"


def _render_card(row: dict) -> list[str]:
    ticker = _display(row.get("ticker"), "UNKNOWN").upper()
    status = _display(row.get("checklist_status"), "REVIEW_MANUALLY").upper()
    label = STATUS_LABELS.get(status, "REVISION MANUAL")
    score = _display(row.get("final_trade_score"))
    checklist_score = _display(row.get("checklist_score"))
    earnings = _display(_first_value(row, ["next_earnings_date", "earnings_date"]))

    lines: list[str] = []
    lines.append(f"## {ticker} - {status}")
    lines.append("")
    lines.append(f"**{label}**")
    lines.append("")
    lines.append("### Resumen")
    lines.append(f"- Senal: {_display(row.get('signal'))}")
    lines.append(f"- Recomendacion: {_display(row.get('recommendation'))}")
    lines.append(f"- Setup: {_display(row.get('setup_type'))}")
    lines.append(f"- Score: final={score}; checklist={checklist_score}")
    lines.append(f"- Score activo: {_display(row.get('asset_attractiveness_score'))}")
    lines.append(f"- Score timing: {_display(row.get('timing_quality_score'))}")
    lines.append(f"- Score momentum: {_display(row.get('momentum_confirmation_score'))}")
    lines.append(f"- Readiness operativo: {_display(row.get('operational_readiness_score'))} / {_display(row.get('operational_readiness_bucket'))}")
    lines.append(f"- Estado operativo: {label}")
    lines.append("")
    lines.append("### Niveles operativos")
    lines.append(f"- Entrada: {_display(row.get('actionable_entry'))}")
    lines.append(f"- Stop: {_display(row.get('actionable_stop'))}")
    lines.append(f"- Target: {_display(row.get('actionable_target'))}")
    lines.append(f"- R/R: {_display(row.get('rr'))}")
    lines.append("")
    lines.append("### Niveles diagnosticos")
    lines.append(f"- Entrada shadow: {_display(row.get('shadow_entry'))}")
    lines.append(f"- Stop shadow: {_display(row.get('shadow_stop'))}")
    lines.append(f"- Target shadow: {_display(row.get('shadow_target'))}")
    lines.append(f"- R/R shadow: {_display(row.get('shadow_rr'))}")
    lines.append(f"- Estado shadow: {_display(row.get('shadow_level_status'))}")
    lines.append("")
    lines.append("### Validacion de ejecucion")
    lines.append(f"- quote_status: {_display(row.get('quote_status'))}")
    lines.append(f"- execution_quote_quality: {_display(row.get('execution_quote_quality'))}")
    lines.append(f"- execution_readiness_status: {_display(row.get('execution_readiness_status'))}")
    lines.append(f"- live quote recheck: {_live_recheck_text(row)}")
    lines.append(f"- acciones requeridas: {_display(row.get('checklist_required_actions'), 'NONE')}")
    lines.append("")
    lines.append("### Tecnica")
    lines.append(f"- prefiltro_tecnico: {_display(row.get('technical_prefilter_status'))}")
    lines.append(f"- razon_prefiltro: {_display(row.get('technical_prefilter_reason'), 'NONE')}")
    lines.append(f"- macd_diario_prefiltro: {_display(row.get('daily_macd_prefilter_status'))}")
    lines.append(f"- macd_semanal_prefiltro: {_display(row.get('weekly_macd_prefilter_status'))}")
    lines.append(f"- ema20_prefiltro: {_display(row.get('ema20_extension_prefilter_status'))}")
    lines.append(f"- referencia_extension: {_display(row.get('ema20_extension_reference_source'))}")
    lines.append(f"- setup_type: {_display(row.get('setup_type'))}")
    lines.append(f"- stop_atr_status: {_display(row.get('stop_atr_status'))}")
    lines.append(f"- warnings tecnicos: {_display(row.get('checklist_warnings'), 'NONE')}")
    lines.append("")
    lines.append("### Diagnostico de escenario")
    lines.append(f"- scenario_status: {_display(row.get('scenario_status'))}")
    lines.append(f"- scenario_confidence: {_display(row.get('scenario_confidence'))}")
    lines.append(f"- scenario_operability: {_display(row.get('scenario_operability'))}")
    lines.append(f"- momentum_state: {_display(row.get('momentum_state'))}")
    lines.append(f"- extension_state: {_display(row.get('extension_state'))}")
    lines.append(f"- ema20_extension_status: {_display(row.get('ema20_extension_status'))}")
    lines.append(f"- entry_timing_status: {_display(row.get('entry_timing_status'))}")
    lines.append(f"- macd_histogram_state: {_display(row.get('macd_histogram_state'))}")
    lines.append(f"- weekly_macd_histogram_state: {_display(row.get('weekly_macd_histogram_state'))}")
    lines.append(f"- weekly_macd_hist_change_1w: {_display(row.get('weekly_macd_hist_change_1w'))}")
    lines.append(f"- sector_benchmark_symbol: {_display(row.get('sector_benchmark_symbol'))}")
    lines.append(f"- sector_weekly_macd_state: {_display(row.get('sector_weekly_macd_state'))}")
    lines.append(f"- sector_weekly_macd_acceleration_state: {_display(row.get('sector_weekly_macd_acceleration_state'))}")
    lines.append(f"- sector_weekly_macd_slope_1w: {_display(row.get('sector_weekly_macd_slope_1w'))}")
    lines.append(f"- sector_weekly_macd_acceleration: {_display(row.get('sector_weekly_macd_acceleration'))}")
    lines.append(f"- sector_context_status: {_display(row.get('sector_context_status'))}")
    lines.append(f"- sector_context_reason: {_display(row.get('sector_context_reason'), 'NONE')}")
    lines.append(f"- distance_ema20_atr: {_display(row.get('technical_distance_ema20_atr'))}")
    lines.append(f"- distance_ema20_pct: {_display(row.get('technical_distance_ema20_pct'))}")
    lines.append(f"- macd_hist_change_3d: {_display(row.get('technical_macd_hist_change_3d'))}")
    lines.append(f"- timing_penalty_reason: {_display(row.get('timing_penalty_reason'), 'NONE')}")
    lines.append(f"- momentum_penalty_reason: {_display(row.get('momentum_penalty_reason'), 'NONE')}")
    lines.append(f"- engine_block_reason: {_display(row.get('engine_block_reason'), 'NONE')}")
    lines.append(f"- confirmacion requerida: {_display(row.get('required_confirmation'), 'NONE')}")
    lines.append(f"- recomendacion del motor: {_display(row.get('engine_recommendation'))}")
    lines.append(
        "- niveles shadow: "
        f"entry={_display(row.get('shadow_entry'))}; "
        f"stop={_display(row.get('shadow_stop'))}; "
        f"target={_display(row.get('shadow_target'))}; "
        f"R/R={_display(row.get('shadow_rr'))}; "
        f"status={_display(row.get('shadow_level_status'))}"
    )
    lines.append("")
    lines.append("### Opciones / flujo institucional")
    lines.append(f"- options_bias: {_display(row.get('options_bias'))}")
    lines.append(f"- options_confidence: {_display(row.get('options_confidence'))}")
    lines.append(f"- options_score: {_display(row.get('options_score'))}")
    lines.append(f"- options_scoring_status: {_display(row.get('options_scoring_status'), 'CONTEXT_ONLY_NOT_SCORED')}")
    lines.append(f"- lectura contrarian: {_contrarian_reading(row)}")
    lines.append("")
    lines.append("### Riesgos y bloqueos")
    lines.append(f"- blockers: {_display(row.get('checklist_blockers'), 'NONE')}")
    lines.append(f"- warnings: {_display(row.get('checklist_warnings'), 'NONE')}")
    lines.append(f"- earnings: {earnings}")
    lines.append(f"- notas: {_display(row.get('manual_decision_note'), 'Revision manual pendiente.')}")
    lines.append("")
    lines.append("### Decision manual")
    lines.append("- No ejecutar automaticamente.")
    lines.append("- Revisar grafico, volumen, spread, noticia, earnings, macro y sector.")
    lines.append("- Resultado manual: PENDIENTE.")
    lines.append("")
    return lines


def build_trade_candidate_cards_dataframe(input_df: pd.DataFrame) -> pd.DataFrame:
    return _prepare_cards_dataframe(input_df)


def build_trade_candidate_cards_markdown(
    cards_df: pd.DataFrame,
    *,
    status: str = "PASS",
    warning: str = "",
) -> str:
    lines: list[str] = []
    lines.append("# Analista - trade candidate cards")
    lines.append("")
    lines.append("- Fichas de revision manual. No generan senales, entradas ni ejecucion automatica.")
    lines.append(f"- status: {status}")
    lines.append(f"- rows: {int(len(cards_df))}")
    if warning:
        lines.append(f"- warning: {warning}")
    lines.append("")

    counts = cards_df["checklist_status"].value_counts().to_dict() if not cards_df.empty else {}
    lines.append("## Summary")
    lines.append("")
    for key in ["HIGH_QUALITY_REVIEW", "REVIEW_MANUALLY", "NEEDS_LIVE_QUOTE_RECHECK", "BLOCKED"]:
        lines.append(f"- {key.lower()}: {int(counts.get(key, 0))}")
    lines.append("")

    if cards_df.empty:
        lines.append("_Sin candidatos para generar fichas._")
        return "\n".join(lines)

    for _, row in cards_df.iterrows():
        lines.extend(_render_card(row.to_dict()))

    return "\n".join(lines).rstrip() + "\n"


def build_trade_candidate_cards_payload(
    cards_df: pd.DataFrame,
    *,
    input_path: Path,
    markdown_out: Path,
    json_out: Path,
    status: str = "PASS",
    warning: str = "",
    error: str = "",
) -> dict:
    counts = cards_df["checklist_status"].value_counts().to_dict() if not cards_df.empty else {}
    return {
        "status": status,
        "rows": int(len(cards_df)),
        "high_quality_review": int(counts.get("HIGH_QUALITY_REVIEW", 0)),
        "review_manually": int(counts.get("REVIEW_MANUALLY", 0)),
        "needs_live_quote_recheck": int(counts.get("NEEDS_LIVE_QUOTE_RECHECK", 0)),
        "blocked": int(counts.get("BLOCKED", 0)),
        "warning": warning,
        "error": error,
        "input_path": str(input_path),
        "markdown_out": str(markdown_out),
        "json_out": str(json_out),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cards": cards_df.fillna("").to_dict(orient="records"),
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_trade_candidate_cards_reports(
    input_path: Path | None = None,
    *,
    markdown_out: Path | None = None,
    json_out: Path | None = None,
    root: Path = ROOT,
) -> dict:
    warning = ""
    if input_path is None:
        input_path, warning = resolve_default_input(root)

    markdown_out = markdown_out or root / "reports" / "trade_candidate_cards_latest.md"
    json_out = json_out or root / "reports" / "trade_candidate_cards_latest.json"

    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)

    input_df, error = _load_csv(input_path)
    if error:
        cards_df = pd.DataFrame(columns=CARD_FIELDS)
        markdown_out.write_text(
            build_trade_candidate_cards_markdown(cards_df, status="FAIL", warning=warning),
            encoding="utf-8",
        )
        result = build_trade_candidate_cards_payload(
            cards_df,
            input_path=input_path,
            markdown_out=markdown_out,
            json_out=json_out,
            status="FAIL",
            warning=warning,
            error=error,
        )
        _write_json(json_out, result)
        return result

    cards_df = build_trade_candidate_cards_dataframe(input_df)
    markdown_out.write_text(
        build_trade_candidate_cards_markdown(cards_df, status="PASS", warning=warning),
        encoding="utf-8",
    )
    result = build_trade_candidate_cards_payload(
        cards_df,
        input_path=input_path,
        markdown_out=markdown_out,
        json_out=json_out,
        status="PASS",
        warning=warning,
    )
    _write_json(json_out, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera fichas operativas manuales por candidato.")
    parser.add_argument("--input-path", default=None)
    parser.add_argument("--markdown-out", default="reports/trade_candidate_cards_latest.md")
    parser.add_argument("--json-out", default="reports/trade_candidate_cards_latest.json")
    args = parser.parse_args()

    result = save_trade_candidate_cards_reports(
        input_path=ROOT / args.input_path if args.input_path else None,
        markdown_out=ROOT / args.markdown_out,
        json_out=ROOT / args.json_out,
        root=ROOT,
    )

    print("=== ANALISTA TRADE CANDIDATE CARDS ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result['rows']}")
    print(f"High quality review: {result.get('high_quality_review', 0)}")
    print(f"Review manually: {result.get('review_manually', 0)}")
    print(f"Needs live quote recheck: {result.get('needs_live_quote_recheck', 0)}")
    print(f"Blocked: {result.get('blocked', 0)}")
    print(f"Markdown: {result['markdown_out']}")
    print(f"JSON: {result['json_out']}")
    if result.get("warning"):
        print(f"Warning: {result['warning']}")
    if result.get("error"):
        print(f"Error: {result['error']}")

    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
