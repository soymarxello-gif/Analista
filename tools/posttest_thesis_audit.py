from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _bool_series(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.strip().str.lower().isin(
        {"true", "1", "yes", "y"}
    )


def _scan_order_series(data: pd.DataFrame) -> pd.Series:
    if "scan_timestamp" in data.columns:
        scan_order = pd.to_datetime(data["scan_timestamp"], errors="coerce", utc=True)
    else:
        scan_order = pd.Series(pd.NaT, index=data.index, dtype="datetime64[ns, UTC]")

    if "_source_file" in data.columns:
        missing = scan_order.isna()
        extracted = data.loc[missing, "_source_file"].astype(str).str.extract(
            r"(\d{8})_(\d{6})",
            expand=False,
        )
        if not extracted.empty:
            fallback_order = pd.to_datetime(
                extracted[0] + extracted[1],
                format="%Y%m%d%H%M%S",
                errors="coerce",
                utc=True,
            )
            scan_order.loc[missing] = fallback_order
    return scan_order


def _load_posttests(patterns: list[str]) -> pd.DataFrame:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(Path(path) for path in glob.glob(pattern, recursive=True))
    frames = []
    for path in sorted(set(files)):
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if not frame.empty:
            frame["_source_file"] = path.name
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def deduplicate_first_operable_daily(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty or not {"ticker", "scan_date"}.issubset(data.columns):
        return data.copy()
    out = data.copy()
    out["_scan_order"] = _scan_order_series(out)
    out = out.sort_values(["scan_date", "ticker", "_scan_order"], na_position="last")
    out = out.drop_duplicates(["scan_date", "ticker"], keep="first")
    return out.drop(columns=["_scan_order"], errors="ignore").reset_index(drop=True)


def select_canonical_daily_top_five(data: pd.DataFrame) -> pd.DataFrame:
    """Select the latest represented scan per day and at most its five valid ranks."""
    if data.empty or "scan_date" not in data.columns:
        return data.copy()

    out = data.copy()
    out["_scan_order"] = _scan_order_series(out)
    if "_source_file" in out.columns:
        out["_run_id"] = out["_source_file"].fillna("").astype(str)
    elif "scan_timestamp" in out.columns:
        out["_run_id"] = out["scan_timestamp"].fillna("").astype(str)
    else:
        out["_run_id"] = "LEGACY_SINGLE_RUN"

    selected: list[pd.DataFrame] = []
    for _, daily in out.groupby("scan_date", sort=True, dropna=False):
        run_order = (
            daily.groupby("_run_id", dropna=False)["_scan_order"]
            .max()
            .reset_index()
            .sort_values(["_scan_order", "_run_id"], na_position="first")
        )
        latest_run_id = run_order.iloc[-1]["_run_id"]
        canonical = daily[daily["_run_id"] == latest_run_id].copy()

        if "scenario_eligible_for_backtest" in canonical.columns:
            declared = canonical["scenario_eligible_for_backtest"].notna()
            if declared.any():
                canonical = canonical[_bool_series(canonical["scenario_eligible_for_backtest"])]
        elif "scenario_status" in canonical.columns:
            statuses = canonical["scenario_status"].fillna("").astype(str).str.upper()
            if statuses.ne("").any():
                canonical = canonical[statuses.eq("VALID_TRIGGER")]

        ranks = pd.to_numeric(
            canonical.get(
                "backtest_selection_rank",
                pd.Series(index=canonical.index, dtype=float),
            ),
            errors="coerce",
        )
        if ranks.notna().any():
            canonical = canonical[ranks.between(1, 5)].copy()
            canonical["_canonical_rank"] = ranks.loc[canonical.index]
            canonical = canonical.sort_values(["_canonical_rank", "ticker"])
        else:
            canonical["_canonical_score"] = pd.to_numeric(
                canonical.get(
                    "final_trade_score",
                    pd.Series(index=canonical.index, dtype=float),
                ),
                errors="coerce",
            )
            sort_columns = ["_canonical_score"]
            ascending = [False]
            if "ticker" in canonical.columns:
                sort_columns.append("ticker")
                ascending.append(True)
            canonical = canonical.sort_values(
                sort_columns,
                ascending=ascending,
                na_position="last",
            ).head(5)

        selected.append(canonical)

    if not selected:
        return out.iloc[0:0].drop(
            columns=["_scan_order", "_run_id", "_canonical_rank", "_canonical_score"],
            errors="ignore",
        )

    return (
        pd.concat(selected, ignore_index=True)
        .drop(
            columns=["_scan_order", "_run_id", "_canonical_rank", "_canonical_score"],
            errors="ignore",
        )
        .reset_index(drop=True)
    )


def _metric_summary(data: pd.DataFrame) -> dict:
    if data.empty:
        return {
            "evaluated_rows": 0,
            "published_evaluated_rows": 0,
            "executed_entries": 0,
            "no_entry_triggers": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
            "target_hit_rate": None,
            "stop_hit_rate": None,
            "avg_return_4d_pct": None,
            "avg_realized_r_4d": None,
            "entry_trigger_rate": None,
            "ambiguous_sequence_rate": None,
            "avg_calculated_rr": None,
            "avg_abs_rr_error": None,
            "rr_match_rate": None,
            "profitable_at_4d_rate": None,
            "execution_win_rate": None,
            "avg_execution_return_4d_pct": None,
            "shadow_evaluated_rows": 0,
            "shadow_win_rate": None,
            "avg_shadow_return_4d_pct": None,
            "avg_target_capture_ratio": None,
            "avg_stop_buffer_ratio": None,
            "breakeven": 0,
            "median_return_4d_pct": None,
            "avg_winner_return_4d_pct": None,
            "avg_loser_return_4d_pct": None,
            "payoff_ratio": None,
            "profit_factor": None,
            "expectancy_4d_pct": None,
            "best_trade_return_4d_pct": None,
            "worst_trade_return_4d_pct": None,
        }
    outcome = data.get("level_outcome", pd.Series("", index=data.index)).fillna("").astype(str)
    if "execution_entry_reached" in data.columns:
        execution_reached = (
            data["execution_entry_reached"].astype(str).str.lower().isin({"true", "1", "yes"})
        )
    else:
        execution_reached = outcome != "NO_ENTRY_TRIGGER"
    executed = data[execution_reached]
    target_success = (
        data["target_success"].astype(str).str.lower().eq("true")
        if "target_success" in data.columns
        else data.get("level_outcome", pd.Series("", index=data.index))
        .fillna("")
        .astype(str)
        .eq("TARGET_HIT")
    )
    published_returns = pd.to_numeric(
        data.get("published_return_4d_pct", data.get("return_close_pct")),
        errors="coerce",
    )
    published_mask = published_returns.notna()
    profitable_values = data.get(
        "published_profitable_4d",
        data.get("profitable_at_4d", published_returns > 0),
    )
    profitable = (
        profitable_values.loc[published_mask]
        .astype(str)
        .str.lower()
        .eq("true")
    )
    execution_profitable = executed.get(
        "execution_profitable_at_4d",
        pd.to_numeric(
            executed.get("execution_return_close_pct", pd.Series(index=executed.index, dtype=float)),
            errors="coerce",
        )
        > 0,
    ).astype(str).str.lower().eq("true")
    shadow_returns = pd.to_numeric(
        data.get("shadow_return_close_pct", pd.Series(index=data.index, dtype=float)),
        errors="coerce",
    )
    shadow_profitable = shadow_returns.dropna() > 0
    evaluated = len(data)
    ambiguous = outcome.eq("BOTH_HIT_DAILY_UNKNOWN_SEQUENCE")
    calculated_rr = pd.to_numeric(
        data.get("calculated_rr", pd.Series(index=data.index, dtype=float)),
        errors="coerce",
    )
    rr_error = pd.to_numeric(
        data.get("rr_error", pd.Series(index=data.index, dtype=float)),
        errors="coerce",
    )
    rr_match_raw = data.get(
        "rr_matches_source",
        pd.Series(index=data.index, dtype=object),
    )
    rr_match = (
        rr_match_raw.loc[rr_match_raw.notna()]
        .astype(str)
        .str.lower()
        .eq("true")
    )
    target_capture = pd.to_numeric(
        data.get("target_capture_ratio", pd.Series(index=data.index, dtype=float)),
        errors="coerce",
    )
    stop_buffer = pd.to_numeric(
        data.get("stop_buffer_ratio", pd.Series(index=data.index, dtype=float)),
        errors="coerce",
    )
    valid_returns = published_returns.dropna()
    winner_returns = valid_returns[valid_returns > 0]
    loser_returns = valid_returns[valid_returns < 0]
    breakeven_returns = valid_returns[valid_returns == 0]
    avg_winner = float(winner_returns.mean()) if len(winner_returns) else None
    avg_loser = float(loser_returns.mean()) if len(loser_returns) else None
    payoff_ratio = (
        avg_winner / abs(avg_loser)
        if avg_winner is not None and avg_loser not in {None, 0}
        else None
    )
    gross_profit = float(winner_returns.sum()) if len(winner_returns) else 0.0
    gross_loss = abs(float(loser_returns.sum())) if len(loser_returns) else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    return {
        "evaluated_rows": int(len(data)),
        "published_evaluated_rows": int(published_mask.sum()),
        "executed_entries": int(len(executed)),
        "no_entry_triggers": int((~execution_reached).sum()),
        "wins": int(profitable.sum()),
        "losses": int((~profitable).sum()),
        "win_rate": round(float(profitable.mean()), 6) if len(profitable) else None,
        "target_wins": int(target_success.sum()),
        "target_success_rate": round(float(target_success.mean()), 6)
        if len(target_success)
        else None,
        "target_hit_rate": round(
            float(
                pd.to_numeric(
                    data.get(
                        "hit_target",
                        outcome.eq("TARGET_HIT"),
                    ),
                    errors="coerce",
                ).mean()
            ),
            6,
        )
        if len(data)
        else None,
        "stop_hit_rate": round(
            float(
                pd.to_numeric(
                    data.get(
                        "hit_stop",
                        outcome.isin(
                            {"STOP_HIT", "BOTH_HIT_DAILY_UNKNOWN_SEQUENCE"}
                        ),
                    ),
                    errors="coerce",
                ).mean()
            ),
            6,
        )
        if len(data)
        else None,
        "avg_return_4d_pct": round(float(published_returns.mean()), 6)
        if published_mask.any()
        else None,
        "avg_realized_r_4d": round(float(pd.to_numeric(executed.get("realized_r_at_close"), errors="coerce").mean()), 6)
        if len(executed)
        else None,
        "entry_trigger_rate": round(float(len(executed) / evaluated), 6) if evaluated else None,
        "ambiguous_sequence_rate": round(float(ambiguous.mean()), 6) if evaluated else None,
        "avg_calculated_rr": round(float(calculated_rr.mean()), 6) if calculated_rr.notna().any() else None,
        "avg_abs_rr_error": round(float(rr_error.abs().mean()), 6) if rr_error.notna().any() else None,
        "rr_match_rate": round(float(rr_match.mean()), 6) if len(rr_match) else None,
        "profitable_at_4d_rate": round(float(profitable.mean()), 6) if len(profitable) else None,
        "execution_win_rate": round(float(execution_profitable.mean()), 6)
        if len(execution_profitable)
        else None,
        "avg_execution_return_4d_pct": round(
            float(
                pd.to_numeric(
                    executed.get(
                        "execution_return_close_pct",
                        pd.Series(index=executed.index, dtype=float),
                    ),
                    errors="coerce",
                ).mean()
            ),
            6,
        )
        if len(executed)
        else None,
        "shadow_evaluated_rows": int(shadow_returns.notna().sum()),
        "shadow_win_rate": round(float(shadow_profitable.mean()), 6)
        if len(shadow_profitable)
        else None,
        "avg_shadow_return_4d_pct": round(float(shadow_returns.mean()), 6)
        if shadow_returns.notna().any()
        else None,
        "avg_target_capture_ratio": round(float(target_capture.mean()), 6)
        if target_capture.notna().any()
        else None,
        "avg_stop_buffer_ratio": round(float(stop_buffer.mean()), 6)
        if stop_buffer.notna().any()
        else None,
        "breakeven": int(len(breakeven_returns)),
        "median_return_4d_pct": round(float(valid_returns.median()), 6)
        if len(valid_returns)
        else None,
        "avg_winner_return_4d_pct": round(avg_winner, 6)
        if avg_winner is not None
        else None,
        "avg_loser_return_4d_pct": round(avg_loser, 6)
        if avg_loser is not None
        else None,
        "payoff_ratio": round(payoff_ratio, 6) if payoff_ratio is not None else None,
        "profit_factor": round(profit_factor, 6)
        if profit_factor is not None
        else None,
        "expectancy_4d_pct": round(float(valid_returns.mean()), 6)
        if len(valid_returns)
        else None,
        "best_trade_return_4d_pct": round(float(valid_returns.max()), 6)
        if len(valid_returns)
        else None,
        "worst_trade_return_4d_pct": round(float(valid_returns.min()), 6)
        if len(valid_returns)
        else None,
    }


def _group_table(data: pd.DataFrame, column: str, min_samples: int) -> list[dict]:
    if data.empty or column not in data.columns:
        return []
    rows = []
    for value, group in data.groupby(column, dropna=False):
        summary = _metric_summary(group)
        if summary["executed_entries"] < min_samples:
            continue
        rows.append({"group": column, "value": "MISSING" if pd.isna(value) else value, **summary})
    return sorted(rows, key=lambda row: (row.get("win_rate") or 0, row["executed_entries"]), reverse=True)


def build_thesis_audit(data: pd.DataFrame, *, min_samples: int = 3) -> dict:
    if data.empty:
        return {
            "status": "WARN",
            "summary": _metric_summary(data),
            "ticker_win_rates": [],
            "common_successes": [],
            "common_failures": [],
            "diagnostic_hints": ["No posttest data available."],
            "sample_size_warning": "sample too small",
            "automatic_changes_allowed": False,
        }

    if "horizon_days" in data.columns:
        data = data[pd.to_numeric(data["horizon_days"], errors="coerce") == 4].copy()
    input_rows_before_canonical_selection = len(data)
    per_run_summary = _metric_summary(data)
    data = select_canonical_daily_top_five(data)
    if "failure_class" not in data.columns:
        outcome = data.get("level_outcome", pd.Series("", index=data.index)).fillna("").astype(str)
        setup = data.get("setup_type", pd.Series("", index=data.index)).fillna("").astype(str).str.upper()
        returns = pd.to_numeric(
            data.get(
                "return_close_pct",
                pd.Series(index=data.index, dtype=float),
            ),
            errors="coerce",
        )
        failure_class = pd.Series("THESIS_NOT_COMPLETED", index=data.index, dtype=object)
        failure_class.loc[outcome.eq("TARGET_HIT")] = ""
        failure_class.loc[outcome.eq("NO_ENTRY_TRIGGER")] = "ENTRY_NOT_TRIGGERED"
        failure_class.loc[outcome.ne("TARGET_HIT") & returns.gt(0)] = "TARGET_TOO_AMBITIOUS"
        failure_class.loc[
            outcome.ne("TARGET_HIT") & returns.le(0) & setup.eq("BREAKOUT")
        ] = "FALSE_BREAKOUT"
        failure_class.loc[
            outcome.ne("TARGET_HIT") & returns.le(0) & setup.eq("PULLBACK")
        ] = "PULLBACK_CONFIRMATION_FAILURE"
        data["failure_class"] = failure_class
    summary = _metric_summary(data)
    summary["input_rows_before_daily_dedupe"] = input_rows_before_canonical_selection
    summary["input_rows_before_canonical_selection"] = input_rows_before_canonical_selection
    summary["deduplicated_rows"] = len(data)
    summary["canonical_rows"] = len(data)
    summary["canonical_dates"] = (
        int(data["scan_date"].nunique()) if "scan_date" in data.columns else 0
    )
    summary["max_candidates_per_canonical_day"] = (
        int(data.groupby("scan_date").size().max())
        if not data.empty and "scan_date" in data.columns
        else 0
    )
    group_columns = [
        "ticker",
        "setup_type",
        "score_bucket",
        "stop_atr_status",
        "options_bias",
        "options_confidence",
        "sector",
        "momentum_state",
        "extension_state",
        "scenario_status",
        "failure_class",
    ]
    tables = {column: _group_table(data, column, min_samples) for column in group_columns}
    all_groups = [row for column in group_columns[1:] for row in tables[column]]
    successes = [row for row in all_groups if (row.get("win_rate") or 0) >= 0.60][:10]
    failures = [row for row in reversed(all_groups) if (row.get("win_rate") or 0) <= 0.40][:10]

    hints: list[str] = []
    if summary["no_entry_triggers"] > summary["executed_entries"]:
        hints.append("Most proposed entries were not reached; review entry placement and setup timing.")
    if summary["stop_hit_rate"] is not None and summary["stop_hit_rate"] > 0.40:
        hints.append("Stop hit rate is high; review stop distance, ATR multiple and setup confirmation.")
    if summary["target_hit_rate"] is not None and summary["target_hit_rate"] < 0.25:
        hints.append("Target hit rate is low; review target distance and four-session realism.")
    if summary["entry_trigger_rate"] is not None and summary["entry_trigger_rate"] < 0.50:
        hints.append("Entry trigger rate is below 50%; proposed entries may be too distant or late.")
    if summary["rr_match_rate"] is not None and summary["rr_match_rate"] < 0.95:
        hints.append("Published R/R does not consistently match entry, stop and target arithmetic.")
    if summary["ambiguous_sequence_rate"] is not None and summary["ambiguous_sequence_rate"] > 0.10:
        hints.append("Daily bars often touch target and stop together; intraday data is needed for sequence accuracy.")
    if summary["win_rate"] is not None and summary["win_rate"] < 0.50:
        hints.append("Four-session profitable close rate is below 50%; inspect the weakest recurring groups.")
    failure_counts = (
        data.get("failure_class", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .replace("", "SUCCESS")
        .value_counts()
        .to_dict()
    )
    recommendation_map = {
        "LATE_ENTRY_FAILURE": "Add or tighten extension guards and avoid chasing entries far above trigger/support.",
        "WEAK_MOMENTUM_FAILURE": "Require improving RSI/MACD evidence before advancing the scenario.",
        "FALSE_BREAKOUT": "Require stronger breakout hold, volume confirmation and follow-through.",
        "PULLBACK_CONFIRMATION_FAILURE": "Do not confirm pullbacks without rejection/recovery evidence near support.",
        "STOP_TOO_TIGHT": "Review stops below one ATR and structural invalidation placement.",
        "TARGET_TOO_AMBITIOUS": "Review target distance against four-session MFE and nearby resistance.",
        "ENTRY_NOT_TRIGGERED": "Review whether proposed entries are too distant or no longer aligned with price.",
    }
    clear_recommendations = [
        {
            "failure_class": key,
            "count": int(value),
            "recommendation": recommendation_map[key],
        }
        for key, value in failure_counts.items()
        if key in recommendation_map and value > 0
    ]
    clear_recommendations.sort(key=lambda item: item["count"], reverse=True)
    if not hints:
        hints.append("No dominant structural failure detected; continue collecting out-of-sample scans.")

    sample_warning = "sample too small" if summary["executed_entries"] < 20 else ""
    return {
        "status": "WARN" if sample_warning else "PASS",
        "horizon_days": 4,
        "summary": summary,
        "per_run_summary": per_run_summary,
        "selection": {
            "mode": "LATEST_COMPLETE_RUN_PER_DAY_TOP_FIVE",
            "input_rows": input_rows_before_canonical_selection,
            "canonical_rows": int(len(data)),
            "canonical_dates": summary["canonical_dates"],
            "max_candidates_per_day": summary["max_candidates_per_canonical_day"],
        },
        "ticker_win_rates": tables["ticker"],
        "common_successes": successes,
        "common_failures": failures,
        "group_analysis": tables,
        "diagnostic_hints": hints,
        "failure_counts": failure_counts,
        "clear_recommendations": clear_recommendations,
        "sample_size_warning": sample_warning,
        "automatic_changes_allowed": False,
        "notice": "observational evidence only; no automatic scoring, threshold or signal changes",
    }


def build_markdown(report: dict) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Analista - 4-day trading thesis audit",
        "",
        f"- status: {report.get('status')}",
        f"- horizon_days: {report.get('horizon_days', 4)}",
        f"- evaluated_rows: {summary.get('evaluated_rows', 0)}",
        f"- canonical_dates: {summary.get('canonical_dates', 0)}",
        f"- max_candidates_per_canonical_day: {summary.get('max_candidates_per_canonical_day', 0)}",
        f"- executed_entries: {summary.get('executed_entries', 0)}",
        f"- no_entry_triggers: {summary.get('no_entry_triggers', 0)}",
        f"- wins: {summary.get('wins', 0)}",
        f"- losses: {summary.get('losses', 0)}",
        f"- win_rate: {summary.get('win_rate')}",
        f"- profitable_at_4d_rate: {summary.get('profitable_at_4d_rate')}",
        f"- execution_win_rate: {summary.get('execution_win_rate')}",
        f"- avg_execution_return_4d_pct: {summary.get('avg_execution_return_4d_pct')}",
        f"- shadow_evaluated_rows: {summary.get('shadow_evaluated_rows')}",
        f"- shadow_win_rate: {summary.get('shadow_win_rate')}",
        f"- avg_shadow_return_4d_pct: {summary.get('avg_shadow_return_4d_pct')}",
        f"- target_hit_rate: {summary.get('target_hit_rate')}",
        f"- stop_hit_rate: {summary.get('stop_hit_rate')}",
        f"- avg_return_4d_pct: {summary.get('avg_return_4d_pct')}",
        f"- median_return_4d_pct: {summary.get('median_return_4d_pct')}",
        f"- avg_winner_return_4d_pct: {summary.get('avg_winner_return_4d_pct')}",
        f"- avg_loser_return_4d_pct: {summary.get('avg_loser_return_4d_pct')}",
        f"- payoff_ratio: {summary.get('payoff_ratio')}",
        f"- profit_factor: {summary.get('profit_factor')}",
        f"- expectancy_4d_pct: {summary.get('expectancy_4d_pct')}",
        f"- best_trade_return_4d_pct: {summary.get('best_trade_return_4d_pct')}",
        f"- worst_trade_return_4d_pct: {summary.get('worst_trade_return_4d_pct')}",
        f"- avg_realized_r_4d: {summary.get('avg_realized_r_4d')}",
        f"- entry_trigger_rate: {summary.get('entry_trigger_rate')}",
        f"- ambiguous_sequence_rate: {summary.get('ambiguous_sequence_rate')}",
        f"- avg_calculated_rr: {summary.get('avg_calculated_rr')}",
        f"- avg_abs_rr_error: {summary.get('avg_abs_rr_error')}",
        f"- rr_match_rate: {summary.get('rr_match_rate')}",
        f"- avg_target_capture_ratio: {summary.get('avg_target_capture_ratio')}",
        f"- avg_stop_buffer_ratio: {summary.get('avg_stop_buffer_ratio')}",
        f"- sample_size_warning: {report.get('sample_size_warning', '')}",
        "",
        "## Per-run diagnostics",
        "",
        f"- evaluated_rows: {report.get('per_run_summary', {}).get('evaluated_rows', 0)}",
        f"- win_rate: {report.get('per_run_summary', {}).get('win_rate')}",
        f"- avg_return_4d_pct: {report.get('per_run_summary', {}).get('avg_return_4d_pct')}",
        "",
        "## Diagnostic hints",
        "",
    ]
    lines.extend(f"- {hint}" for hint in report.get("diagnostic_hints", []))
    lines.extend(["", "## Clear engine recommendations", ""])
    recommendations = report.get("clear_recommendations", [])
    lines.extend(
        f"- {item.get('failure_class')}: count={item.get('count')} | {item.get('recommendation')}"
        for item in recommendations
    )
    if not recommendations:
        lines.append("- insufficient diagnostic failures")
    for title, key in [
        ("Ticker win rates", "ticker_win_rates"),
        ("Common successes", "common_successes"),
        ("Common failures", "common_failures"),
    ]:
        lines.extend(["", f"## {title}", ""])
        rows = report.get(key, [])
        if not rows:
            lines.append("- insufficient data")
        for row in rows[:20]:
            lines.append(
                f"- {row.get('group')}={row.get('value')}: samples={row.get('executed_entries')} "
                f"win_rate={row.get('win_rate')} target_hit={row.get('target_hit_rate')} "
                f"stop_hit={row.get('stop_hit_rate')} avg_return={row.get('avg_return_4d_pct')}"
            )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Observational evidence only.",
            "- No automatic scoring, threshold, signal or execution changes.",
        ]
    )
    return "\n".join(lines)


def save_reports(report: dict, *, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita la tesis operativa a cuatro sesiones.")
    parser.add_argument("--posttests", nargs="+", default=["reports/posttests/**/*.csv"])
    parser.add_argument("--min-samples", type=int, default=3)
    parser.add_argument("--json-out", default="reports/posttest_thesis_audit_latest.json")
    parser.add_argument("--markdown-out", default="reports/posttest_thesis_audit_latest.md")
    args = parser.parse_args()

    report = build_thesis_audit(_load_posttests(args.posttests), min_samples=args.min_samples)
    save_reports(report, json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))
    print("=== ANALISTA 4-DAY THESIS AUDIT ===")
    print(f"Status: {report.get('status')}")
    print(f"Executed entries: {report.get('summary', {}).get('executed_entries', 0)}")
    print(f"Win rate: {report.get('summary', {}).get('win_rate')}")
    print(f"Sample warning: {report.get('sample_size_warning') or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
