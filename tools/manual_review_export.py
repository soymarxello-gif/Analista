from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.report_engine import recommendation_for_row


MANUAL_REVIEW_COLUMNS = [
    "rank",
    "ticker",
    "signal",
    "recommendation",
    "manual_quote_check_required",
    "quote_recheck_priority",
    "quote_recheck_reason",
    "operational_readiness_score",
    "operational_readiness_bucket",
    "asset_attractiveness_score",
    "timing_quality_score",
    "momentum_confirmation_score",
    "scenario_quality_adjustment",
    "timing_penalty_reason",
    "momentum_penalty_reason",
    "engine_block_reason",
    "execution_readiness_status",
    "operational_status",
    "sector_leadership_override_status",
    "sector_headwind_strength",
    "operational_readiness_reason",
    "technical_opportunity_score",
    "decision_lane",
    "decision_reasons",
    "technical_asset_quality_score",
    "entry_readiness_score",
    "research_priority_score",
    "reset_watch_score",
    "context_confidence_score",
    "data_confidence_score",
    "technical_analysis_lane",
    "deep_analysis_tier",
    "operational_eligibility",
    "research_eligibility_reason",
    "setup_readiness_score",
    "setup_readiness_state",
    "setup_candidate_type",
    "primary_setup_hypothesis",
    "primary_setup_hypothesis_state",
    "primary_setup_hypothesis_score",
    "alternative_setup_hypotheses",
    "setup_hypothesis_count",
    "technical_eligibility_reason",
    "trend_setup_compatibility",
    "trend_setup_compatibility_reason",
    "research_trend_compatibility",
    "research_trend_compatibility_reason",
    "momentum_gate_status",
    "timing_gate_status",
    "core_liquidity_status",
    "daily_macd_operable",
    "weekly_macd_operable",
    "technical_assessment_version",
    "technical_prefilter_status",
    "technical_prefilter_reason",
    "technical_prefilter_triage",
    "daily_macd_prefilter_status",
    "weekly_macd_prefilter_status",
    "ema20_extension_prefilter_status",
    "ema20_extension_reference_source",
    "final_trade_score",
    "setup_quality_score",
    "final_score",
    "setup_type",
    "entry",
    "stop",
    "target",
    "actionable_entry",
    "actionable_stop",
    "actionable_target",
    "rr",
    "rr_status",
    "rr_stressed",
    "risk_geometry_status",
    "risk_geometry_reason",
    "rr_confidence",
    "target_validation_source",
    "target_validation_sources",
    "target_candidates",
    "entry_zone_low",
    "entry_zone_high",
    "technical_as_of_date",
    "technical_bar_policy",
    "daily_bar_complete",
    "weekly_bar_complete",
    "intraday_bar_excluded",
    "stop_atr_multiple",
    "stop_atr_status",
    "market_opportunity_status",
    "sector_relative_return_20d",
    "sector_relative_return_60d",
    "sector_relative_line_slope_20d",
    "sector_relative_strength_score",
    "sector_relative_leadership_status",
    "quote_status",
    "execution_quote_quality",
    "execution_spread_status",
    "options_bias",
    "options_confidence",
    "options_scoring_status",
    "sector",
    "industry",
    "earnings_date",
    "days_to_earnings",
    "earnings_as_of_date",
    "earnings_event_status",
    "earnings_data_confidence",
    "earnings_days_recomputed",
    "earnings_refresh_required",
    "earnings_operability_block",
    "earnings_review_reason",
    "earnings_consistency_status",
    "penalty_reasons",
    "all_veto_reasons",
    "reason_summary",
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
    "daily_macd_trajectory_state",
    "daily_macd_trajectory_confidence",
    "daily_macd_hist_slope",
    "daily_macd_hist_acceleration",
    "daily_macd_non_decelerating",
    "weekly_macd_trajectory_state",
    "weekly_macd_trajectory_confidence",
    "weekly_macd_hist_slope",
    "weekly_macd_hist_acceleration",
    "weekly_macd_non_decelerating",
    "momentum_alignment",
    "momentum_alignment_confidence",
    "momentum_acceleration_score",
    "momentum_persistence_score",
    "momentum_operability_status",
    "weekly_macd_hist_improving",
    "weekly_macd_hist",
    "weekly_macd_hist_change_1w",
    "weekly_macd_hist_change_2w",
    "ema20_extension_risk",
    "ema20_extension_confidence",
    "ema20_extension_driver",
    "ema20_distance_percentile_1y",
    "ema20_extension_model",
    "trend_transition_score",
    "trend_transition_state",
    "trend_transition_reason",
    "entry_chase_risk",
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
    "required_confirmations",
    "invalidation_conditions",
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
]


