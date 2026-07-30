from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.price_client import download_daily_prices

DEFAULT_HORIZONS = [5, 10, 15]
NOTICE = "automatic BUY_NOW memory posttest only; no real order; no automatic scoring changes"


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    source_mtime = path.stat().st_mtime
    source_columns = pd.DataFrame(
        {
            "_source_path": str(path),
            "_source_mtime": source_mtime,
            "_report_date": datetime.fromtimestamp(source_mtime).date().isoformat(),
        },
        index=df.index,
    )
    return pd.concat([df.copy(), source_columns], axis=1)


def load_report_sessions(patterns: list[str] | None = None) -> list[pd.DataFrame]:
    patterns = patterns or [
        str(ROOT / "reports" / "history" / "**" / "trade_decision_checklist_latest.csv"),
        str(ROOT / "reports" / "history" / "**" / "trade_decision_checklist.csv"),
        str(ROOT / "reports" / "trade_decision_checklist_latest.csv"),
        str(ROOT / "reports" / "history" / "**" / "manual_review_top.csv"),
        str(ROOT / "reports" / "history" / "**" / "latest_scan_audited.csv"),
        str(ROOT / "reports" / "posttest_memory" / "**" / "automatic_buy_now_memory.csv"),
    ]
    sessions: list[pd.DataFrame] = []
    seen: set[str] = set()
    for pattern in patterns:
        for raw in glob.glob(pattern, recursive=True):
            path = str(Path(raw).resolve())
            if path in seen:
                continue
            seen.add(path)
            frame = _read_csv(Path(path))
            if not frame.empty:
                sessions.append(frame)
    for raw in glob.glob(
        str(ROOT / "reports" / "posttest_memory" / "**" / "session_manifest.json"),
        recursive=True,
    ):
        path = Path(raw).resolve()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if int(payload.get("buy_now_rows", 0) or 0) > 0:
            continue
        mtime = path.stat().st_mtime
        sessions.append(
            pd.DataFrame(
                [
                    {
                        "ticker": "",
                        "_session_empty": True,
                        "_source_path": str(path),
                        "_source_mtime": mtime,
                        "_report_date": str(payload.get("session_date") or path.parent.name),
                    }
                ]
            )
        )
    canonical_by_date: dict[str, pd.DataFrame] = {}
    for session in sessions:
        report_date = _safe_text(session["_report_date"].iloc[0])
        existing = canonical_by_date.get(report_date)
        if existing is None or float(session["_source_mtime"].iloc[0]) >= float(
            existing["_source_mtime"].iloc[0]
        ):
            canonical_by_date[report_date] = session
    canonical = list(canonical_by_date.values())
    canonical.sort(key=lambda df: float(df["_source_mtime"].iloc[0]))
    return canonical


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _is_buy_now_candidate(row: pd.Series) -> bool:
    ticker = _safe_text(row.get("ticker"))
    if not ticker:
        return False

    explicit_status = _safe_text(row.get("automatic_posttest_status")).upper()
    if explicit_status and explicit_status != "BUY_NOW":
        return False
    if "buy_now_candidate" in row.index and _safe_text(row.get("buy_now_candidate")):
        if not _bool(row.get("buy_now_candidate")):
            return False

    signal = _safe_text(row.get("signal")).upper()
    recommendation = _safe_text(row.get("recommendation")).upper()
    checklist = _safe_text(row.get("checklist_status")).upper()
    quote_status = _safe_text(row.get("quote_status")).upper()
    execution_quality = _safe_text(row.get("execution_quote_quality")).upper()
    scenario_status = _safe_text(row.get("scenario_status")).upper()
    scenario_eligible_text = _safe_text(row.get("scenario_eligible_for_backtest"))
    execution_readiness = _safe_text(row.get("execution_readiness_status")).upper()
    blockers = _safe_text(row.get("checklist_blockers"))
    engine_block = _safe_text(row.get("engine_block_reason"))
    shadow_status = _safe_text(row.get("shadow_level_status")).upper()
    daily_macd_state = _safe_text(row.get("macd_histogram_state")).upper()
    weekly_macd_state = _safe_text(row.get("weekly_macd_histogram_state")).upper()
    daily_trajectory_state = _safe_text(row.get("daily_macd_trajectory_state")).upper()
    weekly_trajectory_state = _safe_text(row.get("weekly_macd_trajectory_state")).upper()
    momentum_operability = _safe_text(row.get("momentum_operability_status")).upper()
    technical_prefilter_status = _safe_text(row.get("technical_prefilter_status")).upper()
    technical_analysis_lane = _safe_text(row.get("technical_analysis_lane")).upper()
    decision_lane = _safe_text(row.get("decision_lane")).upper()
    rr_status = _safe_text(row.get("rr_status")).upper()
    risk_geometry_status = _safe_text(row.get("risk_geometry_status")).upper()
    rr = _safe_float(row.get("rr"))

    if signal in {"VETO", "AVOID"}:
        return False
    if recommendation in {"DO_NOT_TRADE", "AVOID_FOR_NOW", "RECHECK_LIVE_QUOTE"}:
        return False
    if checklist and checklist != "HIGH_QUALITY_REVIEW":
        return False
    if quote_status != "VALID" or execution_quality != "HIGH":
        return False
    if scenario_status and scenario_status != "VALID_TRIGGER":
        return False
    if scenario_eligible_text and not _bool(row.get("scenario_eligible_for_backtest")):
        return False
    if execution_readiness and execution_readiness != "EXECUTION_READY_REVIEW":
        return False
    if blockers or engine_block:
        return False
    if technical_prefilter_status and technical_prefilter_status != "PASS":
        return False
    if technical_analysis_lane and technical_analysis_lane != "ADVANCE_DEEP_ANALYSIS":
        return False
    if decision_lane and decision_lane != "EXECUTION_CANDIDATE":
        return False
    if rr_status and rr_status != "VALIDATED":
        return False
    if risk_geometry_status and risk_geometry_status != "ROBUST":
        return False
    if _bool(row.get("earnings_operability_block")):
        return False
    if shadow_status not in {"", "VALID", "NOT_AVAILABLE", "NOT_ELIGIBLE"}:
        return False
    if daily_trajectory_state and daily_trajectory_state not in {"ACCELERATING", "IMPROVING_STEADY"}:
        return False
    if weekly_trajectory_state and weekly_trajectory_state not in {"ACCELERATING", "IMPROVING_STEADY"}:
        return False
    if not weekly_trajectory_state and weekly_macd_state != "WEEKLY_MACD_HIST_IMPROVING":
        return False
    if (
        not daily_trajectory_state
        and daily_macd_state
        and daily_macd_state
        not in {"MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO", "MACD_HIST_POSITIVE_EXPANDING"}
    ):
        return False
    if momentum_operability and momentum_operability != "CONFIRMED_NON_DECELERATING":
        return False
    if rr is None or rr < 1.5:
        return False
    for key in ["actionable_entry", "entry"]:
        entry = _safe_float(row.get(key))
        if entry is not None:
            break
    else:
        entry = None
    for key in ["actionable_stop", "stop"]:
        stop = _safe_float(row.get(key))
        if stop is not None:
            break
    else:
        stop = None
    for key in ["actionable_target", "target"]:
        target = _safe_float(row.get(key))
        if target is not None:
            break
    else:
        target = None
    return entry is not None and stop is not None and target is not None


