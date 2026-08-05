from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd
from loguru import logger

from config_loader import load_config
from data.historical_data_service import load_historical_prices
from engine.scenario_engine import analyze_scenario
from indicators.pipeline import add_all_indicators

DEFAULT_HORIZONS = [4]
NON_OPERABLE_SIGNALS = {"VETO", "AVOID"}
NON_OPERABLE_RECOMMENDATIONS = {
    "DO_NOT_TRADE",
    "AVOID_FOR_NOW",
    "RECHECK_LIVE_QUOTE",
}

HistoryFn = Callable[[str, pd.Timestamp, pd.Timestamp], pd.DataFrame]


def _safe_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _safe_float(value) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _first_float(row: pd.Series, names: list[str]) -> float | None:
    for name in names:
        value = _safe_float(row.get(name))
        if value is not None:
            return value
    return None


def _infer_scan_date(scan_path: Path, scan_df: pd.DataFrame) -> pd.Timestamp:
    if "scan_timestamp" in scan_df.columns and scan_df["scan_timestamp"].notna().any():
        return pd.to_datetime(scan_df["scan_timestamp"].dropna().iloc[0]).tz_localize(None).normalize()
    return pd.Timestamp(datetime.fromtimestamp(scan_path.stat().st_mtime)).normalize()


def _download_history(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frames = load_historical_prices([ticker], period="2y", interval="1d")
    df = frames.get(ticker)
    if df is None or df.empty:
        return pd.DataFrame()
    dates = pd.to_datetime(df.index).tz_localize(None)
    selected = df.loc[(dates >= start.tz_localize(None)) & (dates <= end.tz_localize(None))].copy()
    return selected[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])


def _normalize_history(hist: pd.DataFrame) -> pd.DataFrame:
    if hist is None or hist.empty:
        return pd.DataFrame()
    out = hist.copy()
    out.columns = [str(column).lower().replace(" ", "_") for column in out.columns]
    required = {"open", "high", "low", "close"}
    if not required.issubset(out.columns):
        return pd.DataFrame()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out.sort_index()


def evaluate_candidate_eligibility(row: pd.Series) -> tuple[bool, str]:
    signal = _safe_text(row.get("signal")).upper()
    recommendation = _safe_text(row.get("recommendation")).upper()
    quote_status = _safe_text(row.get("quote_status")).upper()
    execution_quality = _safe_text(row.get("execution_quote_quality")).upper()

    if signal in NON_OPERABLE_SIGNALS:
        return False, f"non_operable_signal:{signal}"
    if recommendation in NON_OPERABLE_RECOMMENDATIONS:
        return False, f"non_operable_recommendation:{recommendation}"
    if quote_status != "VALID":
        return False, f"quote_status_not_valid:{quote_status or 'MISSING'}"
    if execution_quality != "HIGH":
        return False, f"execution_quote_quality_not_high:{execution_quality or 'MISSING'}"
    if "scenario_eligible_for_backtest" in row.index:
        value = row.get("scenario_eligible_for_backtest")
        if not (value is True or str(value).strip().lower() in {"true", "1", "yes"}):
            return False, "scenario_not_eligible_for_backtest"
    else:
        scenario_status = _safe_text(row.get("scenario_status")).upper()
        if scenario_status and scenario_status != "VALID_TRIGGER":
            return False, f"scenario_status_not_valid:{scenario_status}"
        deep_selected = row.get("deep_analysis_selected")
        if deep_selected is not None and not pd.isna(deep_selected):
            if str(deep_selected).strip().lower() not in {"true", "1", "yes"}:
                return False, "not_selected_for_deep_analysis"

    entry = _first_float(row, ["actionable_entry", "entry"])
    stop = _first_float(row, ["actionable_stop", "stop"])
    target = _first_float(row, ["actionable_target", "target"])
    if entry is None or stop is None or target is None:
        return False, "missing_actionable_levels"
    if not stop < entry < target:
        return False, "invalid_actionable_level_order"

    rr = (target - entry) / (entry - stop)
    if rr <= 0:
        return False, "invalid_risk_reward"
    return True, "eligible_operational_thesis"