REVIEW_GROUP_ORDER = {
    "TRIGGER_CONFIRMED": 0,
    "RECHECK_LIVE_QUOTE": 1,
    "READY_WAIT_TRIGGER": 2,
    "WATCHLIST_MONITOR": 3,
    "WATCHLIST": 4,
}


def _bool_series(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "y"})


def _review_group(row: dict) -> str:
    signal = str(row.get("signal") or "").upper().strip()
    recommendation = str(row.get("recommendation") or "").upper().strip()
    manual_quote = str(row.get("manual_quote_check_required") or "").lower().strip() in {
        "true",
        "1",
        "yes",
        "y",
    }

    if signal == "TRIGGER_CONFIRMED":
        return "TRIGGER_CONFIRMED"

    if manual_quote or recommendation == "RECHECK_LIVE_QUOTE":
        return "RECHECK_LIVE_QUOTE"

    if signal == "READY_WAIT_TRIGGER":
        return "READY_WAIT_TRIGGER"

    if recommendation == "WATCHLIST_MONITOR":
        return "WATCHLIST_MONITOR"

    if signal == "WATCHLIST":
        return "WATCHLIST"

    return "OTHER"


def build_manual_review_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()

    if "manual_quote_check_required" not in out.columns:
        out["manual_quote_check_required"] = False

    if "recommendation" not in out.columns:
        out["recommendation"] = ""
    else:
        out["recommendation"] = out["recommendation"].fillna("").astype(str)

    missing_recommendation = out["recommendation"].str.strip().eq("")
    if missing_recommendation.any():
        out.loc[missing_recommendation, "recommendation"] = out.loc[
            missing_recommendation
        ].apply(lambda row: recommendation_for_row(row.to_dict()), axis=1)

    out["_review_group"] = out.apply(lambda row: _review_group(row.to_dict()), axis=1)

    keep_groups = {
        "TRIGGER_CONFIRMED",
        "RECHECK_LIVE_QUOTE",
        "READY_WAIT_TRIGGER",
        "WATCHLIST_MONITOR",
        "WATCHLIST",
    }

    out = out[out["_review_group"].isin(keep_groups)].copy()

    if out.empty:
        return out

    out["_review_group_order"] = out["_review_group"].map(REVIEW_GROUP_ORDER).fillna(99).astype(int)

    sort_cols = [
        "_review_group_order",
        "rank",
        "final_trade_score",
        "setup_quality_score",
    ]
    sort_cols = [c for c in sort_cols if c in out.columns]

    ascending = []
    for col in sort_cols:
        if col in {"final_trade_score", "setup_quality_score"}:
            ascending.append(False)
        else:
            ascending.append(True)

    out = out.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)

    cols = ["_review_group"] + [c for c in MANUAL_REVIEW_COLUMNS if c in out.columns]

    return out[cols]


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin candidatos para revisión manual._\n"

    headers = list(df.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in df.iterrows():
        values = []
        for col in headers:
            value = row.get(col, "")
            if pd.isna(value):
                value = ""
            text = str(value).replace("\n", " ").replace("|", "/")
            values.append(text)
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines) + "\n"


def save_manual_review_reports(
    df: pd.DataFrame,
    csv_out: Path,
    markdown_out: Path,
) -> None:
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    review_df = build_manual_review_dataframe(df)

    review_df.to_csv(csv_out, index=False)

    sections = []
    sections.append("# Analista — revisión manual diaria\n")

    if review_df.empty:
        sections.append("_Sin candidatos para revisión manual._\n")
    else:
        for group, group_df in review_df.groupby("_review_group", sort=False):
            sections.append(f"\n## {group}\n")
            display_df = group_df.drop(columns=["_review_group"], errors="ignore")
            sections.append(_df_to_markdown_table(display_df))

    markdown_out.write_text("\n".join(sections), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta reporte operativo de revisión manual.")
    parser.add_argument("--csv", default="reports/latest_scan_audited.csv")
    parser.add_argument("--csv-out", default="reports/manual_review_latest.csv")
    parser.add_argument("--markdown-out", default="reports/manual_review_latest.md")
    args = parser.parse_args()

    csv_path = ROOT / args.csv
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe CSV: {csv_path}")

    df = pd.read_csv(csv_path)

    save_manual_review_reports(
        df,
        csv_out=ROOT / args.csv_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print(f"CSV escrito en: {ROOT / args.csv_out}")
    print(f"Markdown escrito en: {ROOT / args.markdown_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
