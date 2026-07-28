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


CHECKLIST_STATUSES = {
    "BLOCKED",
    "NEEDS_LIVE_QUOTE_RECHECK",
    "REVIEW_MANUALLY",
    "HIGH_QUALITY_REVIEW",
}

OUTPUT_COLUMNS = [
    "ticker",
    "signal",
    "recommendation",
    "setup_type",
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
    "sector",
    "industry",
    "metadata_source",
    "quote_source",
    "deep_analysis_selected",
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
    "technical_macd_hist_change_3d",
    "checklist_status",
    "checklist_score",
    "checklist_required_actions",
    "checklist_blockers",
    "checklist_warnings",
    "automatic_posttest_status",
    "automatic_posttest_reason",
    "buy_now_candidate",
    "manual_decision_note",
]


def _safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _safe_float(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _first_value(row: dict, keys: list[str]):
    for key in keys:
        value = row.get(key)
        if _safe_text(value):
            return value
    return None


def _join(items: list[str]) -> str:
    return "; ".join(dict.fromkeys([item for item in items if item]))


def _derive_automatic_posttest_status(
    *,
    status: str,
    signal: str,
    quote_status: str,
    execution_quality: str,
    recommendation: str,
    scenario_status: str,
    scenario_eligible_text: str,
    scenario_eligible: bool,
    execution_readiness: str,
    entry_timing_status: str,
    ema20_extension_status: str,
    macd_histogram_state: str,
    weekly_macd_histogram_state: str,
    sector_weekly_macd_state: str,
    technical_prefilter_status: str,
    technical_prefilter_reason: str,
    shadow_level_status: str,
    blockers: list[str],
    entry: float | None,
    stop: float | None,
    target: float | None,
    rr: float | None,
    min_rr: float,
) -> tuple[str, str, bool]:
    reasons: list[str] = []
    if status != "HIGH_QUALITY_REVIEW":
        reasons.append(f"checklist_status_{status.lower()}")
    if signal not in {"WATCHLIST", "TRIGGER_CONFIRMED"}:
        reasons.append(f"signal_{signal.lower() or 'missing'}")
    if quote_status != "VALID":
        reasons.append(f"quote_status_{quote_status.lower() or 'missing'}")
    if execution_quality != "HIGH":
        reasons.append(f"execution_quote_quality_{execution_quality.lower() or 'missing'}")
    if recommendation in {"RECHECK_LIVE_QUOTE", "DO_NOT_TRADE", "AVOID_FOR_NOW"}:
        reasons.append(f"recommendation_{recommendation.lower()}")
    if scenario_status and scenario_status != "VALID_TRIGGER":
        reasons.append(f"scenario_{scenario_status.lower()}")
    if scenario_eligible_text and not scenario_eligible:
        reasons.append("scenario_not_eligible")
    if execution_readiness and execution_readiness != "EXECUTION_READY_REVIEW":
        reasons.append(f"execution_readiness_{execution_readiness.lower()}")
    if entry_timing_status not in {"", "ON_TIME"}:
        reasons.append(f"entry_timing_{entry_timing_status.lower()}")
    if ema20_extension_status not in {"", "HEALTHY"}:
        reasons.append(f"ema20_extension_{ema20_extension_status.lower()}")
    if macd_histogram_state in {"MACD_HIST_DETERIORATING", "MACD_HIST_FLATTENING"}:
        reasons.append(f"macd_histogram_{macd_histogram_state.lower()}")
    if weekly_macd_histogram_state != "WEEKLY_MACD_HIST_IMPROVING":
        reasons.append(
            f"weekly_macd_histogram_{weekly_macd_histogram_state.lower() or 'missing'}"
        )
    if sector_weekly_macd_state in {
        "SECTOR_MACD_DECELERATING",
        "SECTOR_MACD_BEARISH",
        "SECTOR_MACD_IMPROVING_BUT_DECELERATING",
        "SECTOR_MACD_MIXED",
        "SECTOR_MACD_UNKNOWN",
    }:
        reasons.append(f"sector_weekly_macd_{sector_weekly_macd_state.lower()}")
    if technical_prefilter_status and technical_prefilter_status != "PASS":
        reasons.append(f"technical_prefilter_{technical_prefilter_status.lower()}")
    if technical_prefilter_reason and technical_prefilter_status != "PASS":
        reasons.append(f"technical_prefilter_reason_{technical_prefilter_reason}")
    if shadow_level_status not in {"", "VALID", "NOT_AVAILABLE", "NOT_ELIGIBLE"}:
        reasons.append(f"shadow_level_status_{shadow_level_status.lower()}")
    if blockers:
        reasons.append("checklist_blockers_present")
    if entry is None or stop is None or target is None:
        reasons.append("missing_operational_levels")
    if rr is None or rr < min_rr:
        reasons.append("rr_invalid_or_below_minimum")

    if reasons:
        return "NOT_BUY_NOW", "; ".join(dict.fromkeys(reasons)), False
    return "BUY_NOW", "strict_automatic_posttest_memory_only", True


def _empty_output_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def resolve_default_input(root: Path = ROOT) -> Path:
    reports = root / "reports"
    top = reports / "manual_review_top.csv"
    latest = reports / "manual_review_latest.csv"
    return top if top.exists() else latest


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def enrich_candidates(input_df: pd.DataFrame, root: Path = ROOT) -> pd.DataFrame:
    if input_df.empty or "ticker" not in input_df.columns:
        return input_df.copy()

    out = input_df.copy()
    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["_manual_order"] = range(len(out))

    for reference_path in [
        root / "reports" / "manual_review_latest.csv",
        root / "reports" / "latest_scan_audited.csv",
    ]:
        ref = _load_csv(reference_path)
        if ref.empty or "ticker" not in ref.columns:
            continue

        ref = ref.copy()
        ref["ticker"] = ref["ticker"].astype(str).str.upper().str.strip()
        ref = ref.drop_duplicates(subset=["ticker"], keep="first")

        extra_cols = [col for col in ref.columns if col != "ticker"]
        merged = out.merge(
            ref[["ticker", *extra_cols]],
            on="ticker",
            how="left",
            suffixes=("", "_ref"),
        )

        for col in extra_cols:
            ref_col = f"{col}_ref"
            if ref_col not in merged.columns:
                continue

            if col not in out.columns:
                merged[col] = merged[ref_col]
            else:
                merged[col] = merged[col].astype(object)
                missing = merged[col].apply(_safe_text).eq("")
                merged.loc[missing, col] = merged.loc[missing, ref_col]

            merged = merged.drop(columns=[ref_col])

        out = merged

    return out.sort_values("_manual_order").drop(columns=["_manual_order"], errors="ignore")


def evaluate_checklist_row(
    row: dict,
    *,
    min_price: float = 10.0,
    min_market_cap: float = 2_500_000_000,
    min_rr: float = 1.5,
    high_quality_score: float = 85.0,
) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []
    required_actions: list[str] = []

    signal = _safe_text(row.get("signal")).upper()
    recommendation = _safe_text(row.get("recommendation")).upper()
    setup_type = _safe_text(row.get("setup_type")).upper()
    quote_status = _safe_text(row.get("quote_status")).upper() or "MISSING"
    execution_quality = _safe_text(row.get("execution_quote_quality")).upper() or "LOW"
    stop_atr_status = _safe_text(row.get("stop_atr_status")).upper()
    scenario_status = _safe_text(row.get("scenario_status")).upper()
    scenario_eligible_text = _safe_text(row.get("scenario_eligible_for_backtest"))
    shadow_level_status = _safe_text(row.get("shadow_level_status")).upper()
    execution_readiness = _safe_text(row.get("execution_readiness_status")).upper()
    engine_block_reason = _safe_text(row.get("engine_block_reason"))
    entry_timing_status = _safe_text(row.get("entry_timing_status")).upper()
    ema20_extension_status = _safe_text(row.get("ema20_extension_status")).upper()
    macd_histogram_state = _safe_text(row.get("macd_histogram_state")).upper()
    weekly_macd_histogram_state = _safe_text(row.get("weekly_macd_histogram_state")).upper()
    sector_weekly_macd_state = _safe_text(row.get("sector_weekly_macd_state")).upper()
    sector_context_reason = _safe_text(row.get("sector_context_reason"))
    technical_prefilter_status = _safe_text(row.get("technical_prefilter_status")).upper()
    technical_prefilter_reason = _safe_text(row.get("technical_prefilter_reason"))

    entry = _safe_float(_first_value(row, ["actionable_entry", "entry"]))
    stop = _safe_float(_first_value(row, ["actionable_stop", "stop"]))
    target = _safe_float(_first_value(row, ["actionable_target", "target"]))
    rr = _safe_float(row.get("rr"))
    price = _safe_float(_first_value(row, ["price", "current_price", "close"]))
    market_cap = _safe_float(row.get("market_cap"))

    if signal == "VETO":
        _append_unique(blockers, "signal_veto")
    if signal == "AVOID":
        _append_unique(blockers, "signal_avoid")
    if technical_prefilter_status and technical_prefilter_status != "PASS":
        _append_unique(blockers, f"technical_prefilter_{technical_prefilter_status.lower()}")
        if technical_prefilter_reason:
            _append_unique(blockers, f"technical_prefilter_reason_{technical_prefilter_reason}")
    if setup_type in {"", "NO_VALID_SETUP"}:
        _append_unique(blockers, "no_valid_setup")

    if scenario_status and scenario_status != "VALID_TRIGGER":
        _append_unique(blockers, f"scenario_not_operable_{scenario_status.lower()}")
    if scenario_eligible_text and not _bool(row.get("scenario_eligible_for_backtest")):
        _append_unique(blockers, "scenario_not_eligible_for_backtest")
    if engine_block_reason:
        _append_unique(blockers, f"engine_block_{engine_block_reason.replace('; ', '_')}")

    required_confirmation = _safe_text(row.get("required_confirmation"))
    if required_confirmation:
        _append_unique(required_actions, required_confirmation)

    if shadow_level_status and shadow_level_status not in {
        "VALID",
        "NOT_AVAILABLE",
        "NOT_ELIGIBLE",
    }:
        _append_unique(warnings, f"shadow_level_status_{shadow_level_status.lower()}")

    if entry_timing_status in {"CAUTION", "OVEREXTENDED", "LATE_ENTRY"}:
        _append_unique(warnings, f"entry_timing_status_{entry_timing_status.lower()}")
    if ema20_extension_status in {"CAUTION", "OVEREXTENDED", "LATE_ENTRY"}:
        _append_unique(warnings, f"ema20_extension_status_{ema20_extension_status.lower()}")
    if macd_histogram_state == "MACD_HIST_DETERIORATING":
        _append_unique(warnings, "macd_histogram_deteriorating")
    if weekly_macd_histogram_state in {"WEEKLY_MACD_HIST_BEARISH", "WEEKLY_MACD_HIST_DECELERATING"}:
        _append_unique(blockers, f"weekly_macd_histogram_{weekly_macd_histogram_state.lower()}")
    elif weekly_macd_histogram_state and weekly_macd_histogram_state != "WEEKLY_MACD_HIST_IMPROVING":
        _append_unique(warnings, f"weekly_macd_histogram_{weekly_macd_histogram_state.lower()}")
    if sector_weekly_macd_state in {"SECTOR_MACD_BEARISH", "SECTOR_MACD_DECELERATING"}:
        _append_unique(blockers, f"sector_weekly_macd_{sector_weekly_macd_state.lower()}")
    elif sector_weekly_macd_state in {
        "SECTOR_MACD_IMPROVING_BUT_DECELERATING",
        "SECTOR_MACD_MIXED",
        "SECTOR_MACD_UNKNOWN",
    }:
        _append_unique(warnings, f"sector_weekly_macd_{sector_weekly_macd_state.lower()}")
        if sector_context_reason:
            _append_unique(required_actions, f"monitor_sector_context_{sector_context_reason}")

    if price is not None and price < min_price:
        _append_unique(blockers, "price_below_minimum")

    quote_type = _safe_text(row.get("quote_type")).upper()
    if market_cap is not None and quote_type in {"", "EQUITY", "STOCK"} and market_cap < min_market_cap:
        _append_unique(blockers, "market_cap_below_minimum")

    if "liquidity_pass" in row and _safe_text(row.get("liquidity_pass")) and not _bool(row.get("liquidity_pass")):
        _append_unique(blockers, "liquidity_fail")

    if entry is None or stop is None or target is None:
        _append_unique(blockers, "missing_actionable_entry_stop_or_target")

    if rr is None or rr < min_rr:
        _append_unique(blockers, "rr_invalid_or_below_minimum")

    if quote_status != "VALID":
        _append_unique(required_actions, "review_live_quote_recheck_latest")
        _append_unique(warnings, f"quote_status_{quote_status.lower()}")

    if execution_quality != "HIGH":
        _append_unique(required_actions, "review_live_quote_recheck_latest")
        _append_unique(warnings, f"execution_quote_quality_{execution_quality.lower()}")

    if recommendation == "RECHECK_LIVE_QUOTE":
        _append_unique(required_actions, "review_live_quote_recheck_latest")
    if execution_readiness == "NEEDS_LIVE_QUOTE_RECHECK":
        _append_unique(required_actions, "review_live_quote_recheck_latest")
    elif execution_readiness in {"EXECUTION_DATA_BLOCKED", "NOT_OPERABLE"}:
        _append_unique(blockers, f"execution_readiness_{execution_readiness.lower()}")

    spread_pct = _safe_float(_first_value(row, ["spread_validated_pct", "spread_pct"]))
    if spread_pct is None and quote_status == "VALID":
        _append_unique(warnings, "spread_unknown")
    elif spread_pct is not None and spread_pct > 0.03:
        _append_unique(warnings, "spread_high")

    rsi = _safe_float(_first_value(row, ["rsi", "rsi_14", "RSI"]))
    if rsi is not None and rsi > 75:
        _append_unique(warnings, "rsi_overextended")

    if stop_atr_status == "BELOW_HARD_MIN":
        _append_unique(blockers, "stop_too_tight_below_hard_min")
    elif stop_atr_status in {"AGGRESSIVE_TIGHT", "WIDE"}:
        _append_unique(warnings, f"stop_atr_status_{stop_atr_status.lower()}")

    if price is not None and entry is not None and entry > 0:
        distance = abs(price - entry) / entry
        if distance > 0.08:
            _append_unique(warnings, "price_far_from_actionable_entry")

    days_to_earnings = _safe_float(row.get("days_to_earnings"))
    if _bool(row.get("earnings_veto")):
        _append_unique(blockers, "earnings_too_close")
    elif days_to_earnings is not None and 0 <= days_to_earnings <= 10:
        _append_unique(warnings, "earnings_near")

    base_score = _safe_float(row.get("final_trade_score"), 0.0) or 0.0
    readiness_score = _safe_float(row.get("operational_readiness_score"))
    checklist_score = base_score
    if readiness_score is not None:
        checklist_score = min(checklist_score, readiness_score)
    checklist_score -= 25 * len(blockers)
    checklist_score -= 7 * len([a for a in required_actions if a == "review_live_quote_recheck_latest"])
    checklist_score -= 2 * len(warnings)
    checklist_score = max(0.0, min(100.0, round(checklist_score, 2)))

    if blockers:
        status = "BLOCKED"
    elif (
        quote_status != "VALID"
        or execution_quality != "HIGH"
        or recommendation == "RECHECK_LIVE_QUOTE"
    ):
        status = "NEEDS_LIVE_QUOTE_RECHECK"
    elif (
        signal in {"WATCHLIST", "TRIGGER_CONFIRMED"}
        and (not scenario_status or scenario_status == "VALID_TRIGGER")
        and (not scenario_eligible_text or _bool(row.get("scenario_eligible_for_backtest")))
        and (not execution_readiness or execution_readiness == "EXECUTION_READY_REVIEW")
        and entry_timing_status in {"", "ON_TIME"}
        and ema20_extension_status in {"", "HEALTHY"}
        and macd_histogram_state not in {"MACD_HIST_DETERIORATING", "MACD_HIST_FLATTENING"}
        and weekly_macd_histogram_state == "WEEKLY_MACD_HIST_IMPROVING"
        and sector_weekly_macd_state in {"", "SECTOR_MACD_ACCELERATING", "SECTOR_MACD_IMPROVING"}
        and shadow_level_status in {"", "VALID", "NOT_AVAILABLE", "NOT_ELIGIBLE"}
        and checklist_score >= high_quality_score
    ):
        status = "HIGH_QUALITY_REVIEW"
    else:
        status = "REVIEW_MANUALLY"

    manual_note = (
        "Revision manual obligatoria; HIGH_QUALITY_REVIEW no equivale a compra automatica."
        if status == "HIGH_QUALITY_REVIEW"
        else "Revision manual obligatoria antes de cualquier operacion."
    )
    posttest_status, posttest_reason, buy_now_candidate = _derive_automatic_posttest_status(
        status=status,
        signal=signal,
        quote_status=quote_status,
        execution_quality=execution_quality,
        recommendation=recommendation,
        scenario_status=scenario_status,
        scenario_eligible_text=scenario_eligible_text,
        scenario_eligible=_bool(row.get("scenario_eligible_for_backtest")),
        execution_readiness=execution_readiness,
        entry_timing_status=entry_timing_status,
        ema20_extension_status=ema20_extension_status,
        macd_histogram_state=macd_histogram_state,
        weekly_macd_histogram_state=weekly_macd_histogram_state,
        sector_weekly_macd_state=sector_weekly_macd_state,
        technical_prefilter_status=technical_prefilter_status,
        technical_prefilter_reason=technical_prefilter_reason,
        shadow_level_status=shadow_level_status,
        blockers=blockers,
        entry=entry,
        stop=stop,
        target=target,
        rr=rr,
        min_rr=min_rr,
    )

    return {
        "checklist_status": status,
        "checklist_score": checklist_score,
        "checklist_required_actions": _join(required_actions),
        "checklist_blockers": _join(blockers),
        "checklist_warnings": _join(warnings),
        "automatic_posttest_status": posttest_status,
        "automatic_posttest_reason": posttest_reason,
        "buy_now_candidate": buy_now_candidate,
        "manual_decision_note": manual_note,
    }


def build_trade_decision_checklist_dataframe(
    input_df: pd.DataFrame,
    *,
    root: Path = ROOT,
    min_price: float = 10.0,
    min_market_cap: float = 2_500_000_000,
    min_rr: float = 1.5,
    high_quality_score: float = 85.0,
) -> pd.DataFrame:
    if input_df.empty:
        return _empty_output_dataframe()

    enriched = enrich_candidates(input_df, root=root)
    rows: list[dict] = []

    for _, item in enriched.iterrows():
        original = item.to_dict()
        checklist = evaluate_checklist_row(
            original,
            min_price=min_price,
            min_market_cap=min_market_cap,
            min_rr=min_rr,
            high_quality_score=high_quality_score,
        )

        out = dict(original)
        out.update(checklist)
        out["actionable_entry"] = _first_value(out, ["actionable_entry", "entry"])
        out["actionable_stop"] = _first_value(out, ["actionable_stop", "stop"])
        out["actionable_target"] = _first_value(out, ["actionable_target", "target"])
        out["next_earnings_date"] = _first_value(out, ["next_earnings_date", "earnings_date"])
        rows.append(out)

    out_df = pd.DataFrame(rows)

    for col in OUTPUT_COLUMNS:
        if col not in out_df.columns:
            out_df[col] = ""

    return out_df[OUTPUT_COLUMNS].copy()


def build_trade_decision_checklist_markdown(df: pd.DataFrame, status: str = "PASS") -> str:
    lines: list[str] = []
    lines.append("# Analista - trade decision checklist")
    lines.append("")
    lines.append("- Revision manual final. No genera senales, compras ni TRIGGER_CONFIRMED.")
    lines.append(f"- status: {status}")
    lines.append(f"- rows: {int(len(df))}")
    lines.append("")

    counts = df["checklist_status"].value_counts().to_dict() if not df.empty else {}
    lines.append("## Summary")
    lines.append("")
    for key in ["BLOCKED", "NEEDS_LIVE_QUOTE_RECHECK", "REVIEW_MANUALLY", "HIGH_QUALITY_REVIEW"]:
        lines.append(f"- {key.lower()}: {int(counts.get(key, 0))}")
    lines.append("")

    if df.empty:
        lines.append("_Sin candidatos para checklist._")
        return "\n".join(lines)

    table_cols = [
        "ticker",
        "signal",
        "recommendation",
        "final_trade_score",
        "checklist_status",
        "checklist_score",
        "checklist_blockers",
        "checklist_warnings",
        "checklist_required_actions",
        "automatic_posttest_status",
    ]

    lines.append("## Candidates")
    lines.append("")
    lines.append("| " + " | ".join(table_cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(table_cols)) + " |")
    for _, row in df.iterrows():
        values = []
        for col in table_cols:
            value = row.get(col, "")
            if pd.isna(value):
                value = ""
            values.append(str(value).replace("\n", " ").replace("|", "/"))
        lines.append("| " + " | ".join(values) + " |")

    lines.append("")
    lines.append("## Reminder")
    lines.append("")
    lines.append("- VETO y AVOID no son operables.")
    lines.append("- RECHECK_LIVE_QUOTE requiere validar reportes live antes de cualquier decision.")
    lines.append("- HIGH_QUALITY_REVIEW no equivale a compra automatica.")
    lines.append("- Opciones son contexto, no gatillo de entrada.")
    lines.append("- BUY_NOW, si aparece, es memoria automatica de posttest; no es orden real.")

    return "\n".join(lines)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_trade_decision_checklist_reports(
    input_path: Path | None = None,
    *,
    csv_out: Path | None = None,
    markdown_out: Path | None = None,
    json_out: Path | None = None,
    root: Path = ROOT,
) -> dict:
    input_path = input_path or resolve_default_input(root)
    csv_out = csv_out or root / "reports" / "trade_decision_checklist_latest.csv"
    markdown_out = markdown_out or root / "reports" / "trade_decision_checklist_latest.md"
    json_out = json_out or root / "reports" / "trade_decision_checklist_latest.json"

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        out = _empty_output_dataframe()
        out.to_csv(csv_out, index=False)
        markdown_out.write_text(
            "# Analista - trade decision checklist\n\nStatus: FAIL\n\nInput no encontrado: "
            + str(input_path)
            + "\n",
            encoding="utf-8",
        )
        result = {
            "status": "FAIL",
            "rows": 0,
            "error": "input_csv_not_found",
            "input_path": str(input_path),
            "csv_out": str(csv_out),
            "markdown_out": str(markdown_out),
            "json_out": str(json_out),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(json_out, result)
        return result

    try:
        input_df = pd.read_csv(input_path)
    except Exception as exc:
        out = _empty_output_dataframe()
        out.to_csv(csv_out, index=False)
        markdown_out.write_text(build_trade_decision_checklist_markdown(out, status="FAIL"), encoding="utf-8")
        result = {
            "status": "FAIL",
            "rows": 0,
            "error": f"input_csv_read_failed:{exc}",
            "input_path": str(input_path),
            "csv_out": str(csv_out),
            "markdown_out": str(markdown_out),
            "json_out": str(json_out),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(json_out, result)
        return result

    out = build_trade_decision_checklist_dataframe(input_df, root=root)
    out.to_csv(csv_out, index=False)
    markdown_out.write_text(build_trade_decision_checklist_markdown(out, status="PASS"), encoding="utf-8")

    counts = out["checklist_status"].value_counts().to_dict() if not out.empty else {}
    result = {
        "status": "PASS",
        "rows": int(len(out)),
        "blocked": int(counts.get("BLOCKED", 0)),
        "needs_live_quote_recheck": int(counts.get("NEEDS_LIVE_QUOTE_RECHECK", 0)),
        "review_manually": int(counts.get("REVIEW_MANUALLY", 0)),
        "high_quality_review": int(counts.get("HIGH_QUALITY_REVIEW", 0)),
        "input_path": str(input_path),
        "csv_out": str(csv_out),
        "markdown_out": str(markdown_out),
        "json_out": str(json_out),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(json_out, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera checklist operativo final por candidato.")
    parser.add_argument("--input-path", default=None)
    parser.add_argument("--csv-out", default="reports/trade_decision_checklist_latest.csv")
    parser.add_argument("--markdown-out", default="reports/trade_decision_checklist_latest.md")
    parser.add_argument("--json-out", default="reports/trade_decision_checklist_latest.json")
    args = parser.parse_args()

    result = save_trade_decision_checklist_reports(
        input_path=ROOT / args.input_path if args.input_path else None,
        csv_out=ROOT / args.csv_out,
        markdown_out=ROOT / args.markdown_out,
        json_out=ROOT / args.json_out,
        root=ROOT,
    )

    print("=== ANALISTA TRADE DECISION CHECKLIST ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result['rows']}")
    print(f"Blocked: {result.get('blocked', 0)}")
    print(f"Needs live quote recheck: {result.get('needs_live_quote_recheck', 0)}")
    print(f"Review manually: {result.get('review_manually', 0)}")
    print(f"High quality review: {result.get('high_quality_review', 0)}")
    print(f"CSV: {result['csv_out']}")
    print(f"Markdown: {result['markdown_out']}")
    print(f"JSON: {result['json_out']}")
    if result.get("error"):
        print(f"Error: {result['error']}")

    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