def filter_eligible_candidates(scan_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    eligible_indices: list[int] = []
    reasons: dict[str, int] = {}
    for index, row in scan_df.iterrows():
        eligible, reason = evaluate_candidate_eligibility(row)
        reasons[reason] = reasons.get(reason, 0) + 1
        if eligible:
            eligible_indices.append(index)
    return scan_df.loc[eligible_indices].copy(), reasons


def select_backtest_candidates(
    eligible_df: pd.DataFrame,
    top_n_candidates: int = 5,
) -> pd.DataFrame:
    if eligible_df.empty or top_n_candidates <= 0:
        return eligible_df.iloc[0:0].copy()

    selected = eligible_df.copy()
    raw_scores = (
        selected["operational_readiness_score"]
        if "operational_readiness_score" in selected.columns
        else selected["final_trade_score"]
        if "final_trade_score" in selected.columns
        else pd.Series(index=selected.index, dtype=float)
    )
    selected["_selection_score"] = pd.to_numeric(
        raw_scores,
        errors="coerce",
    ).fillna(float("-inf"))
    selected["_selection_ticker"] = (
        selected.get("ticker", pd.Series(index=selected.index, dtype=object))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    selected = selected.sort_values(
        ["_selection_score", "_selection_ticker"],
        ascending=[False, True],
        kind="stable",
    ).head(int(top_n_candidates))
    selected["backtest_selection_rank"] = range(1, len(selected) + 1)
    return selected.drop(columns=["_selection_score", "_selection_ticker"])


def _future_history(hist: pd.DataFrame, scan_date: pd.Timestamp) -> pd.DataFrame:
    dates = pd.to_datetime(hist.index).tz_localize(None).normalize()
    return hist.loc[dates > scan_date].copy()


def _find_entry_position(future: pd.DataFrame, entry: float, entry_window_days: int) -> tuple[int | None, str]:
    for position in range(min(entry_window_days, len(future))):
        bar = future.iloc[position]
        bar_open = float(bar["open"])
        bar_high = float(bar["high"])
        bar_low = float(bar["low"])
        if bar_low <= entry <= bar_high:
            return position, "LEVEL_TOUCHED"
        if bar_open < entry and bar_high >= entry:
            return position, "GAP_BELOW_LEVEL_RECOVERED"
    return None, "ENTRY_NOT_TOUCHED"


def _score_bucket(value) -> str:
    score = _safe_float(value)
    if score is None:
        return "MISSING"
    if score >= 85:
        return "85_PLUS"
    if score >= 75:
        return "75_TO_84"
    if score >= 65:
        return "65_TO_74"
    return "BELOW_65"


def _evaluate_horizon(
    future: pd.DataFrame,
    *,
    entry_position: int,
    horizon: int,
    entry: float,
    stop: float,
    target: float,
) -> dict | None:
    final_position = horizon - 1
    if final_position >= len(future) or entry_position > final_position:
        return None

    window = future.iloc[entry_position : final_position + 1]
    close_h = float(future.iloc[final_position]["close"])
    high_max = float(window["high"].max())
    low_min = float(window["low"].min())
    hit_target = high_max >= target
    hit_stop = low_min <= stop
    return_close = close_h / entry - 1.0
    mfe = high_max / entry - 1.0
    mae = low_min / entry - 1.0
    risk = entry - stop
    realized_r_at_close = (close_h - entry) / risk if risk > 0 else None
    calculated_rr = (target - entry) / risk if risk > 0 else None

    profitable_at_4d = return_close > 0
    if hit_target and hit_stop:
        level_outcome = "BOTH_HIT_DAILY_UNKNOWN_SEQUENCE"
        thesis_reason = "ambiguous_target_stop_sequence"
    elif hit_stop:
        level_outcome = "STOP_HIT"
        thesis_reason = "stop_hit_within_horizon"
    elif hit_target:
        level_outcome = "TARGET_HIT"
        thesis_reason = "target_hit_within_horizon"
    elif return_close > 0:
        level_outcome = "POSITIVE_CLOSE"
        thesis_reason = "profitable_close_without_target"
    elif return_close == 0:
        level_outcome = "BREAKEVEN_CLOSE"
        thesis_reason = "breakeven_close"
    else:
        level_outcome = "NEGATIVE_CLOSE"
        thesis_reason = "negative_close_without_stop"

    return {
        "horizon_days": horizon,
        "evaluation_sessions": len(window),
        "close_h": close_h,
        "return_close_pct": return_close,
        "mfe_pct": mfe,
        "mae_pct": mae,
        "hit_target": hit_target,
        "hit_stop": hit_stop,
        "level_outcome": level_outcome,
        "outcome": level_outcome,
        "thesis_success": bool(hit_target and not hit_stop),
        "thesis_reason": thesis_reason,
        "target_success": bool(hit_target and not hit_stop),
        "profitable_at_4d": profitable_at_4d,
        "calculated_rr": calculated_rr,
        "realized_r_at_close": realized_r_at_close,
        "target_distance_pct": (target / entry) - 1.0,
        "stop_distance_pct": (stop / entry) - 1.0,
        "target_capture_ratio": (mfe / ((target / entry) - 1.0))
        if target > entry
        else None,
        "stop_buffer_ratio": (abs(mae) / abs((stop / entry) - 1.0))
        if stop < entry
        else None,
    }


def _prefixed(values: dict | None, prefix: str) -> dict:
    if not values:
        return {}
    return {f"{prefix}{key}": value for key, value in values.items()}


def run_posttest(
    scan_csv: str | Path,
    horizons: list[int] | None = None,
    output_csv: str | Path | None = None,
    *,
    entry_window_days: int = 2,
    top_n_candidates: int = 5,
    history_fn: HistoryFn = _download_history,
    config: dict | None = None,
) -> pd.DataFrame:
    scan_path = Path(scan_csv)
    horizons = sorted(set(horizons or DEFAULT_HORIZONS))
    scan_df = pd.read_csv(scan_path)
    if scan_df.empty:
        raise ValueError(f"Scan vacío: {scan_path}")

    eligible_df, eligibility_counts = filter_eligible_candidates(scan_df)
    eligible_pool_size = len(eligible_df)
    eligible_df = select_backtest_candidates(
        eligible_df,
        top_n_candidates=top_n_candidates,
    )
    scan_date = _infer_scan_date(scan_path, scan_df)
    max_horizon = max(horizons)
    config = config or load_config()
    start = scan_date - timedelta(days=420)
    end = scan_date + timedelta(days=(entry_window_days + max_horizon) * 3 + 14)
    rows: list[dict] = []

    for _, row in eligible_df.iterrows():
        ticker = _safe_text(row.get("ticker")).upper()
        if not ticker:
            continue
        try:
            history = _normalize_history(history_fn(ticker, start, end))
        except Exception as exc:
            logger.warning(f"Post-test: falló descarga {ticker}: {exc}")
            continue
        future = _future_history(history, scan_date)
        if future.empty:
            continue

        entry = _first_float(row, ["actionable_entry", "entry"])
        stop = _first_float(row, ["actionable_stop", "stop"])
        target = _first_float(row, ["actionable_target", "target"])
        assert entry is not None and stop is not None and target is not None
        entry_position, entry_status = _find_entry_position(future, entry, entry_window_days)
        scan_history = history.loc[
            pd.to_datetime(history.index).tz_localize(None).normalize() <= scan_date
        ].copy()
        scenario_snapshot: dict = {}
        if len(scan_history) >= 64:
            try:
                scenario_snapshot = analyze_scenario(
                    add_all_indicators(scan_history, config),
                    setup_type=_safe_text(row.get("setup_type")).upper(),
                    trigger_level=_safe_float(row.get("trigger_level")),
                    market_regime=_safe_text(row.get("market_regime")),
                    selected=True,
                )
            except Exception as exc:
                logger.warning(f"Post-test: no se pudo reconstruir escenario {ticker}: {exc}")
        for key in [
            "scenario_status",
            "scenario_confidence",
            "momentum_state",
            "extension_state",
            "ema20_extension_status",
            "entry_timing_status",
            "macd_histogram_state",
            "timing_quality_score",
            "momentum_confirmation_score",
            "engine_recommendation",
            "technical_rsi",
            "technical_rsi_change_5d",
            "technical_macd_hist",
            "technical_macd_hist_change_1d",
            "technical_macd_hist_change_3d",
            "technical_distance_ema20_atr",
            "technical_distance_ema20_pct",
            "technical_distance_sma20_atr",
            "technical_distance_sma50_atr",
            "technical_trigger_distance_pct",
            "technical_trigger_distance_atr",
            "technical_relative_volume",
        ]:
            stored = row.get(key)
            if stored is not None and not pd.isna(stored) and str(stored).strip():
                scenario_snapshot[key] = stored

        base = {
            "scan_file": scan_path.name,
            "scan_date": scan_date.date().isoformat(),
            "scan_timestamp": row.get("scan_timestamp"),
            "ticker": ticker,
            "signal": row.get("signal"),
            "recommendation": row.get("recommendation"),
            "setup_type": row.get("setup_type"),
            "sector": row.get("sector"),
            "final_score": row.get("final_score"),
            "final_trade_score": row.get("final_trade_score"),
            "backtest_selection_rank": row.get("backtest_selection_rank"),
            "eligible_pool_size": eligible_pool_size,
            "top_n_candidates": top_n_candidates,
            "score_bucket": _score_bucket(row.get("final_trade_score")),
            "options_bias": row.get("options_bias"),
            "options_confidence": row.get("options_confidence"),
            "stop_atr_status": row.get("stop_atr_status"),
            "quote_status": row.get("quote_status"),
            "execution_quote_quality": row.get("execution_quote_quality"),
            "entry": entry,
            "stop": stop,
            "target": target,
            "published_entry_price": entry,
            "source_rr": _safe_float(row.get("rr")),
            "shadow_entry": _safe_float(row.get("shadow_entry")),
            "shadow_stop": _safe_float(row.get("shadow_stop")),
            "shadow_target": _safe_float(row.get("shadow_target")),
            "shadow_rr": _safe_float(row.get("shadow_rr")),
            "shadow_level_status": row.get("shadow_level_status"),
            "entry_status": entry_status,
            "entry_window_days": entry_window_days,
            **scenario_snapshot,
        }

        for horizon in horizons:
            published_evaluation = _evaluate_horizon(
                future,
                entry_position=0,
                horizon=horizon,
                entry=entry,
                stop=stop,
                target=target,
            )
            if published_evaluation is None:
                continue

            source_rr = base.get("source_rr")
            calculated_rr = published_evaluation.get("calculated_rr")
            published_evaluation["rr_error"] = (
                calculated_rr - source_rr
                if source_rr is not None and calculated_rr is not None
                else None
            )
            published_evaluation["rr_matches_source"] = (
                abs(published_evaluation["rr_error"]) <= 0.02
                if published_evaluation["rr_error"] is not None
                else None
            )

            execution_evaluation = (
                _evaluate_horizon(
                    future,
                    entry_position=entry_position,
                    horizon=horizon,
                    entry=entry,
                    stop=stop,
                    target=target,
                )
                if entry_position is not None
                else None
            )
            shadow_entry = _safe_float(row.get("shadow_entry"))
            shadow_stop = _safe_float(row.get("shadow_stop"))
            shadow_target = _safe_float(row.get("shadow_target"))
            shadow_evaluation = (
                _evaluate_horizon(
                    future,
                    entry_position=0,
                    horizon=horizon,
                    entry=shadow_entry,
                    stop=shadow_stop,
                    target=shadow_target,
                )
                if (
                    _safe_text(row.get("shadow_level_status")).upper() == "VALID"
                    and shadow_entry is not None
                    and shadow_stop is not None
                    and shadow_target is not None
                )
                else None
            )

            status = _safe_text(base.get("scenario_status")).upper()
            setup_type = _safe_text(base.get("setup_type")).upper()
            stop_status = _safe_text(base.get("stop_atr_status")).upper()
            if status == "LATE_ENTRY_OVEREXTENDED":
                failure_class = "LATE_ENTRY_FAILURE"
            elif status == "WEAK_MOMENTUM":
                failure_class = "WEAK_MOMENTUM_FAILURE"
            elif published_evaluation.get("hit_stop") and stop_status in {
                "AGGRESSIVE_TIGHT",
                "BELOW_HARD_MIN",
            }:
                failure_class = "STOP_TOO_TIGHT"
            elif setup_type == "PULLBACK" and not published_evaluation.get("profitable_at_4d"):
                failure_class = "PULLBACK_CONFIRMATION_FAILURE"
            elif setup_type == "BREAKOUT" and not published_evaluation.get("profitable_at_4d"):
                failure_class = "FALSE_BREAKOUT"
            elif (
                published_evaluation.get("profitable_at_4d")
                and not published_evaluation.get("target_success")
            ):
                failure_class = "TARGET_TOO_AMBITIOUS"
            elif published_evaluation.get("profitable_at_4d"):
                failure_class = ""
            else:
                failure_class = "THESIS_NOT_COMPLETED"

            rows.append(
                {
                    **base,
                    **published_evaluation,
                    "published_exit_price_4d": published_evaluation.get("close_h"),
                    "published_return_4d_pct": published_evaluation.get("return_close_pct"),
                    "published_profitable_4d": published_evaluation.get("profitable_at_4d"),
                    "execution_entry_reached": entry_position is not None,
                    "execution_entry_status": entry_status,
                    "execution_entry_date": (
                        future.index[entry_position].date().isoformat()
                        if entry_position is not None
                        else ""
                    ),
                    "entry_date": (
                        future.index[entry_position].date().isoformat()
                        if entry_position is not None
                        else ""
                    ),
                    **_prefixed(execution_evaluation, "execution_"),
                    **_prefixed(shadow_evaluation, "shadow_"),
                    "failure_class": failure_class,
                }
            )

    out = pd.DataFrame(rows)
    out.attrs["input_rows"] = len(scan_df)
    out.attrs["eligible_rows"] = eligible_pool_size
    out.attrs["selected_rows"] = len(eligible_df)
    out.attrs["top_n_candidates"] = top_n_candidates
    out.attrs["eligibility_counts"] = eligibility_counts

    output_path = Path(output_csv) if output_csv else Path("reports/posttests") / f"posttest_{scan_path.stem}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False, float_format="%.6f")
    logger.info(
        f"Post-test guardado en {output_path}; input={len(scan_df)} eligible={len(eligible_df)} output={len(out)}"
    )
    return out