def select_top_candidates(session: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    if session.empty:
        return session.copy()
    candidates = session[session.apply(_is_buy_now_candidate, axis=1)].copy()
    if candidates.empty:
        return candidates
    score_column = "operational_readiness_score" if "operational_readiness_score" in candidates.columns else "final_trade_score"
    candidates["_selection_score"] = pd.to_numeric(candidates.get(score_column), errors="coerce").fillna(float("-inf"))
    candidates["_selection_trade_score"] = pd.to_numeric(candidates.get("final_trade_score"), errors="coerce").fillna(float("-inf"))
    candidates["_selection_ticker"] = candidates["ticker"].astype(str).str.upper()
    candidates = candidates.sort_values(
        ["_selection_score", "_selection_trade_score", "_selection_ticker"],
        ascending=[False, False, True],
        kind="stable",
    ).head(int(top_n))
    candidates["posttest_rank"] = range(1, len(candidates) + 1)
    candidates["automatic_posttest_status"] = "BUY_NOW"
    if "automatic_posttest_reason" not in candidates.columns:
        candidates["automatic_posttest_reason"] = "strict_automatic_posttest_memory_only"
    return candidates.drop(columns=["_selection_score", "_selection_trade_score", "_selection_ticker"], errors="ignore")


def persist_daily_candidate_memory(
    *,
    source_csv: Path | None = None,
    memory_root: Path | None = None,
    session_date: str | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    source_csv = source_csv or ROOT / "reports" / "latest_scan_audited.csv"
    memory_root = memory_root or ROOT / "reports" / "posttest_memory"
    date_text = session_date or datetime.now(timezone.utc).date().isoformat()
    session_dir = memory_root / date_text
    session_dir.mkdir(parents=True, exist_ok=True)

    source = _read_csv(source_csv) if source_csv.exists() else pd.DataFrame()
    selected = select_top_candidates(source, top_n=top_n) if not source.empty else pd.DataFrame()
    shadow = (
        select_shadow_research_candidates(source, top_n=top_n)
        if not source.empty
        else pd.DataFrame()
    )
    buy_path = session_dir / "automatic_buy_now_memory.csv"
    shadow_path = session_dir / "research_shadow_memory.csv"
    manifest_path = session_dir / "session_manifest.json"
    selected.to_csv(buy_path, index=False)
    shadow.to_csv(shadow_path, index=False)
    payload = {
        "session_date": date_text,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(source_csv),
        "source_exists": source_csv.exists(),
        "buy_now_rows": int(len(selected)),
        "shadow_research_rows": int(len(shadow)),
        "primary_memory": "BUY_NOW_ONLY",
        "empty_session_recorded": selected.empty,
        "notice": NOTICE,
        "creates_trigger_confirmed": False,
        "broker_execution": False,
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _is_shadow_research_candidate(row: pd.Series) -> bool:
    decision_lane = _safe_text(row.get("decision_lane")).upper()
    if decision_lane != "TACTICAL_RESEARCH":
        return False
    daily = _safe_text(row.get("daily_macd_trajectory_state")).upper()
    weekly = _safe_text(row.get("weekly_macd_trajectory_state")).upper()
    if daily not in {"ACCELERATING", "IMPROVING_STEADY"}:
        return False
    if weekly not in {"ACCELERATING", "IMPROVING_STEADY"}:
        return False
    if _safe_text(row.get("ema20_extension_status")).upper() in {
        "OVEREXTENDED",
        "LATE_ENTRY",
    }:
        return False
    return all(
        _safe_float(row.get(field)) is not None
        for field in ["shadow_entry", "shadow_stop", "shadow_target"]
    )


def select_shadow_research_candidates(
    session: pd.DataFrame,
    top_n: int = 5,
) -> pd.DataFrame:
    if session.empty:
        return session.copy()
    candidates = session[session.apply(_is_shadow_research_candidate, axis=1)].copy()
    if candidates.empty:
        return candidates
    candidates["_research_score"] = pd.to_numeric(
        candidates.get(
            "research_priority_score",
            pd.Series(index=candidates.index, dtype=float),
        ),
        errors="coerce",
    ).fillna(float("-inf"))
    candidates["_opportunity_score"] = pd.to_numeric(
        candidates.get(
            "technical_opportunity_score",
            pd.Series(index=candidates.index, dtype=float),
        ),
        errors="coerce",
    ).fillna(float("-inf"))
    candidates["_ticker"] = candidates["ticker"].astype(str).str.upper()
    candidates = candidates.sort_values(
        ["_research_score", "_opportunity_score", "_ticker"],
        ascending=[False, False, True],
        kind="stable",
    ).head(int(top_n))
    candidates["shadow_posttest_rank"] = range(1, len(candidates) + 1)
    return candidates.drop(
        columns=["_research_score", "_opportunity_score", "_ticker"],
        errors="ignore",
    )


def _as_shadow_evaluation_row(row: pd.Series) -> pd.Series:
    shadow = row.copy()
    shadow["actionable_entry"] = row.get("shadow_entry")
    shadow["actionable_stop"] = row.get("shadow_stop")
    shadow["actionable_target"] = row.get("shadow_target")
    return shadow


def _evaluate_with_history(row: pd.Series, history: pd.DataFrame, horizon: int) -> dict[str, Any]:
    entry = _safe_float(row.get("actionable_entry") if "actionable_entry" in row.index else row.get("entry"))
    stop = _safe_float(row.get("actionable_stop") if "actionable_stop" in row.index else row.get("stop"))
    target = _safe_float(row.get("actionable_target") if "actionable_target" in row.index else row.get("target"))
    ticker = _safe_text(row.get("ticker")).upper()
    base = {
        "ticker": ticker,
        "horizon_sessions": horizon,
        "entry": entry,
        "stop": stop,
        "target": target,
        "evaluated": False,
        "return_pct": None,
        "win": None,
        "target_hit": False,
        "stop_hit": False,
        "entry_touched": False,
        "failure_class": "DATA_UNAVAILABLE",
    }
    if history is None or history.empty or entry is None or stop is None or target is None:
        return base
    hist = history.copy()
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    hist = hist.sort_index()
    future = hist.tail(max(horizon, 1))
    if len(future) < horizon or "close" not in future.columns:
        return base
    high = pd.to_numeric(future.get("high"), errors="coerce")
    low = pd.to_numeric(future.get("low"), errors="coerce")
    close = pd.to_numeric(future.get("close"), errors="coerce")
    if close.dropna().empty:
        return base
    close_h = float(close.dropna().iloc[-1])
    target_hit = bool(high.max() >= target) if high.notna().any() else False
    stop_hit = bool(low.min() <= stop) if low.notna().any() else False
    entry_touched = bool((low <= entry).any() and (high >= entry).any()) if high.notna().any() and low.notna().any() else False
    ret = (close_h / entry - 1.0) * 100.0 if entry else None
    failure = ""
    scenario = _safe_text(row.get("scenario_status")).upper()
    momentum = _safe_text(row.get("momentum_state")).upper()
    extension = _safe_text(row.get("extension_state")).upper()
    ema20_extension = _safe_text(row.get("ema20_extension_status")).upper()
    weekly_macd_state = _safe_text(row.get("weekly_macd_histogram_state")).upper()
    sector_macd_state = _safe_text(row.get("sector_weekly_macd_state")).upper()
    if not entry_touched:
        failure = "ENTRY_NOT_TOUCHED"
    elif ema20_extension in {"OVEREXTENDED", "LATE_ENTRY"}:
        failure = "ENTRY_TOO_FAR_FROM_EMA20"
    elif scenario == "LATE_ENTRY_OVEREXTENDED" or extension in {"OVEREXTENDED", "LATE_ENTRY"}:
        failure = "LATE_ENTRY_OR_OVEREXTENSION"
    elif ema20_extension == "CAUTION":
        failure = "EMA20_EXTENSION_CAUTION"
    elif weekly_macd_state in {"WEEKLY_MACD_HIST_DECELERATING", "WEEKLY_MACD_HIST_BEARISH"}:
        failure = "WEEKLY_MACD_NOT_IMPROVING"
    elif sector_macd_state in {"SECTOR_MACD_DECELERATING", "SECTOR_MACD_BEARISH"}:
        failure = "SECTOR_MACD_NOT_IMPROVING"
    elif _safe_text(row.get("macd_histogram_state")).upper() == "MACD_HIST_DETERIORATING":
        failure = "MACD_HIST_DETERIORATED_AFTER_SIGNAL"
    elif momentum in {"WEAK", "DETERIORATING"} or scenario == "WEAK_MOMENTUM":
        failure = "WEAK_MOMENTUM"
    elif stop_hit:
        failure = "STOP_HIT"
    elif ret is not None and ret <= 0:
        failure = "THESIS_NOT_COMPLETED"
    return {
        **base,
        "evaluated": True,
        "close_h": close_h,
        "return_pct": ret,
        "win": bool(ret is not None and ret > 0),
        "target_hit": target_hit,
        "stop_hit": stop_hit,
        "entry_touched": entry_touched,
        "failure_class": failure,
    }


def _profit_factor(returns: pd.Series) -> float | None:
    gains = returns[returns > 0].sum()
    losses = returns[returns < 0].sum()
    if losses == 0:
        return None if gains == 0 else float("inf")
    return float(gains / abs(losses))


def _empty_horizon_summary(horizons: list[int]) -> dict[str, dict[str, Any]]:
    return {
        str(horizon): {
            "tickers_evaluated": 0,
            "avg_return_pct": None,
            "median_return_pct": None,
            "win_rate": None,
            "best_trade": None,
            "worst_trade": None,
            "target_hit_rate": None,
            "stop_hit_rate": None,
            "entry_touched_rate": None,
            "profit_factor": None,
            "expectancy_pct": None,
            "top_failures": {},
        }
        for horizon in horizons
    }


def summarize_results(rows: pd.DataFrame) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for horizon, group in rows.groupby("horizon_sessions") if not rows.empty else []:
        evaluated = group[group["evaluated"] == True]  # noqa: E712
        returns = pd.to_numeric(evaluated.get("return_pct"), errors="coerce").dropna()
        summary[str(horizon)] = {
            "tickers_evaluated": int(len(evaluated)),
            "avg_return_pct": float(returns.mean()) if not returns.empty else None,
            "median_return_pct": float(returns.median()) if not returns.empty else None,
            "win_rate": float((returns > 0).mean()) if not returns.empty else None,
            "best_trade": float(returns.max()) if not returns.empty else None,
            "worst_trade": float(returns.min()) if not returns.empty else None,
            "target_hit_rate": float(evaluated["target_hit"].mean()) if not evaluated.empty else None,
            "stop_hit_rate": float(evaluated["stop_hit"].mean()) if not evaluated.empty else None,
            "entry_touched_rate": float(evaluated["entry_touched"].mean()) if not evaluated.empty else None,
            "profit_factor": _profit_factor(returns) if not returns.empty else None,
            "expectancy_pct": float(returns.mean()) if not returns.empty else None,
            "top_failures": evaluated["failure_class"].replace("", pd.NA).dropna().value_counts().head(5).to_dict()
            if "failure_class" in evaluated.columns
            else {},
        }
    return summary


def run_posttest(
    *,
    horizons: list[int] | None = None,
    top_n: int = 5,
    history_fn: Callable[..., dict[str, pd.DataFrame]] = download_daily_prices,
) -> dict[str, Any]:
    horizons = sorted(set(horizons or DEFAULT_HORIZONS))
    sessions = load_report_sessions()
    rows: list[dict[str, Any]] = []
    shadow_rows: list[dict[str, Any]] = []
    if not sessions:
        return {
            "status": "WARN",
            "rows": 0,
            "report_sessions_available": 0,
            "horizons": horizons,
            "horizon_summary": _empty_horizon_summary(horizons),
            "recommendations": ["need_more_report_history"],
            "buy_now_memory_rows": 0,
            "shadow_research_rows": 0,
            "shadow_false_negative_summary": _empty_horizon_summary(horizons),
            "shadow_rows_data": [],
            "notice": NOTICE,
        }

    for horizon in horizons:
        if len(sessions) <= horizon:
            continue
        session = sessions[-(horizon + 1)]
        selected = select_top_candidates(session, top_n)
        shadow_selected = select_shadow_research_candidates(session, top_n)
        tickers = sorted(
            set(
                selected.get("ticker", pd.Series(dtype=str))
                .astype(str)
                .str.upper()
                .tolist()
                + shadow_selected.get("ticker", pd.Series(dtype=str))
                .astype(str)
                .str.upper()
                .tolist()
            )
        )
        try:
            histories = history_fn(tickers, period="3mo", interval="1d") if tickers else {}
        except Exception:
            histories = {}
        for _, row in selected.iterrows():
            ticker = _safe_text(row.get("ticker")).upper()
            evaluation = _evaluate_with_history(row, histories.get(ticker, pd.DataFrame()), horizon)
            rows.append(
                {
                    "report_session_index": len(sessions) - horizon - 1,
                    "report_date": row.get("_report_date", ""),
                    "source_path": row.get("_source_path", ""),
                    "posttest_rank": row.get("posttest_rank", ""),
                    "signal": row.get("signal", ""),
                    "recommendation": row.get("recommendation", ""),
                    "setup_type": row.get("setup_type", ""),
                    "scenario_status": row.get("scenario_status", ""),
                    "momentum_state": row.get("momentum_state", ""),
                    "extension_state": row.get("extension_state", ""),
                    "ema20_extension_status": row.get("ema20_extension_status", ""),
                    "entry_timing_status": row.get("entry_timing_status", ""),
                    "macd_histogram_state": row.get("macd_histogram_state", ""),
                    "weekly_macd_histogram_state": row.get("weekly_macd_histogram_state", ""),
                    "weekly_macd_hist_change_1w": row.get("weekly_macd_hist_change_1w", ""),
                    "weekly_macd_hist_change_2w": row.get("weekly_macd_hist_change_2w", ""),
                    "sector_benchmark_symbol": row.get("sector_benchmark_symbol", ""),
                    "sector_weekly_macd_state": row.get("sector_weekly_macd_state", ""),
                    "sector_weekly_macd_acceleration_state": row.get(
                        "sector_weekly_macd_acceleration_state", ""
                    ),
                    "sector_context_status": row.get("sector_context_status", ""),
                    "sector_context_reason": row.get("sector_context_reason", ""),
                    "timing_quality_score": row.get("timing_quality_score", ""),
                    "momentum_confirmation_score": row.get("momentum_confirmation_score", ""),
                    "technical_distance_ema20_atr": row.get("technical_distance_ema20_atr", ""),
                    "technical_distance_ema20_pct": row.get("technical_distance_ema20_pct", ""),
                    "technical_macd_hist_change_3d": row.get("technical_macd_hist_change_3d", ""),
                    "final_trade_score": row.get("final_trade_score", ""),
                    "operational_readiness_score": row.get("operational_readiness_score", ""),
                    "automatic_posttest_status": row.get("automatic_posttest_status", "BUY_NOW"),
                    "automatic_posttest_reason": row.get("automatic_posttest_reason", ""),
                    **evaluation,
                }
            )
        for _, row in shadow_selected.iterrows():
            ticker = _safe_text(row.get("ticker")).upper()
            evaluation = _evaluate_with_history(
                _as_shadow_evaluation_row(row),
                histories.get(ticker, pd.DataFrame()),
                horizon,
            )
            shadow_rows.append(
                {
                    "report_session_index": len(sessions) - horizon - 1,
                    "report_date": row.get("_report_date", ""),
                    "source_path": row.get("_source_path", ""),
                    "shadow_posttest_rank": row.get("shadow_posttest_rank", ""),
                    "decision_lane": row.get("decision_lane", ""),
                    "primary_setup_hypothesis": row.get(
                        "primary_setup_hypothesis",
                        row.get("setup_type", ""),
                    ),
                    "research_priority_score": row.get("research_priority_score", ""),
                    "technical_opportunity_score": row.get(
                        "technical_opportunity_score",
                        "",
                    ),
                    "cohort": "TACTICAL_RESEARCH_SHADOW",
                    **evaluation,
                }
            )
    out = pd.DataFrame(rows)
    shadow_out = pd.DataFrame(shadow_rows)
    horizon_summary = summarize_results(out)
    for horizon in horizons:
        horizon_summary.setdefault(
            str(horizon),
            {
                "tickers_evaluated": 0,
                "avg_return_pct": None,
                "median_return_pct": None,
                "win_rate": None,
                "best_trade": None,
                "worst_trade": None,
                "target_hit_rate": None,
                "stop_hit_rate": None,
                "entry_touched_rate": None,
                "profit_factor": None,
                "expectancy_pct": None,
                "top_failures": {},
            },
        )
    recommendations = []
    failures = out.get("failure_class", pd.Series(dtype=str)).replace("", pd.NA).dropna().value_counts() if not out.empty else pd.Series(dtype=int)
    if not failures.empty:
        top_failure = str(failures.index[0])
        recommendations.append(f"monitorear_falla_principal:{top_failure}")
    if "LATE_ENTRY_OR_OVEREXTENSION" in failures.index:
        recommendations.append("revisar_penalizacion_de_entradas_tardias")
    if "WEAK_MOMENTUM" in failures.index:
        recommendations.append("revisar_confirmacion_de_momentum")
    if "WEEKLY_MACD_NOT_IMPROVING" in failures.index:
        recommendations.append("revisar_confirmacion_de_macd_semanal")
    if "SECTOR_MACD_NOT_IMPROVING" in failures.index:
        recommendations.append("revisar_contexto_macd_semanal_sectorial")
    if "EMA20_EXTENSION_CAUTION" in failures.index:
        recommendations.append("revisar_timing_por_extension_ema20")
    if not recommendations:
        recommendations.append("NO_BUY_NOW_MEMORY" if out.empty else "NO_ACTION")
    status = "PASS" if not out.empty else "PASS_NO_ELIGIBLE_COHORT"
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(out)),
        "report_sessions_available": int(len(sessions)),
        "horizons": horizons,
        "horizon_summary": horizon_summary,
        "recommendations": recommendations,
        "buy_now_memory_rows": int(len(out)),
        "shadow_research_rows": int(len(shadow_out)),
        "shadow_false_negative_summary": summarize_results(shadow_out),
        "notice": NOTICE,
        "creates_trigger_confirmed": False,
        "broker_execution": False,
        "changes_scoring": False,
        "rows_data": out.to_dict(orient="records") if not out.empty else [],
        "shadow_rows_data": (
            shadow_out.to_dict(orient="records") if not shadow_out.empty else []
        ),
    }


def save_reports(result: dict[str, Any], *, csv_out: Path, json_out: Path, markdown_out: Path) -> dict[str, Any]:
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    rows = pd.DataFrame(result.get("rows_data", []))
    rows.to_csv(csv_out, index=False)
    payload = {key: value for key, value in result.items() if key != "rows_data"}
    payload["csv_out"] = str(csv_out)
    payload["json_out"] = str(json_out)
    payload["markdown_out"] = str(markdown_out)
    json_out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Analista - Automatic BUY_NOW memory posttest",
        "",
        f"- status: {payload.get('status')}",
        f"- rows: {payload.get('rows')}",
        f"- buy_now_memory_rows: {payload.get('buy_now_memory_rows', payload.get('rows', 0))}",
        f"- report_sessions_available: {payload.get('report_sessions_available')}",
        f"- notice: {NOTICE}",
        "",
        "## Horizons",
    ]
    for horizon, summary in (payload.get("horizon_summary") or {}).items():
        lines.append(f"- {horizon}: win_rate={summary.get('win_rate')} avg_return_pct={summary.get('avg_return_pct')}")
    lines.extend(["", "## Cohorte shadow de investigación"])
    lines.append(
        f"- filas: {payload.get('shadow_research_rows', 0)}"
    )
    for horizon, summary in (
        payload.get("shadow_false_negative_summary") or {}
    ).items():
        lines.append(
            f"- {horizon}: win_rate={summary.get('win_rate')} "
            f"avg_return_pct={summary.get('avg_return_pct')}"
        )
    lines.extend(["", "## Recommendations"])
    for item in payload.get("recommendations", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- BUY_NOW is only an automatic posttest memory label.",
            "- No automatic trading.",
            "- No scoring changes.",
            "- No real order.",
        ]
    )
    markdown_out.write_text("\n".join(lines), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-out", default=str(ROOT / "reports" / "simple_candidate_posttest_latest.csv"))
    parser.add_argument("--json-out", default=str(ROOT / "reports" / "simple_candidate_posttest_latest.json"))
    parser.add_argument("--markdown-out", default=str(ROOT / "reports" / "simple_candidate_posttest_latest.md"))
    args = parser.parse_args()
    memory = persist_daily_candidate_memory()
    result = run_posttest()
    result["daily_memory"] = memory
    payload = save_reports(result, csv_out=Path(args.csv_out), json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))
    print("=== ANALISTA SIMPLE CANDIDATE POSTTEST ===")
    print(f"Status: {payload.get('status')}")
    print(f"Rows: {payload.get('rows')}")
    print(f"JSON: {args.json_out}")
    print(f"Markdown: {args.markdown_out}")
    return 0 if payload.get("status") in {"PASS", "WARN", "PASS_NO_ELIGIBLE_COHORT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
