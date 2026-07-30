from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

import pandas as pd
from loguru import logger

from data.data_quality import score_data_quality
from data.earnings_context import (
    evaluate_post_earnings_stabilization,
    normalize_earnings_context,
)
from data.fundamentals_client import enrich_metadata
from data.options_client import fetch_options_metrics
from data.price_client import download_daily_prices
from data.screener_client import run_screeners
from data.technical_bars import derive_technical_prices
from engine.data_sources.analysis_quotes import (
    apply_analysis_quote_fallback,
    build_analysis_quote_fallbacks,
    select_analysis_quote_fallback_tickers,
)
from engine.candidate_funnel import select_deep_analysis_candidates
from engine.options_flow import build_options_flow_fields
from engine.options_selection import select_options_tickers
from engine.scenario_engine import (
    analyze_scenario,
    apply_scenario_guardrail,
    calculate_shadow_levels,
)
from engine.technical_assessment import (
    RADAR_SETUP_TYPES,
    VALID_SETUP_TYPES,
    evaluate_technical_opportunity,
)
from engine.technical_prefilter import evaluate_technical_prefilter
from indicators.pipeline import add_all_indicators
from market.market_regime import classify_market_regime
from market.sector_rotation import (
    calculate_sector_benchmark_context,
    calculate_sector_rotation,
    sector_benchmark_symbols_for_meta,
)
from scoring.final_score import calculate_final_score, calculate_trade_score_breakdown
from scoring.fundamental_score import score_fundamentals
from scoring.momentum_score import score_momentum
from scoring.operational_priority import calculate_operational_priority
from scoring.operational_readiness import calculate_operational_readiness
from scoring.options_score import calculate_options_score_adjustment, score_options_flow
from scoring.relative_strength import add_relative_strength_scores
from scoring.signal_classifier import classify_base_signal, classify_signal
from scoring.volume_score import score_volume
from universe.equity_validator import validate_universe
from universe.liquidity_filter import compute_liquidity


def _clean_warning_value(value) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in {"", "none", "nan", "null"}:
        return ""

    return text


def _join_warnings(*values) -> str:
    cleaned = [_clean_warning_value(v) for v in values]
    cleaned = [v for v in cleaned if v]
    return "; ".join(cleaned)


def _safe_float(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _scenario_setup_type(assessment: dict, structure: dict) -> str:
    exact_setup = str((structure or {}).get("setup_type") or "NO_VALID_SETUP").upper()
    if (
        str((assessment or {}).get("technical_analysis_lane") or "").upper()
        == "ADVANCE_RESEARCH_ANALYSIS"
        and str((assessment or {}).get("setup_readiness_state") or "").upper()
        == "FORMING"
    ):
        candidate_setup = str(
            (assessment or {}).get("research_setup_type")
            or (assessment or {}).get("setup_candidate_type")
            or exact_setup
        ).upper()
        if candidate_setup in VALID_SETUP_TYPES:
            return candidate_setup
    return exact_setup


def _performance_report_path(config: dict) -> Path:
    return Path(
        config.get("performance", {}).get(
            "scan_report_path",
            "reports/scan_performance_latest.json",
        )
    )


def _public_performance_payload(performance: dict) -> dict:
    return {key: value for key, value in performance.items() if not str(key).startswith("_")}


def _write_scan_performance(performance: dict) -> None:
    path = performance.get("_report_path")
    if not path:
        return
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_public_performance_payload(performance), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning(f"No se pudo guardar scan performance: {exc}")


def _stage_start(performance: dict, name: str) -> None:
    performance["status"] = "RUNNING"
    performance["current_stage"] = name
    performance["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_scan_performance(performance)


def _stage_done(performance: dict, name: str, started: float) -> None:
    performance.setdefault("stage_seconds", {})[name] = round(perf_counter() - started, 4)
    performance["last_completed_stage"] = name
    performance["current_stage"] = ""
    performance["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_scan_performance(performance)


def apply_operational_signal_guardrails(row: dict, penalty_reasons: list[str]) -> dict:
    """Apply post-scenario operational demotions without promoting signals."""
    guarded = dict(row)
    signal = str(guarded.get("signal") or "").upper().strip()
    macd_state = str(guarded.get("macd_histogram_state") or "").upper().strip()

    if macd_state == "MACD_HIST_DETERIORATING" and signal not in {"VETO", "AVOID"}:
        guarded["signal"] = "AVOID"
        if "macd_histogram_deteriorating" not in penalty_reasons:
            penalty_reasons.append("macd_histogram_deteriorating")

    if (
        bool(guarded.get("earnings_operability_block"))
        and guarded.get("signal") not in {"VETO", "AVOID"}
    ):
        guarded["signal"] = "WATCHLIST"
        guarded["recommendation"] = "WATCHLIST_MONITOR"
        guarded["scenario_eligible_for_backtest"] = False
        guarded["scenario_operability"] = "RESEARCH_ONLY"
        guarded["engine_recommendation"] = "RESEARCH_ONLY"
        guarded["actionable_entry"] = None
        guarded["actionable_stop"] = None
        guarded["actionable_target"] = None
        reason = str(
            guarded.get("earnings_review_reason")
            or "earnings_operability_block"
        )
        if reason not in penalty_reasons:
            penalty_reasons.append(reason)

    risk_geometry_status = str(
        guarded.get("risk_geometry_status") or "UNKNOWN"
    ).upper()
    if risk_geometry_status in {"FRAGILE", "INVALID"}:
        guarded["scenario_eligible_for_backtest"] = False
        guarded["scenario_operability"] = "RESEARCH_ONLY"
        guarded["engine_recommendation"] = "RESEARCH_ONLY"
        guarded["actionable_entry"] = None
        guarded["actionable_stop"] = None
        guarded["actionable_target"] = None
        reason = str(
            guarded.get("risk_geometry_reason")
            or f"risk_geometry_{risk_geometry_status.lower()}"
        )
        if reason not in penalty_reasons:
            penalty_reasons.append(reason)

    return guarded


def _build_technical_prefilter_reject_row(
    *,
    ticker: str,
    source_meta: dict,
    prefilter: dict,
    liquidity: dict,
    scan_timestamp: str,
) -> dict:
    reason = str(
        prefilter.get("technical_eligibility_reason")
        or prefilter.get("technical_prefilter_reason")
        or "technical_assessment_failed"
    )
    lane = str(
        prefilter.get("technical_analysis_lane")
        or prefilter.get("technical_prefilter_triage")
        or "REJECT_RISK"
    ).upper()
    decision_lane = str(prefilter.get("decision_lane") or "").upper()
    if decision_lane == "LEADERSHIP_RESET_WATCH":
        operational_status = "WAIT_PULLBACK_OR_CONSOLIDATION"
        momentum_state = "STRONG_BUT_EXTENDED"
    elif decision_lane == "MOMENTUM_RECOVERY_WATCH":
        operational_status = "WAIT_MOMENTUM_RECOVERY"
        momentum_state = "DECELERATING_OR_UNCONFIRMED"
    elif lane == "RADAR_FORMING_SETUP":
        operational_status = "MONITOR_NEXT_TRIGGER"
        momentum_state = "UNCONFIRMED"
    elif lane == "INSUFFICIENT_DATA":
        operational_status = "DATA_BLOCKED"
        momentum_state = "UNKNOWN"
    else:
        operational_status = "REJECTED_TECHNICAL"
        momentum_state = "WEAK" if lane == "REJECT_MOMENTUM" else "NOT_EVALUATED"
    structure = prefilter.get("structure") or {}
    rr_data = prefilter.get("rr_data") or {}
    setup_type = str(
        prefilter.get("setup_type")
        or structure.get("setup_type")
        or "NO_VALID_SETUP"
    ).upper()
    latest_price = liquidity.get("price") or prefilter.get("technical_close")
    return {
        "scan_timestamp": scan_timestamp,
        "ticker": ticker,
        "company": source_meta.get("company"),
        "exchange": source_meta.get("exchange"),
        "quote_type": source_meta.get("quote_type"),
        "country": source_meta.get("country"),
        "sector": source_meta.get("sector"),
        "industry": source_meta.get("industry"),
        "market_cap": source_meta.get("market_cap"),
        "final_score": 0.0,
        "asset_attractiveness_score": 0.0,
        "asset_quality_score": 0.0,
        "setup_quality_score": 0.0,
        "context_score": 0.0,
        "institutional_score": 0.0,
        "final_trade_score": 0.0,
        "score_breakdown": "{}",
        "deep_analysis_selected": False,
        "deep_analysis_tier": prefilter.get("deep_analysis_tier", "NONE"),
        "deep_analysis_rank": None,
        "deep_analysis_score": None,
        "deep_analysis_reason": reason,
        "decision_lane": decision_lane or "STRUCTURAL_REJECT",
        "decision_reasons": prefilter.get("decision_reasons", reason),
        "technical_asset_quality_score": prefilter.get("technical_asset_quality_score"),
        "entry_readiness_score": prefilter.get("entry_readiness_score"),
        "research_priority_score": prefilter.get("research_priority_score"),
        "reset_watch_score": prefilter.get("reset_watch_score"),
        "context_confidence_score": prefilter.get("context_confidence_score"),
        "data_confidence_score": prefilter.get("data_confidence_score"),
        "operational_eligibility": bool(prefilter.get("operational_eligibility", False)),
        "research_eligibility_reason": prefilter.get("research_eligibility_reason", ""),
        "research_setup_type": prefilter.get("research_setup_type"),
        "research_trend_compatibility": prefilter.get("research_trend_compatibility"),
        "research_trend_compatibility_reason": prefilter.get(
            "research_trend_compatibility_reason"
        ),
        "setup_readiness_score": prefilter.get("setup_readiness_score"),
        "setup_readiness_state": prefilter.get("setup_readiness_state", "NONE"),
        "setup_candidate_type": prefilter.get("setup_candidate_type"),
        "setup_readiness_reason": prefilter.get("setup_readiness_reason"),
        "setup_readiness_components": prefilter.get("setup_readiness_components"),
        "primary_setup_hypothesis": prefilter.get("primary_setup_hypothesis"),
        "primary_setup_hypothesis_state": prefilter.get("primary_setup_hypothesis_state"),
        "primary_setup_hypothesis_score": prefilter.get("primary_setup_hypothesis_score"),
        "alternative_setup_hypotheses": prefilter.get("alternative_setup_hypotheses"),
        "setup_hypotheses": prefilter.get("setup_hypotheses"),
        "setup_hypothesis_count": prefilter.get("setup_hypothesis_count"),
        "ema20_caution_mild": bool(prefilter.get("ema20_caution_mild", False)),
        "ema20_distance_percentile_1y": prefilter.get("ema20_distance_percentile_1y"),
        "ema20_extension_model": prefilter.get("ema20_extension_model"),
        "trend_transition_score": prefilter.get("trend_transition_score"),
        "trend_transition_state": prefilter.get("trend_transition_state"),
        "trend_transition_reason": prefilter.get("trend_transition_reason"),
        "trend_score": prefilter.get("trend_score", 0.0),
        "trend_status": prefilter.get("trend_status", "NOT_EVALUATED"),
        "volume_score": 0.0,
        "sector_score": 0.0,
        "structure_score": structure.get("structure_score", 0.0),
        "rr_score": rr_data.get("rr_score", 0.0),
        "liquidity_pass": bool(
            liquidity.get("liquidity_core_pass", liquidity.get("liquidity_pass", False))
        ),
        "liquidity_score": liquidity.get("liquidity_score", 0.0),
        "momentum_score": 0.0,
        "fundamental_score": 0.0,
        "options_score": 0.5,
        "options_scoring_status": "CONTEXT_ONLY_NOT_SCORED",
        "options_bias": "UNKNOWN_OPTIONS_FLOW",
        "options_confidence": "UNKNOWN",
        "options_coverage_status": "NOT_SELECTED_TECHNICAL_ASSESSMENT",
        "options_priority_selected": False,
        "options_priority_reason": "technical_assessment_not_eligible",
        "setup_type": setup_type,
        "trigger_confirmed": bool(structure.get("trigger_confirmed", False)),
        "trigger_level": structure.get("trigger_level"),
        "entry": rr_data.get("entry"),
        "stop": rr_data.get("stop"),
        "target": rr_data.get("target"),
        "rr": rr_data.get("rr"),
        "rr_valid": rr_data.get("rr_valid", prefilter.get("rr_valid", False)),
        "rr_status": rr_data.get(
            "rr_status",
            prefilter.get("rr_status", "NOT_APPLICABLE_FORMING_SETUP"),
        ),
        "rr_confidence": rr_data.get(
            "rr_confidence",
            prefilter.get("rr_confidence", "UNKNOWN"),
        ),
        "target_validation_source": rr_data.get(
            "target_validation_source",
            prefilter.get("target_validation_source", "NONE"),
        ),
        "target_validation_sources": rr_data.get("target_validation_sources"),
        "target_candidates": rr_data.get("target_candidates"),
        "entry_zone_low": prefilter.get("entry_zone_low"),
        "entry_zone_high": prefilter.get("entry_zone_high"),
        "theoretical_entry": None,
        "theoretical_stop": None,
        "theoretical_target": None,
        "actionable_entry": None,
        "actionable_stop": None,
        "actionable_target": None,
        "scenario_entry": None,
        "scenario_stop": None,
        "scenario_target": None,
        "shadow_entry": None,
        "shadow_stop": None,
        "shadow_target": None,
        "shadow_rr": None,
        "shadow_stop_atr_multiple": None,
        "shadow_level_status": "NOT_ELIGIBLE",
        "stop_method": rr_data.get("stop_method"),
        "target_method": rr_data.get("target_method"),
        "risk_pct": rr_data.get("risk_pct"),
        "reward_pct": rr_data.get("reward_pct"),
        "atr": prefilter.get("technical_atr"),
        "atr_pct": prefilter.get("technical_atr_pct"),
        "stop_atr_multiple": rr_data.get("stop_atr_multiple"),
        "stop_atr_status": rr_data.get("stop_atr_status", "NOT_AVAILABLE"),
        "rr_stressed": rr_data.get("rr_stressed"),
        "risk_geometry_status": rr_data.get("risk_geometry_status", "INVALID"),
        "risk_geometry_reason": rr_data.get(
            "risk_geometry_reason",
            "technical_prefilter_not_operational",
        ),
        "relative_volume": prefilter.get("technical_relative_volume"),
        "price": latest_price,
        "adjusted_close": latest_price,
        "price_adjustment_factor": None,
        "technical_price_basis": "ADJUSTED_OHLC" if latest_price is not None else "UNKNOWN",
        "technical_as_of_date": prefilter.get("technical_as_of_date"),
        "technical_bar_policy": prefilter.get(
            "technical_bar_policy",
            "CLOSED_DAILY_AND_WEEKLY_ONLY",
        ),
        "daily_bar_complete": prefilter.get("daily_bar_complete", False),
        "weekly_bar_complete": prefilter.get("weekly_bar_complete", False),
        "intraday_bar_excluded": prefilter.get("intraday_bar_excluded", False),
        "avg_volume_20d": liquidity.get("avg_volume_20d"),
        "avg_volume_60d": liquidity.get("avg_volume_60d"),
        "median_volume_20d": liquidity.get("median_volume_20d"),
        "mean_volume_20d": liquidity.get("mean_volume_20d"),
        "dollar_volume_20d": liquidity.get("dollar_volume_20d"),
        "dollar_volume_60d": liquidity.get("dollar_volume_60d"),
        "liquidity_turnover_20d": liquidity.get("liquidity_turnover_20d"),
        "liquidity_turnover_60d": liquidity.get("liquidity_turnover_60d"),
        "liquidity_market_cap_tier": liquidity.get("liquidity_market_cap_tier"),
        "liquidity_required_turnover_20d": liquidity.get("liquidity_required_turnover_20d"),
        "liquidity_required_turnover_60d": liquidity.get("liquidity_required_turnover_60d"),
        "liquidity_formula_pass_20d": liquidity.get("liquidity_formula_pass_20d"),
        "liquidity_formula_pass_60d": liquidity.get("liquidity_formula_pass_60d"),
        "liquidity_dollar_pass_20d": liquidity.get("liquidity_dollar_pass_20d"),
        "liquidity_dollar_pass_60d": liquidity.get("liquidity_dollar_pass_60d"),
        "liquidity_core_pass": liquidity.get("liquidity_core_pass"),
        "liquidity_spread_pass": liquidity.get("liquidity_spread_pass"),
        "execution_spread_status": liquidity.get("execution_spread_status", "UNKNOWN"),
        "execution_spread_score": liquidity.get("execution_spread_score"),
        "median_to_mean_volume_ratio": liquidity.get("median_to_mean_volume_ratio"),
        "spread_pct": None,
        "bid": None,
        "ask": None,
        "bid_ask_valid": False,
        "bid_ask_warning": "technical_prefilter_failed_before_quote_enrichment",
        "spread_validated_pct": None,
        "quote_status": "MISSING",
        "execution_quote_quality": "LOW",
        "quote_source": "NOT_REQUESTED_TECHNICAL_PREFILTER",
        "analysis_price": latest_price,
        "analysis_bid": None,
        "analysis_ask": None,
        "analysis_spread_pct": None,
        "analysis_quote_source": "OHLCV_TECHNICAL_PREFILTER",
        "analysis_quote_timestamp": scan_timestamp,
        "analysis_quote_freshness": "DELAYED_OR_EOD",
        "analysis_quote_confidence": "LOW" if latest_price is not None else "UNKNOWN",
        "secondary_data_sources_used": "",
        "secondary_data_notes": "ticker excluded from expensive enrichment by canonical technical assessment",
        "metadata_source": "NOT_REQUESTED_TECHNICAL_ASSESSMENT",
        "metadata_confidence": "UNKNOWN",
        "warnings": reason,
        "data_quality_score": 0.0,
        "data_quality_confidence": "LOW",
        "pre_veto_signal": "AVOID",
        "signal": "AVOID",
        "recommendation": "AVOID_FOR_NOW",
        "all_veto_reasons": "",
        "veto_reasons": "",
        "penalty_reasons": reason,
        "reason_summary": f"Canonical technical assessment: {reason}",
        "scenario_status": "NOT_SELECTED_FOR_DEEP_ANALYSIS",
        "scenario_confidence": "LOW",
        "scenario_operability": "DO_NOT_ADVANCE",
        "scenario_eligible_for_backtest": False,
        "scenario_guardrail_applied": True,
        "scenario_guardrail_reason": "technical_assessment_not_eligible",
        "momentum_state": momentum_state,
        "extension_state": prefilter.get("ema20_extension_status", "UNKNOWN"),
        "entry_timing_status": "NOT_OPERABLE",
        "required_confirmation": prefilter.get(
            "required_confirmations",
            "daily_and_weekly_macd_histogram_resume_rising",
        ),
        "required_confirmations": prefilter.get("required_confirmations"),
        "invalidation_conditions": prefilter.get("invalidation_conditions"),
        "invalidation_reason": reason,
        "engine_recommendation": "DO_NOT_ADVANCE",
        "engine_block_reason": "technical_assessment_not_eligible",
        "execution_readiness_status": "NOT_OPERABLE",
        "market_opportunity_status": "NO_CLEAN_EXECUTION",
        "operational_status": operational_status,
        "operational_readiness_score": 0.0,
        "operational_readiness_bucket": "BLOCKED",
        "operational_readiness_reason": reason,
        "scenario_quality_adjustment": 0.0,
        "timing_penalty_reason": reason if "ema20_extension" in reason else "",
        "momentum_penalty_reason": reason,
        **prefilter,
    }


def _evaluate_canonical_technical_opportunity(
    df: pd.DataFrame,
    config: dict,
    *,
    liquidity: dict,
    prefilter: dict,
) -> dict:
    # Some focused scanner tests replace the legacy prefilter with a compact
    # fixture. Preserve that contract while production uses complete evidence.
    if not prefilter.get("evidence_available") and prefilter.get("technical_close") is None:
        passed = str(prefilter.get("technical_prefilter_status") or "").upper() == "PASS"
        liquidity_passed = bool(
            liquidity.get("liquidity_core_pass", liquidity.get("liquidity_pass", False))
        )
        lane = (
            "ADVANCE_DEEP_ANALYSIS"
            if passed and liquidity_passed
            else "REJECT_RISK"
            if not liquidity_passed
            else "REJECT_MOMENTUM"
        )
        return {
            **prefilter,
            "technical_opportunity_score": 100.0 if passed else 0.0,
            "technical_analysis_lane": lane,
            "technical_eligibility_reason": (
                "legacy_prefilter_fixture_pass"
                if passed
                else str(prefilter.get("technical_prefilter_reason") or "legacy_prefilter_fixture_fail")
            ),
            "trend_setup_compatibility": "UNKNOWN",
            "momentum_gate_status": "PASS" if passed else "REJECT",
            "timing_gate_status": "UNKNOWN",
            "core_liquidity_status": "PASS" if liquidity_passed else "FAIL",
            "daily_macd_operable": passed,
            "weekly_macd_operable": passed,
            "technical_assessment_version": "LEGACY_FIXTURE_COMPAT",
        }
    return {
        **prefilter,
        **evaluate_technical_opportunity(
            df,
            config,
            liquidity=liquidity,
            evidence=prefilter,
        ),
    }


def _run_scan_impl(
    config: dict,
    max_candidates: int | None,
    performance: dict,
) -> pd.DataFrame:
    logger.info("Iniciando scanner Analista MVP.")

    # 1. Screener and first universe validation.
    stage_started = perf_counter()
    _stage_start(performance, "screener_and_initial_validation")
    screen = run_screeners(config)
    meta = validate_universe(screen.dataframe, config)

    if max_candidates:
        meta = meta.head(max_candidates)
    performance["counts"]["screener_rows"] = int(len(screen.dataframe))
    performance["counts"]["initial_universe_rows"] = int(len(meta))
    _stage_done(performance, "screener_and_initial_validation", stage_started)

    if meta.empty:
        logger.warning("No hay tickers tras screener/validación inicial.")
        return pd.DataFrame()

    # 2. Bulk prices before expensive metadata.
    tickers = meta["ticker"].dropna().astype(str).str.upper().unique().tolist()
    price_cfg = config.get("price_data", {})
    price_stats: dict = {}
    stage_started = perf_counter()
    _stage_start(performance, "bulk_price_download")

    def _price_progress(stats: dict) -> None:
        performance["current_stage"] = "bulk_price_download"
        performance["updated_at"] = datetime.now(timezone.utc).isoformat()
        performance["price_download"] = stats
        _write_scan_performance(performance)

    raw_prices = download_daily_prices(
        tickers,
        period=price_cfg.get("daily_period", "1y"),
        interval=price_cfg.get("daily_interval", "1d"),
        batch_size=int(price_cfg.get("batch_size", 150)),
        retry_batch_size=int(price_cfg.get("retry_batch_size", 50)),
        timeout_seconds=int(price_cfg.get("timeout_seconds", 15)),
        max_individual_fallbacks=int(price_cfg.get("max_individual_fallbacks", 10)),
        cache_dir=price_cfg.get("cache_dir", "cache/prices/daily"),
        cache_ttl_minutes=int(price_cfg.get("cache_ttl_minutes", 30)),
        max_stale_hours=int(price_cfg.get("max_stale_hours", 120)),
        stats=price_stats,
        progress_callback=_price_progress,
    )
    performance["price_download"] = price_stats
    _stage_done(performance, "bulk_price_download", stage_started)

    prices: dict[str, pd.DataFrame] = {}
    pre_liquidity_rows: list[dict] = []
    technical_prefilter_rows: dict[str, dict] = {}
    technical_assessment_rows: dict[str, dict] = {}
    price_history_reject_rows: list[dict] = []
    initial_meta_by_ticker = meta.set_index("ticker").to_dict(orient="index")
    scan_timestamp = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    base_rows: list[dict] = []
    price_cache_status = price_stats.get("cache_status_by_ticker", {})
    stale_price_tickers = set(price_stats.get("stale_fallback_tickers", []))

    # 3. Fast in-memory liquidity and technical funnel. Bid/ask is intentionally excluded here.
    stage_started = perf_counter()
    _stage_start(performance, "technical_preliquidity_prefilter")
    for ticker in tickers:
        df = raw_prices.get(ticker)

        if df is None or df.empty:
            logger.warning(f"Sin precios para {ticker}.")
            missing_assessment = {
                "technical_analysis_lane": "REJECT_RISK",
                "decision_lane": "DATA_BLOCKED",
                "decision_reasons": "price_history_missing",
                "technical_eligibility_reason": "price_history_missing",
                "technical_opportunity_score": 0.0,
                "technical_prefilter_status": "FAIL",
                "technical_prefilter_reason": "price_history_missing",
                "technical_prefilter_triage": "INSUFFICIENT_DATA",
                "daily_macd_trajectory_state": "UNKNOWN",
                "weekly_macd_trajectory_state": "UNKNOWN",
                "momentum_gate_status": "MONITOR",
                "timing_gate_status": "UNKNOWN",
                "core_liquidity_status": "FAIL",
                "daily_macd_operable": False,
                "weekly_macd_operable": False,
                "technical_assessment_version": "INSTITUTIONAL_OPPORTUNITY_V2",
            }
            price_history_reject_rows.append(
                _build_technical_prefilter_reject_row(
                    ticker=ticker,
                    source_meta=initial_meta_by_ticker.get(ticker, {}),
                    prefilter=missing_assessment,
                    liquidity={
                        "ticker": ticker,
                        "liquidity_core_pass": False,
                        "liquidity_pass": False,
                        "liquidity_score": 0.0,
                        "execution_spread_status": "NOT_EVALUATED",
                    },
                    scan_timestamp=scan_timestamp,
                )
            )
            continue

        technical_df, bar_metadata = derive_technical_prices(df)
        if technical_df.empty:
            logger.warning(f"Sin barras diarias cerradas para {ticker}.")
            technical_df = df.iloc[0:0].copy()
        ind = add_all_indicators(technical_df, config)
        prices[ticker] = ind
        liquidity = compute_liquidity(
            ticker,
            ind,
            config,
            metadata={},
        )
        prefilter = {
            **evaluate_technical_prefilter(ind),
            **bar_metadata,
            "ohlcv_cache_status": price_cache_status.get(ticker, "NETWORK"),
            "ohlcv_stale_fallback_used": ticker in stale_price_tickers,
        }
        technical_prefilter_rows[ticker] = prefilter
        assessment = _evaluate_canonical_technical_opportunity(
            ind,
            config,
            liquidity=liquidity,
            prefilter=prefilter,
        )
        technical_assessment_rows[ticker] = assessment
        pre_liquidity_rows.append({**liquidity, **assessment})

    pre_liquidity = pd.DataFrame(pre_liquidity_rows)

    if pre_liquidity.empty:
        logger.warning("No hay datos de liquidez; se conservan rechazos por historial.")
        return pd.DataFrame(price_history_reject_rows)

    liquid_mask = (
        pre_liquidity.get(
            "liquidity_core_pass",
            pre_liquidity.get("liquidity_pass", pd.Series(False, index=pre_liquidity.index)),
        )
        .fillna(False)
        .astype(bool)
    )
    technical_pass_mask = (
        pre_liquidity.get("technical_analysis_lane", pd.Series("", index=pre_liquidity.index))
        .fillna("")
        .astype(str)
        .str.upper()
        .isin({"ADVANCE_DEEP_ANALYSIS", "ADVANCE_RESEARCH_ANALYSIS"})
    )
    pre_liquid_tickers = set(pre_liquidity.loc[liquid_mask, "ticker"].astype(str))
    technical_pass_tickers = set(
        pre_liquidity.loc[technical_pass_mask, "ticker"].astype(str)
    )
    technical_reject_rows = price_history_reject_rows + [
        _build_technical_prefilter_reject_row(
            ticker=str(row.get("ticker")),
            source_meta=initial_meta_by_ticker.get(str(row.get("ticker")), {}),
            prefilter=technical_assessment_rows.get(str(row.get("ticker")), {}),
            liquidity=row.to_dict(),
            scan_timestamp=scan_timestamp,
        )
        for _, row in pre_liquidity.loc[~technical_pass_mask].iterrows()
    ]
    meta = meta[meta["ticker"].astype(str).isin(technical_pass_tickers)].copy()
    pre_metrics = pre_liquidity[
        pre_liquidity["ticker"].astype(str).isin(technical_pass_tickers)
    ].drop(columns=["structure", "rr_data"], errors="ignore").copy()
    meta = meta.drop(columns=["price"], errors="ignore").merge(pre_metrics, on="ticker", how="inner")
    prices = {ticker: frame for ticker, frame in prices.items() if ticker in technical_pass_tickers}
    performance["counts"]["price_history_rows"] = int(len(pre_liquidity))
    performance["counts"]["advance_price_rows"] = int(len(prices))
    performance["counts"]["ohlcv_available_rows"] = int(len(pre_liquidity))
    performance["counts"]["pre_liquidity_rows"] = int(len(pre_liquid_tickers))
    performance["counts"]["technical_prefilter_pass_rows"] = int(len(technical_pass_tickers))
    performance["counts"]["operational_analysis_rows"] = int(
        pre_liquidity["technical_analysis_lane"]
        .fillna("")
        .astype(str)
        .str.upper()
        .eq("ADVANCE_DEEP_ANALYSIS")
        .sum()
    )
    performance["counts"]["research_analysis_rows"] = int(
        pre_liquidity["technical_analysis_lane"]
        .fillna("")
        .astype(str)
        .str.upper()
        .eq("ADVANCE_RESEARCH_ANALYSIS")
        .sum()
    )
    performance["technical_bar_policy_counts"] = {
        "intraday_bar_excluded": int(
            pre_liquidity.get(
                "intraday_bar_excluded",
                pd.Series(False, index=pre_liquidity.index),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "daily_bar_complete": int(
            pre_liquidity.get(
                "daily_bar_complete",
                pd.Series(False, index=pre_liquidity.index),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "weekly_bar_complete": int(
            pre_liquidity.get(
                "weekly_bar_complete",
                pd.Series(False, index=pre_liquidity.index),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        ),
    }
    performance["counts"]["technical_prefilter_fail_rows"] = int(len(technical_reject_rows))
    performance["counts"]["setup_valid_before_metadata_rows"] = int(
        pre_liquidity.get("setup_type", pd.Series("", index=pre_liquidity.index))
        .fillna("")
        .astype(str)
        .str.upper()
        .isin(VALID_SETUP_TYPES | RADAR_SETUP_TYPES)
        .sum()
    )
    performance["counts"]["metadata_queries_avoided_by_technical_assessment"] = int(
        len(tickers) - len(technical_pass_tickers)
    )
    lane_counts = (
        pre_liquidity["technical_analysis_lane"].fillna("UNKNOWN").astype(str).value_counts().to_dict()
    )
    if price_history_reject_rows:
        lane_counts["REJECT_RISK"] = int(
            lane_counts.get("REJECT_RISK", 0) + len(price_history_reject_rows)
        )
    performance["technical_analysis_lane_counts"] = lane_counts
    performance["decision_lane_counts"] = (
        pre_liquidity.get("decision_lane", pd.Series(dtype=str))
        .fillna("UNKNOWN")
        .astype(str)
        .value_counts()
        .to_dict()
    )
    performance["counts"]["deep_analysis_operational_rows"] = int(
        lane_counts.get("ADVANCE_DEEP_ANALYSIS", 0)
    )
    performance["counts"]["deep_analysis_research_rows"] = int(
        lane_counts.get("ADVANCE_RESEARCH_ANALYSIS", 0)
    )
    performance["counts"]["rejected_risk_rows"] = int(
        lane_counts.get("REJECT_RISK", 0)
    )
    reason_counts = (
        pre_liquidity["technical_eligibility_reason"]
        .fillna("UNKNOWN")
        .astype(str)
        .value_counts()
        .to_dict()
    )
    if price_history_reject_rows:
        reason_counts["price_history_missing"] = int(len(price_history_reject_rows))
    performance["technical_eligibility_reason_counts"] = reason_counts
    performance["technical_evidence"] = {
        "calculated": int(len(pre_liquidity)),
        "unavailable": int(len(price_history_reject_rows)),
        "reused_for_scenario": 0,
        "assessment_version": "INSTITUTIONAL_OPPORTUNITY_V2",
    }
    performance["technical_prefilter_counts"] = {
        "technical_prefilter_status": pre_liquidity.get(
            "technical_prefilter_status",
            pd.Series(dtype=str),
        ).fillna("MISSING").astype(str).value_counts().to_dict(),
        "daily_macd_prefilter_status": pre_liquidity.get(
            "daily_macd_prefilter_status",
            pd.Series(dtype=str),
        ).fillna("MISSING").astype(str).value_counts().to_dict(),
        "weekly_macd_prefilter_status": pre_liquidity.get(
            "weekly_macd_prefilter_status",
            pd.Series(dtype=str),
        ).fillna("MISSING").astype(str).value_counts().to_dict(),
        "technical_prefilter_triage": pre_liquidity.get(
            "technical_prefilter_triage",
            pd.Series(dtype=str),
        ).fillna("MISSING").astype(str).value_counts().to_dict(),
        "ema20_extension_prefilter_status": pre_liquidity.get(
            "ema20_extension_prefilter_status",
            pd.Series(dtype=str),
        ).fillna("MISSING").astype(str).value_counts().to_dict(),
    }
    _stage_done(performance, "technical_preliquidity_prefilter", stage_started)

    if meta.empty:
        logger.warning("Todos los tickers fallaron preliquidez o prefiltro técnico.")
        return pd.DataFrame(technical_reject_rows)

    # 4. Expensive metadata/fundamentals only for liquid survivors.
    logger.info(
        "Enriqueciendo metadata para supervivientes de liquidez: "
        f"{len(meta)} tickers."
    )
    meta = meta.drop(
        columns=[
            "bid",
            "ask",
            "spread_pct",
            "bid_ask_valid",
            "bid_ask_warning",
            "spread_validated_pct",
            "quote_status",
            "execution_quote_quality",
        ],
        errors="ignore",
    )
    metadata_stats: dict = {}
    stage_started = perf_counter()
    _stage_start(performance, "metadata_and_fundamentals")

    def _metadata_progress(stats: dict) -> None:
        performance["current_stage"] = "metadata_and_fundamentals"
        performance["updated_at"] = datetime.now(timezone.utc).isoformat()
        performance["metadata_enrichment"] = stats
        _write_scan_performance(performance)

    try:
        meta = enrich_metadata(meta, config, stats=metadata_stats, progress_callback=_metadata_progress)
    except TypeError as exc:
        if "progress_callback" not in str(exc):
            raise
        meta = enrich_metadata(meta, config, stats=metadata_stats)
    performance["metadata_enrichment"] = metadata_stats
    _stage_done(performance, "metadata_and_fundamentals", stage_started)

    # 4b. Strict universe validation after enrichment.
    stage_started = perf_counter()
    _stage_start(performance, "strict_universe_validation")
    meta = validate_universe(meta, config, strict_metadata=True)
    performance["counts"]["post_metadata_rows"] = int(len(meta))
    _stage_done(performance, "strict_universe_validation", stage_started)
    if meta.empty:
        logger.warning("No hay tickers tras enriquecimiento y revalidación de universo.")
        return pd.DataFrame(technical_reject_rows)

    tickers = meta["ticker"].dropna().astype(str).str.upper().unique().tolist()
    logger.info(f"Tickers tras screener/liquidez/enriquecimiento: {len(tickers)}")

    # 5. Final liquidity/quote evaluation with enriched bid/ask.
    stage_started = perf_counter()
    _stage_start(performance, "final_quote_liquidity")
    meta_by_ticker = meta.set_index("ticker").to_dict(orient="index")
    final_liquidity_rows = [
        compute_liquidity(
            ticker,
            prices.get(ticker),
            config,
            metadata=meta_by_ticker.get(ticker, {}),
        )
        for ticker in tickers
        if prices.get(ticker) is not None and not prices[ticker].empty
    ]
    final_liquidity = pd.DataFrame(final_liquidity_rows)
    if final_liquidity.empty:
        logger.warning("No hay datos para validación final de liquidez y quote.")
        return pd.DataFrame(technical_reject_rows)
    liquidity_columns = [column for column in final_liquidity.columns if column != "ticker"]
    meta = meta.drop(columns=liquidity_columns, errors="ignore")
    meta = meta.merge(final_liquidity, on="ticker", how="inner")
    if "liquidity_core_pass" in meta.columns:
        meta = meta[meta["liquidity_core_pass"]].reset_index(drop=True)
    else:
        meta = meta[meta["liquidity_pass"]].reset_index(drop=True)
    tickers = meta["ticker"].dropna().astype(str).str.upper().tolist()
    prices = {ticker: frame for ticker, frame in prices.items() if ticker in set(tickers)}
    performance["counts"]["final_liquidity_rows"] = int(len(meta))
    _stage_done(performance, "final_quote_liquidity", stage_started)
    logger.info(f"Tickers tras liquidez: {len(tickers)}")

    if meta.empty:
        logger.warning("Todos los tickers fallaron liquidez.")
        return pd.DataFrame(technical_reject_rows)

    analysis_quote_fallbacks: dict[str, dict] = {}

    # 4. Market regime and sector rotation.
    stage_started = perf_counter()
    _stage_start(performance, "market_regime_context")
    regime = classify_market_regime(config)
    _stage_done(performance, "market_regime_context", stage_started)

    sector_df = calculate_sector_rotation(meta, prices)
    sector_context_cfg = config.get("sector_context", {})
    sector_context_df = pd.DataFrame()
    if sector_context_cfg.get("enabled", True):
        stage_started = perf_counter()
        _stage_start(performance, "sector_benchmark_context")
        sector_benchmark_symbols = sector_benchmark_symbols_for_meta(meta, config)
        sector_download_stats: dict = {}
        sector_prices: dict[str, pd.DataFrame] = {}
        if sector_benchmark_symbols:
            try:
                sector_prices = download_daily_prices(
                    sector_benchmark_symbols,
                    period=sector_context_cfg.get("daily_period", "1y"),
                    interval=sector_context_cfg.get("daily_interval", "1d"),
                    batch_size=int(sector_context_cfg.get("batch_size", 50)),
                    retry_batch_size=int(sector_context_cfg.get("retry_batch_size", 25)),
                    timeout_seconds=int(sector_context_cfg.get("timeout_seconds", 15)),
                    max_individual_fallbacks=int(sector_context_cfg.get("max_individual_fallbacks", 3)),
                    stats=sector_download_stats,
                )
            except Exception as exc:
                sector_download_stats["fatal_error"] = f"{type(exc).__name__}:{exc}"
                sector_prices = {}
        sector_prices = {
            symbol: derive_technical_prices(frame)[0]
            for symbol, frame in sector_prices.items()
            if frame is not None and not frame.empty
        }
        sector_context_df = calculate_sector_benchmark_context(
            meta,
            sector_prices,
            config,
            ticker_prices=prices,
        )
        performance["sector_benchmark_context"] = {
            "enabled": True,
            "benchmark_symbols": sector_benchmark_symbols,
            "downloaded_symbols": sorted(sector_prices.keys()),
            "source": "yfinance",
            "data_freshness": "DELAYED_OR_EOD",
            "state_counts": (
                sector_context_df["sector_weekly_macd_state"].value_counts(dropna=False).to_dict()
                if not sector_context_df.empty and "sector_weekly_macd_state" in sector_context_df.columns
                else {}
            ),
            "download_stats": sector_download_stats,
            "benchmarks_are_not_tradable_universe": True,
        }
        _stage_done(performance, "sector_benchmark_context", stage_started)

    if not sector_context_df.empty:
        sector_df = sector_df.merge(sector_context_df, on="ticker", how="left")
    sector_map = (
        sector_df.set_index("ticker").to_dict(orient="index")
        if not sector_df.empty
        else {}
    )

    # 5. First pass: returns for percentile RS.
    for _, m in meta.iterrows():
        ticker = m["ticker"]
        df = prices.get(ticker)

        if df is None or len(df) < 64:
            continue

        close_for_returns = df["adj_close"] if "adj_close" in df.columns else df["close"]
        ret20 = close_for_returns.iloc[-1] / close_for_returns.iloc[-21] - 1 if len(df) >= 21 else 0
        ret63 = close_for_returns.iloc[-1] / close_for_returns.iloc[-64] - 1 if len(df) >= 64 else ret20

        base_rows.append(
            {
                "ticker": ticker,
                "ret20": ret20,
                "ret63": ret63,
            }
        )

    base_rows = add_relative_strength_scores(base_rows)
    rs_map = {r["ticker"]: r.get("rs_score", 0.5) for r in base_rows}

    # 6. Build option-neutral scoring inputs from the canonical assessment.
    # Options remain context-only and are requested after scenario classification.
    options_enabled = config.get("options_flow", {}).get("enabled", False)
    max_options_tickers = config.get("options_flow", {}).get("max_tickers_per_run", 50)

    # Build an option-neutral candidate ranking before spending the network budget.
    # This prevents arbitrary universe order from consuming option queries on early VETO rows.
    stage_started = perf_counter()
    _stage_start(performance, "candidate_preparation_and_scenario")
    prepared: dict[str, dict] = {}
    selection_candidates: list[dict] = []
    for _, m in meta.iterrows():
        ticker = m["ticker"]
        df = prices.get(ticker)
        if df is None or df.empty:
            continue

        assessment = technical_assessment_rows.get(ticker, {})
        trend_score = float(assessment.get("trend_score", 0.0) or 0.0)
        trend_status = assessment.get("trend_status", "weak")
        volume_score = score_volume(df)
        structure = assessment.get("structure") or {
            "structure_score": 0.25,
            "setup_type": assessment.get("setup_type", "NO_VALID_SETUP"),
            "trigger_confirmed": assessment.get("trigger_confirmed", False),
            "trigger_level": assessment.get("trigger_level"),
        }
        rr_data = assessment.get("rr_data") or {}
        momentum_score = score_momentum(df, config)
        earnings_context = normalize_earnings_context(
            m.to_dict(),
            as_of=assessment.get("technical_as_of_date"),
            earnings_ttl_minutes=int(
                config.get("data_sources", {})
                .get("cache_ttl_minutes", {})
                .get("earnings", 720)
            ),
        )
        if earnings_context.get("earnings_event_status") == "RECENTLY_REPORTED":
            earnings_context.update(
                evaluate_post_earnings_stabilization(
                    df,
                    earnings_date=earnings_context.get("earnings_date"),
                    as_of=assessment.get("technical_as_of_date"),
                )
            )
            earnings_context = normalize_earnings_context(
                earnings_context,
                as_of=assessment.get("technical_as_of_date"),
                earnings_ttl_minutes=int(
                    config.get("data_sources", {})
                    .get("cache_ttl_minutes", {})
                    .get("earnings", 720)
                ),
            )
        fund = score_fundamentals(earnings_context, config)
        sector_info = sector_map.get(ticker, {})
        sector_score = float(sector_info.get("sector_score", 0.5) or 0.5)
        latest = df.iloc[-1]
        spot = _safe_float(latest.get("close"))

        neutral_scores = {
            "rs_score": float(rs_map.get(ticker, 0.5)),
            "trend_score": trend_score,
            "market_regime_score": regime.get("regime_score_norm", 0.5),
            "volume_score": volume_score,
            "sector_score": sector_score,
            "structure_score": structure.get("structure_score", 0.5),
            "rr_score": rr_data.get("rr_score", 0.0),
            "liquidity_score": float(m.get("liquidity_score", 0.5)),
            "momentum_score": momentum_score,
            "fundamental_score": fund.get("fundamental_score", 0.5),
            "options_score": 0.5,
            "sentiment_score": 0.5,
        }
        preliminary_final_score = calculate_final_score(neutral_scores, config)
        preliminary_trade_scores = calculate_trade_score_breakdown(
            neutral_scores,
            {
                "setup_type": structure.get("setup_type"),
                "trigger_confirmed": structure.get("trigger_confirmed", False),
            },
        )
        preliminary_row = {
            "final_score": preliminary_final_score,
            "rr": rr_data.get("rr"),
            "rr_status": rr_data.get("rr_status"),
            "trigger_confirmed": structure.get("trigger_confirmed", False),
            "price": spot,
            "market_cap": m.get("market_cap"),
            "quote_type": m.get("quote_type"),
            "liquidity_pass": bool(m.get("liquidity_pass", False)),
            "trend_score": trend_score,
            "setup_type": structure.get("setup_type"),
            "earnings_veto": fund.get("earnings_veto", False),
            "earnings_operability_block": fund.get(
                "earnings_operability_block",
                False,
            ),
            "quote_status": m.get("quote_status"),
            "execution_quote_quality": m.get("execution_quote_quality"),
            "universe_veto_reasons": m.get("universe_veto_reasons"),
            "technical_analysis_lane": assessment.get("technical_analysis_lane"),
        }
        preliminary_signal, _ = classify_signal(preliminary_row, config)

        prepared[ticker] = {
            "trend_score": trend_score,
            "trend_status": trend_status,
            "volume_score": volume_score,
            "structure": structure,
            "rr_data": rr_data,
            "momentum_score": momentum_score,
            "fund": fund,
            "sector_info": sector_info,
            "sector_score": sector_score,
            "latest": latest,
            "spot": spot,
            "technical_assessment": assessment,
        }
        selection_candidates.append(
            {
                "ticker": ticker,
                "spot": spot,
                "preliminary_signal": preliminary_signal,
                "preliminary_trade_score": preliminary_trade_scores.get("final_trade_score", 0.0),
                "preliminary_final_score": preliminary_final_score,
                "setup_type": structure.get("setup_type"),
                "liquidity_pass": bool(m.get("liquidity_pass", False)),
                "earnings_veto": fund.get("earnings_veto", False),
                "earnings_operability_block": fund.get(
                    "earnings_operability_block",
                    False,
                ),
                "rr": rr_data.get("rr"),
                "quote_status": m.get("quote_status"),
                "execution_quote_quality": m.get("execution_quote_quality"),
                "sector": m.get("sector") or sector_info.get("sector"),
                "trend_score": trend_score,
                "momentum_score": momentum_score,
                "liquidity_score": float(m.get("liquidity_score", 0.5)),
                "source_quality_score": float(m.get("source_quality_score", 0.5) or 0.5),
                "liquidity_core_pass": bool(
                    m.get("liquidity_core_pass", m.get("liquidity_pass", False))
                ),
                "technical_analysis_lane": assessment.get("technical_analysis_lane"),
                "technical_opportunity_score": assessment.get("technical_opportunity_score"),
            }
        )

    funnel_cfg = config.get("deep_analysis", {}).get("candidate_funnel", {})
    deep_analysis_tickers, deep_analysis_audit = select_deep_analysis_candidates(
        selection_candidates,
        target_tickers=int(funnel_cfg.get("target_tickers", 50)),
        min_tickers=int(funnel_cfg.get("min_tickers", 40)),
        max_tickers=int(funnel_cfg.get("max_tickers", 60)),
        max_sector_share=float(funnel_cfg.get("max_sector_share", 0.20)),
    )
    deep_analysis_set = set(deep_analysis_tickers)
    performance["counts"]["deep_analysis_rows"] = int(len(deep_analysis_tickers))

    scenario_by_ticker: dict[str, dict] = {}
    for ticker in deep_analysis_tickers:
        prepared_row = prepared.get(ticker, {})
        assessment = prepared_row.get("technical_assessment") or {}
        structure = prepared_row.get("structure") or {}
        scenario_setup_type = _scenario_setup_type(assessment, structure)
        scenario_by_ticker[ticker] = analyze_scenario(
            prices.get(ticker),
            setup_type=scenario_setup_type,
            trigger_level=structure.get("trigger_level"),
            market_regime=regime.get("regime", ""),
            selected=True,
            technical_evidence={
                key: value
                for key, value in assessment.items()
                if key not in {"structure", "rr_data"}
            },
        )
    performance["technical_evidence"]["reused_for_scenario"] = int(
        len(scenario_by_ticker)
    )
    _stage_done(performance, "candidate_preparation_and_scenario", stage_started)

    review_scenario_tickers = {
        ticker
        for ticker, scenario in scenario_by_ticker.items()
        if str(scenario.get("scenario_status") or "").upper()
        in {"VALID_TRIGGER", "WAIT_FOR_CONFIRMATION"}
        and str(
            prepared.get(ticker, {})
            .get("technical_assessment", {})
            .get("technical_analysis_lane")
            or ""
        ).upper()
        == "ADVANCE_DEEP_ANALYSIS"
        and not bool(prepared.get(ticker, {}).get("fund", {}).get("earnings_veto", False))
    }
    stage_started = perf_counter()
    _stage_start(performance, "analysis_quote_fallbacks")
    quote_candidate_rows = [
        row
        for row in meta.to_dict(orient="records")
        if str(row.get("ticker")) in review_scenario_tickers
    ]
    analysis_quote_tickers = select_analysis_quote_fallback_tickers(quote_candidate_rows)
    analysis_quote_fallbacks = build_analysis_quote_fallbacks(analysis_quote_tickers, config)
    analysis_quote_source_counts: dict[str, int] = {}
    for quote in analysis_quote_fallbacks.values():
        source = str(quote.get("analysis_quote_source") or "UNKNOWN")
        analysis_quote_source_counts[source] = analysis_quote_source_counts.get(source, 0) + 1
    performance["analysis_quote_fallbacks"] = {
        "eligible_after_scenario": int(len(review_scenario_tickers)),
        "requested_tickers": int(len(analysis_quote_tickers)),
        "returned_tickers": int(len(analysis_quote_fallbacks)),
        "skipped_before_network": int(
            max(len(deep_analysis_tickers) - len(analysis_quote_tickers), 0)
        ),
        "source_counts": analysis_quote_source_counts,
        "execution_fields_unchanged": True,
    }
    _stage_done(performance, "analysis_quote_fallbacks", stage_started)

    stage_started = perf_counter()
    _stage_start(performance, "options_context_queries")
    options_selection_candidates = [
        {
            **row,
            "scenario_status": scenario_by_ticker.get(
                str(row.get("ticker")),
                {},
            ).get("scenario_status"),
        }
        for row in selection_candidates
        if row.get("ticker") in deep_analysis_set
    ]
    selected_options_tickers, options_selection_audit = select_options_tickers(
        options_selection_candidates,
        max_tickers=min(max_options_tickers, len(deep_analysis_tickers)) if options_enabled else 0,
    )
    selected_options_set = set(selected_options_tickers)
    options_metrics_by_ticker: dict[str, dict] = {}
    if options_enabled:
        for ticker in selected_options_tickers:
            spot = prepared.get(ticker, {}).get("spot")
            if spot is not None:
                options_metrics_by_ticker[ticker] = fetch_options_metrics(ticker, spot, config)
    performance["options_queries"] = {
        "eligible_after_scenario": int(len(selected_options_tickers)),
        "requested": int(len(options_metrics_by_ticker)),
        "skipped_after_scenario": int(
            max(len(deep_analysis_tickers) - len(selected_options_tickers), 0)
        ),
        "max_tickers_safety_cap": int(max_options_tickers),
        "context_only_not_scored": True,
    }
    _stage_done(performance, "options_context_queries", stage_started)

    # 7. Full scoring pass.
    scan_timestamp = datetime.now(timezone.utc).isoformat()

    stage_started = perf_counter()
    _stage_start(performance, "final_scoring_and_guardrails")
    rows: list[dict] = []

    for _, m in meta.iterrows():
        ticker = m["ticker"]
        df = prices.get(ticker)

        if df is None or df.empty:
            continue

        prepared_row = prepared[ticker]
        trend_score = prepared_row["trend_score"]
        trend_status = prepared_row["trend_status"]
        volume_score = prepared_row["volume_score"]
        structure = prepared_row["structure"]
        rr_data = prepared_row["rr_data"]
        momentum_score = prepared_row["momentum_score"]
        fund = prepared_row["fund"]
        sector_info = prepared_row["sector_info"]
        sector_score = prepared_row["sector_score"]
        latest = prepared_row["latest"]
        spot = prepared_row["spot"]
        deep_selected = ticker in deep_analysis_set
        assessment = prepared_row.get("technical_assessment") or {}
        scenario_setup_type = _scenario_setup_type(assessment, structure)
        research_diagnostic = (
            str(assessment.get("technical_analysis_lane") or "").upper()
            == "ADVANCE_RESEARCH_ANALYSIS"
        )
        scenario = scenario_by_ticker.get(ticker) or analyze_scenario(
            df,
            setup_type=scenario_setup_type,
            trigger_level=structure.get("trigger_level"),
            market_regime=regime.get("regime", ""),
            selected=deep_selected,
            technical_evidence={
                key: value
                for key, value in (prepared_row.get("technical_assessment") or {}).items()
                if key not in {"structure", "rr_data"}
            },
        )
        shadow_levels = calculate_shadow_levels(
            df,
            scenario=scenario,
            setup_type=scenario_setup_type,
            rr_data=(
                assessment.get("research_rr_data") or rr_data
                if research_diagnostic
                else rr_data
            ),
            config=config,
            diagnostic_only=research_diagnostic,
        )

        if ticker in options_metrics_by_ticker:
            options_metrics = options_metrics_by_ticker[ticker]
            options_score_data = score_options_flow(options_metrics, spot, config)
        else:
            scenario_status = str(scenario.get("scenario_status") or "").upper()
            if not options_enabled:
                selection_error = "options_flow_disabled"
            elif not deep_selected:
                selection_error = "not_selected_for_deep_analysis"
            elif bool(fund.get("earnings_veto", False)):
                selection_error = "blocked_by_earnings"
            elif scenario_status not in {"VALID_TRIGGER", "WAIT_FOR_CONFIRMATION"}:
                selection_error = "scenario_not_eligible_for_options"
            elif ticker not in selected_options_set:
                selection_error = "not_selected_by_safety_cap"
            else:
                selection_error = "missing_spot"
            options_metrics = {
                "options_data_available": False,
                "options_available": False,
                "options_source": "disabled_or_limit",
                "options_error": selection_error,
                "options_warning": f"options flow no consultado: {selection_error}",
                "options_notes": f"options flow no consultado: {selection_error}",
            }
            options_score_data = score_options_flow(options_metrics, spot, config)

        if options_metrics.get("options_data_available") is True:
            options_coverage_status = "AVAILABLE"
        elif options_metrics.get("options_error") == "not_selected_by_safety_cap":
            options_coverage_status = "NOT_SELECTED_BY_SAFETY_CAP"
        elif options_metrics.get("options_error") == "no_options_listed":
            options_coverage_status = "NO_OPTIONS_AVAILABLE"
        else:
            options_coverage_status = "SOURCE_ERROR_OR_MISSING"

        options_adjustment_data = calculate_options_score_adjustment(options_score_data, config)
        options_score_data = {
            **options_score_data,
            **options_adjustment_data,
            "options_score": options_adjustment_data.get(
                "options_score_adjusted",
                options_score_data.get("options_score", 0.5),
            ),
        }

        scores = {
            "rs_score": float(rs_map.get(ticker, 0.5)),
            "trend_score": trend_score,
            "market_regime_score": regime.get("regime_score_norm", 0.5),
            "volume_score": volume_score,
            "sector_score": sector_score,
            "structure_score": structure.get("structure_score", 0.5),
            "rr_score": rr_data.get("rr_score", 0.0),
            "liquidity_score": float(m.get("liquidity_score", 0.5)),
            "momentum_score": momentum_score,
            "fundamental_score": fund.get("fundamental_score", 0.5),
            "options_score": 0.5,
            "options_score_adjustment": options_score_data.get("options_score_adjustment", 0.0),
            "options_score_reason": options_score_data.get("options_score_reason", ""),
            "options_contrarian_adjustment": options_score_data.get("options_contrarian_adjustment", 0.0),
            "options_contrarian_reason": options_score_data.get("options_contrarian_reason", ""),
            "options_risk_flag": options_score_data.get("options_risk_flag", ""),
            "sentiment_score": 0.5,
        }

        final_score = calculate_final_score(scores, config)

        trade_scores = calculate_trade_score_breakdown(
            scores,
            {
                "setup_type": structure.get("setup_type"),
                "trigger_confirmed": structure.get("trigger_confirmed", False),
            },
        )

        row = {
            "scan_timestamp": scan_timestamp,
            "ticker": ticker,
            "company": m.get("company"),
            "exchange": m.get("exchange"),
            "quote_type": m.get("quote_type"),
            "country": m.get("country"),
            "sector": m.get("sector") or sector_info.get("sector"),
            "industry": m.get("industry"),
            "market_cap": m.get("market_cap"),
            "market_regime": regime.get("regime"),
            "macro_context_status": regime.get("macro_context_status"),
            "macro_risk_flag": regime.get("macro_risk_flag"),
            "macro_notes": regime.get("macro_notes"),
            "macro_source": regime.get("macro_source"),
            "macro_timestamp": regime.get("macro_timestamp"),
            "macro_data_freshness": regime.get("macro_data_freshness"),
            "final_score": round(final_score, 2),
            "asset_attractiveness_score": trade_scores["asset_quality_score"],
            "asset_quality_score": trade_scores["asset_quality_score"],
            "setup_quality_score": trade_scores["setup_quality_score"],
            "context_score": trade_scores["context_score"],
            "institutional_score": trade_scores["institutional_score"],
            "final_trade_score": trade_scores["final_trade_score"],
            "score_breakdown": trade_scores["score_breakdown_json"],
            "deep_analysis_selected": deep_selected,
            "deep_analysis_tier": deep_analysis_audit.get(ticker, {}).get(
                "deep_analysis_tier",
                assessment.get("deep_analysis_tier", "NONE"),
            ),
            "deep_analysis_rank": deep_analysis_audit.get(ticker, {}).get("deep_analysis_rank"),
            "deep_analysis_score": deep_analysis_audit.get(ticker, {}).get("deep_analysis_score"),
            "deep_analysis_reason": deep_analysis_audit.get(ticker, {}).get(
                "deep_analysis_reason",
                "outside_deep_analysis_budget",
            ),
            "technical_opportunity_score": prepared_row.get(
                "technical_assessment",
                {},
            ).get("technical_opportunity_score"),
            "decision_lane": assessment.get("decision_lane"),
            "decision_reasons": assessment.get("decision_reasons"),
            "technical_asset_quality_score": assessment.get(
                "technical_asset_quality_score"
            ),
            "entry_readiness_score": assessment.get("entry_readiness_score"),
            "research_priority_score": assessment.get("research_priority_score"),
            "reset_watch_score": assessment.get("reset_watch_score"),
            "context_confidence_score": assessment.get("context_confidence_score"),
            "data_confidence_score": assessment.get("data_confidence_score"),
            "technical_analysis_lane": prepared_row.get(
                "technical_assessment",
                {},
            ).get("technical_analysis_lane"),
            "operational_eligibility": assessment.get("operational_eligibility", False),
            "research_eligibility_reason": assessment.get("research_eligibility_reason", ""),
            "research_setup_type": assessment.get("research_setup_type"),
            "scenario_setup_type": scenario_setup_type,
            "setup_readiness_score": assessment.get("setup_readiness_score"),
            "setup_readiness_state": assessment.get("setup_readiness_state"),
            "setup_candidate_type": assessment.get("setup_candidate_type"),
            "setup_readiness_reason": assessment.get("setup_readiness_reason"),
            "setup_readiness_components": assessment.get("setup_readiness_components"),
            "primary_setup_hypothesis": assessment.get("primary_setup_hypothesis"),
            "primary_setup_hypothesis_state": assessment.get(
                "primary_setup_hypothesis_state"
            ),
            "primary_setup_hypothesis_score": assessment.get(
                "primary_setup_hypothesis_score"
            ),
            "alternative_setup_hypotheses": assessment.get(
                "alternative_setup_hypotheses"
            ),
            "setup_hypotheses": assessment.get("setup_hypotheses"),
            "setup_hypothesis_count": assessment.get("setup_hypothesis_count"),
            "ema20_caution_mild": assessment.get("ema20_caution_mild", False),
            "ema20_distance_percentile_1y": assessment.get(
                "ema20_distance_percentile_1y"
            ),
            "ema20_extension_model": assessment.get("ema20_extension_model"),
            "trend_transition_score": assessment.get("trend_transition_score"),
            "trend_transition_state": assessment.get("trend_transition_state"),
            "trend_transition_reason": assessment.get("trend_transition_reason"),
            "technical_eligibility_reason": prepared_row.get(
                "technical_assessment",
                {},
            ).get("technical_eligibility_reason"),
            "trend_setup_compatibility": prepared_row.get(
                "technical_assessment",
                {},
            ).get("trend_setup_compatibility"),
            "trend_setup_compatibility_reason": prepared_row.get(
                "technical_assessment",
                {},
            ).get("trend_setup_compatibility_reason"),
            "research_trend_compatibility": assessment.get(
                "research_trend_compatibility"
            ),
            "research_trend_compatibility_reason": assessment.get(
                "research_trend_compatibility_reason"
            ),
            "momentum_gate_status": prepared_row.get(
                "technical_assessment",
                {},
            ).get("momentum_gate_status"),
            "timing_gate_status": prepared_row.get(
                "technical_assessment",
                {},
            ).get("timing_gate_status"),
            "core_liquidity_status": prepared_row.get(
                "technical_assessment",
                {},
            ).get("core_liquidity_status"),
            "daily_macd_operable": prepared_row.get(
                "technical_assessment",
                {},
            ).get("daily_macd_operable"),
            "weekly_macd_operable": prepared_row.get(
                "technical_assessment",
                {},
            ).get("weekly_macd_operable"),
            "technical_assessment_version": prepared_row.get(
                "technical_assessment",
                {},
            ).get("technical_assessment_version"),
            "technical_as_of_date": assessment.get("technical_as_of_date"),
            "technical_bar_policy": assessment.get("technical_bar_policy"),
            "daily_bar_complete": assessment.get("daily_bar_complete"),
            "weekly_bar_complete": assessment.get("weekly_bar_complete"),
            "intraday_bar_excluded": assessment.get("intraday_bar_excluded"),
            "technical_prefilter_status": m.get("technical_prefilter_status"),
            "technical_prefilter_reason": m.get("technical_prefilter_reason"),
            "daily_macd_prefilter_status": m.get("daily_macd_prefilter_status"),
            "weekly_macd_prefilter_status": m.get("weekly_macd_prefilter_status"),
            "technical_prefilter_triage": m.get("technical_prefilter_triage"),
            "daily_macd_trajectory_state": m.get("daily_macd_trajectory_state"),
            "weekly_macd_trajectory_state": m.get("weekly_macd_trajectory_state"),
            "daily_macd_non_decelerating": m.get("daily_macd_non_decelerating"),
            "weekly_macd_non_decelerating": m.get("weekly_macd_non_decelerating"),
            "ema20_extension_prefilter_status": m.get("ema20_extension_prefilter_status"),
            "ema20_extension_reference_source": m.get("ema20_extension_reference_source"),
            "technical_prefilter_guardrail": m.get("technical_prefilter_guardrail"),
            "rs_score": round(scores["rs_score"], 3),
            "trend_score": round(trend_score, 3),
            "trend_status": trend_status,
            "volume_score": round(volume_score, 3),
            "sector_score": round(sector_score, 3),
            "sector_benchmark_symbol": sector_info.get("sector_benchmark_symbol"),
            "sector_weekly_macd_hist": sector_info.get("sector_weekly_macd_hist"),
            "sector_weekly_macd_slope_1w": sector_info.get("sector_weekly_macd_slope_1w"),
            "sector_weekly_macd_prev_slope_1w": sector_info.get("sector_weekly_macd_prev_slope_1w"),
            "sector_weekly_macd_acceleration": sector_info.get("sector_weekly_macd_acceleration"),
            "sector_weekly_macd_state": sector_info.get("sector_weekly_macd_state"),
            "sector_weekly_macd_acceleration_state": sector_info.get(
                "sector_weekly_macd_acceleration_state"
            ),
            "sector_context_status": sector_info.get("sector_context_status"),
            "sector_context_reason": sector_info.get("sector_context_reason"),
            "sector_relative_return_20d": sector_info.get("sector_relative_return_20d"),
            "sector_relative_return_60d": sector_info.get("sector_relative_return_60d"),
            "sector_relative_line_slope_20d": sector_info.get("sector_relative_line_slope_20d"),
            "sector_relative_strength_score": sector_info.get("sector_relative_strength_score"),
            "sector_relative_leadership_status": sector_info.get(
                "sector_relative_leadership_status"
            ),
            "structure_score": round(structure.get("structure_score", 0.5), 3),
            "rr_score": round(rr_data.get("rr_score", 0.0), 3),
            "liquidity_pass": bool(
                m.get("liquidity_core_pass", m.get("liquidity_pass", False))
            ),
            "liquidity_core_pass": bool(
                m.get("liquidity_core_pass", m.get("liquidity_pass", False))
            ),
            "execution_spread_status": m.get("execution_spread_status"),
            "execution_spread_score": m.get("execution_spread_score"),
            "liquidity_score": round(float(m.get("liquidity_score", 0.5)), 3),
            "momentum_score": round(momentum_score, 3),
            "fundamental_score": fund.get("fundamental_score", 0.5),
            "options_score": options_score_data.get("options_score", 0.5),
            "options_score_raw": options_score_data.get("options_score_raw"),
            "options_score_adjustment": options_score_data.get("options_score_adjustment", 0.0),
            "options_score_reason": options_score_data.get("options_score_reason", ""),
            "options_contrarian_adjustment": options_score_data.get("options_contrarian_adjustment", 0.0),
            "options_contrarian_reason": options_score_data.get("options_contrarian_reason", ""),
            "options_risk_flag": options_score_data.get("options_risk_flag", ""),
            "options_bias": options_score_data.get("options_bias"),
            "options_confidence": options_score_data.get("options_confidence"),
            "options_crowded_bullish": options_score_data.get("options_crowded_bullish", False),
            "options_crowded_bearish": options_score_data.get("options_crowded_bearish", False),
            "options_liquidity_score": options_score_data.get("options_liquidity_score"),
            "options_notes": options_score_data.get("options_notes") or options_metrics.get("options_notes"),
            "options_coverage_status": options_coverage_status,
            "options_priority_selected": ticker in selected_options_set,
            "options_priority_rank": options_selection_audit.get(ticker, {}).get("options_priority_rank"),
            "options_priority_reason": options_selection_audit.get(ticker, {}).get(
                "options_priority_reason",
                "not_selected_by_priority_budget",
            ),
            "options_preliminary_signal": options_selection_audit.get(ticker, {}).get(
                "options_preliminary_signal"
            ),
            "options_preliminary_trade_score": options_selection_audit.get(ticker, {}).get(
                "options_preliminary_trade_score"
            ),
            "setup_type": structure.get("setup_type"),
            "trigger_confirmed": structure.get("trigger_confirmed", False),
            "trigger_level": structure.get("trigger_level"),
            "entry": rr_data.get("entry"),
            "stop": rr_data.get("stop"),
            "target": rr_data.get("target"), 
            "rr": rr_data.get("rr"),
            "rr_valid": rr_data.get("rr_valid", assessment.get("rr_valid")),
            "rr_status": rr_data.get("rr_status", assessment.get("rr_status")),
            "rr_confidence": rr_data.get("rr_confidence", assessment.get("rr_confidence")),
            "target_validation_source": rr_data.get(
                "target_validation_source",
                assessment.get("target_validation_source"),
            ),
            "target_validation_sources": rr_data.get(
                "target_validation_sources",
                assessment.get("target_validation_sources"),
            ),
            "target_candidates": rr_data.get(
                "target_candidates",
                assessment.get("target_candidates"),
            ),
            "entry_zone_low": assessment.get("entry_zone_low"),
            "entry_zone_high": assessment.get("entry_zone_high"),
            "required_confirmations": assessment.get("required_confirmations"),
            "invalidation_conditions": assessment.get("invalidation_conditions"),
            "theoretical_entry": rr_data.get("entry"),
            "theoretical_stop": rr_data.get("stop"),
            "theoretical_target": rr_data.get("target"),
            "actionable_entry": rr_data.get("entry"),
            "actionable_stop": rr_data.get("stop"),
            "actionable_target": rr_data.get("target"),
            "scenario_entry": (
                float(latest.get("high")) * 1.001
                if deep_selected
                and scenario.get("scenario_status") in {"VALID_TRIGGER", "WAIT_FOR_CONFIRMATION"}
                and structure.get("setup_type") in {"PULLBACK", "RECLAIM"}
                else rr_data.get("entry")
            ),
            "scenario_stop": rr_data.get("stop"),
            "scenario_target": rr_data.get("target"),
            **shadow_levels,
	        "stop_method": rr_data.get("stop_method"),
            "target_method": rr_data.get("target_method"),
            "risk_pct": rr_data.get("risk_pct"),
            "reward_pct": rr_data.get("reward_pct"),
            "atr": rr_data.get("atr"),
            "atr_pct": latest.get("atr_pct"),
            "stop_atr_multiple": rr_data.get("stop_atr_multiple"),
            "stop_atr_status": rr_data.get("stop_atr_status"),
            "rr_stressed": rr_data.get("rr_stressed"),
            "risk_geometry_status": rr_data.get("risk_geometry_status"),
            "risk_geometry_reason": rr_data.get("risk_geometry_reason"),
            "relative_volume": latest.get("relative_volume"),
            "price": latest.get("close"),
            "adjusted_close": latest.get("adj_close"),
            "price_adjustment_factor": latest.get("adj_factor"),
            "technical_price_basis": "ADJUSTED_OHLC" if "adj_close" in latest.index else "RAW_OHLC",
            "avg_volume_20d": m.get("avg_volume_20d"),
            "avg_volume_60d": m.get("avg_volume_60d"),
            "median_volume_20d": m.get("median_volume_20d"),
            "mean_volume_20d": m.get("mean_volume_20d"),
            "dollar_volume_20d": m.get("dollar_volume_20d"),
            "dollar_volume_60d": m.get("dollar_volume_60d"),
            "liquidity_turnover_20d": m.get("liquidity_turnover_20d"),
            "liquidity_turnover_60d": m.get("liquidity_turnover_60d"),
            "liquidity_market_cap_tier": m.get("liquidity_market_cap_tier"),
            "liquidity_required_turnover_20d": m.get("liquidity_required_turnover_20d"),
            "liquidity_required_turnover_60d": m.get("liquidity_required_turnover_60d"),
            "liquidity_formula_pass_20d": m.get("liquidity_formula_pass_20d"),
            "liquidity_formula_pass_60d": m.get("liquidity_formula_pass_60d"),
            "liquidity_dollar_pass_20d": m.get("liquidity_dollar_pass_20d"),
            "liquidity_dollar_pass_60d": m.get("liquidity_dollar_pass_60d"),
            "liquidity_core_pass": m.get("liquidity_core_pass"),
            "liquidity_spread_pass": m.get("liquidity_spread_pass"),
            "median_to_mean_volume_ratio": m.get("median_to_mean_volume_ratio"),
            "spread_pct": m.get("spread_pct"),
            "bid": m.get("bid"),
            "ask": m.get("ask"),
            "bid_ask_valid": m.get("bid_ask_valid"),
            "bid_ask_warning": m.get("bid_ask_warning"),
            "spread_validated_pct": m.get("spread_validated_pct"),
            "quote_status": m.get("quote_status"),
            "execution_quote_quality": m.get("execution_quote_quality"),
            "quote_source": m.get("quote_source"),
            "analysis_price": latest.get("close"),
            "analysis_bid": m.get("bid"),
            "analysis_ask": m.get("ask"),
            "analysis_spread_pct": m.get("spread_pct") or m.get("spread_validated_pct"),
            "analysis_quote_source": m.get("quote_source") or "yfinance",
            "analysis_quote_timestamp": scan_timestamp,
            "analysis_quote_freshness": "UNKNOWN",
            "analysis_quote_confidence": "UNKNOWN",
            "secondary_data_sources_used": "",
            "secondary_data_notes": (
                "analysis quote fields mirror scanner quote data; "
                "secondary providers are audited read-only before scanner fallback use"
            ),
            "metadata_source": m.get("metadata_source"),
            "sector_source": m.get("sector_source"),
            "industry_source": m.get("industry_source"),
            "market_cap_source": m.get("market_cap_source"),
            "earnings_source": m.get("earnings_source"),
            "metadata_fallback_used": m.get("metadata_fallback_used"),
            "metadata_fallback_sources": m.get("metadata_fallback_sources"),
            "metadata_fallback_notes": m.get("metadata_fallback_notes"),
            "metadata_confidence": m.get("metadata_confidence"),
            "fundamentals_cache_status": m.get("fundamentals_cache_status"),
            "fundamentals_cache_age_minutes": m.get("fundamentals_cache_age_minutes"),
            "earnings_cache_status": m.get("earnings_cache_status"),
            "earnings_cache_age_minutes": m.get("earnings_cache_age_minutes"),
            "average_volume_yf": m.get("average_volume_yf"),
            "average_volume_10d_yf": m.get("average_volume_10d_yf"),
            "regular_market_volume_yf": m.get("regular_market_volume_yf"),
            "earnings_date": fund.get("earnings_date"),
            "days_to_earnings": fund.get("days_to_earnings"),
            "earnings_veto": fund.get("earnings_veto"),
            "earnings_penalty": fund.get("earnings_penalty"),
            "earnings_as_of_date": fund.get("earnings_as_of_date"),
            "earnings_event_status": fund.get("earnings_event_status"),
            "earnings_data_confidence": fund.get("earnings_data_confidence"),
            "earnings_days_recomputed": fund.get("earnings_days_recomputed"),
            "earnings_refresh_required": fund.get("earnings_refresh_required"),
            "earnings_operability_block": fund.get(
                "earnings_operability_block"
            ),
            "earnings_review_reason": fund.get("earnings_review_reason"),
            "earnings_consistency_status": fund.get(
                "earnings_consistency_status"
            ),
            "post_earnings_stabilization_score": fund.get(
                "post_earnings_stabilization_score"
            ),
            "post_earnings_stabilization_status": fund.get(
                "post_earnings_stabilization_status"
            ),
            "post_earnings_closed_bars": fund.get(
                "post_earnings_closed_bars"
            ),
            "post_earnings_gap_atr": fund.get("post_earnings_gap_atr"),
            "post_earnings_range_atr": fund.get("post_earnings_range_atr"),
            "post_earnings_close_location": fund.get(
                "post_earnings_close_location"
            ),
            "post_earnings_stabilization_reason": fund.get(
                "post_earnings_stabilization_reason"
            ),
            "revenue_growth": fund.get("revenue_growth"),
            "earnings_growth": fund.get("earnings_growth"),
            "operating_margins": fund.get("operating_margins"),
            "profit_margins": fund.get("profit_margins"),
            "debt_to_equity": fund.get("debt_to_equity"),
            "return_on_equity": fund.get("return_on_equity"),
            "gross_margins": m.get("gross_margins"),
            "return_on_assets": m.get("return_on_assets"),
            "trailing_pe": m.get("trailing_pe"),
            "forward_pe": m.get("forward_pe"),
            "price_to_book": m.get("price_to_book"),
            "price_to_sales_ttm": m.get("price_to_sales_ttm"),
            "enterprise_to_ebitda": m.get("enterprise_to_ebitda"),
            "short_percent_float": m.get("short_percent_float"),
            "short_ratio": m.get("short_ratio"),
            "held_percent_institutions": m.get("held_percent_institutions"),
            "options_data_available": options_metrics.get("options_data_available"),
            "options_available": options_metrics.get(
                "options_available",
                options_metrics.get("options_data_available"),
            ),
            "options_source": options_metrics.get("options_source"),
            "options_error": options_metrics.get("options_error"),
            "options_expirations_used": options_metrics.get("options_expirations_used"),
            "options_expiration_used": options_metrics.get(
                "options_expiration_used",
                options_metrics.get("options_expirations_used"),
            ),
            "call_volume": options_metrics.get("call_volume"),
            "put_volume": options_metrics.get("put_volume"),
            "call_open_interest": options_metrics.get("call_open_interest"),
            "put_open_interest": options_metrics.get("put_open_interest"),
            "options_total_call_oi": options_metrics.get(
                "options_total_call_oi",
                options_metrics.get("call_open_interest"),
            ),
            "options_total_put_oi": options_metrics.get(
                "options_total_put_oi",
                options_metrics.get("put_open_interest"),
            ),
            "put_call_volume_ratio": options_metrics.get("put_call_volume_ratio"),
            "put_call_oi_ratio": options_metrics.get("put_call_oi_ratio"),
            "options_put_call_oi_ratio": options_metrics.get(
                "options_put_call_oi_ratio",
                options_metrics.get("put_call_oi_ratio"),
            ),
            "call_volume_share": options_metrics.get("call_volume_share"),
            "call_oi_share": options_metrics.get("call_oi_share"),
            "near_call_volume": options_metrics.get("near_call_volume"),
            "near_put_volume": options_metrics.get("near_put_volume"),
            "near_call_open_interest": options_metrics.get("near_call_open_interest"),
            "near_put_open_interest": options_metrics.get("near_put_open_interest"),
            "options_near_price_call_oi": options_metrics.get(
                "options_near_price_call_oi",
                options_metrics.get("near_call_open_interest"),
            ),
            "options_near_price_put_oi": options_metrics.get(
                "options_near_price_put_oi",
                options_metrics.get("near_put_open_interest"),
            ),
            "near_put_call_volume_ratio": options_metrics.get("near_put_call_volume_ratio"),
            "near_put_call_oi_ratio": options_metrics.get("near_put_call_oi_ratio"),
            "options_near_price_put_call_ratio": options_metrics.get(
                "options_near_price_put_call_ratio",
                options_metrics.get("near_put_call_oi_ratio"),
            ),
            "near_call_oi_share": options_metrics.get("near_call_oi_share"),
            "max_call_oi_strike": options_metrics.get("max_call_oi_strike"),
            "options_top_call_strike": options_metrics.get(
                "options_top_call_strike",
                options_metrics.get("max_call_oi_strike"),
            ),
            "max_call_oi": options_metrics.get("max_call_oi"),
            "max_put_oi_strike": options_metrics.get("max_put_oi_strike"),
            "options_top_put_strike": options_metrics.get(
                "options_top_put_strike",
                options_metrics.get("max_put_oi_strike"),
            ),
            "max_put_oi": options_metrics.get("max_put_oi"),
            "max_pain_approx": options_metrics.get("max_pain_approx"),
            "atm_implied_volatility": options_metrics.get("atm_implied_volatility"),
            "call_volume_to_oi": options_metrics.get("call_volume_to_oi"),
            "put_volume_to_oi": options_metrics.get("put_volume_to_oi"),
            "total_option_volume": options_metrics.get("total_option_volume"),
            "total_option_open_interest": options_metrics.get("total_option_open_interest"),
            "source_channel": m.get("source_channel"),
            "source_channels": m.get("source_channels"),
            "screener_hit_count": m.get("screener_hit_count"),
            "screener_weighted_hits": m.get("screener_weighted_hits"),
            "avg_source_rank": m.get("avg_source_rank"),
            "best_source_rank": m.get("best_source_rank"),
            "source_quality_score": m.get("source_quality_score"),
            **scenario,
        }

        row.update(build_options_flow_fields(options_metrics, options_score_data))

        if not row.get("quote_status"):
            if row.get("bid_ask_valid") is True:
                row["quote_status"] = "VALID"
                row["execution_quote_quality"] = "HIGH"
            else:
                warning = str(row.get("bid_ask_warning") or "").lower()

                if "no disponible" in warning:
                    row["quote_status"] = "MISSING"
                elif "ask <= bid" in warning or "cero" in warning or "negativo" in warning:
                    row["quote_status"] = "INVALID"
                elif "stale" in warning or "alejado" in warning:
                    row["quote_status"] = "STALE_POSSIBLE"
                elif "spread" in warning:
                    row["quote_status"] = "WIDE_OR_INCOHERENT"
                else:
                    row["quote_status"] = "MISSING"

                row["execution_quote_quality"] = "LOW"

        if not row.get("execution_quote_quality"):
            row["execution_quote_quality"] = (
                "HIGH" if row.get("quote_status") == "VALID" else "LOW"
            )

        if row.get("quote_status") == "VALID" and row.get("execution_quote_quality") == "HIGH":
            row["analysis_quote_confidence"] = "HIGH"
        elif row.get("analysis_price") is not None:
            row["analysis_quote_confidence"] = "LOW"
        else:
            row["analysis_quote_confidence"] = "UNKNOWN"

        row = apply_analysis_quote_fallback(row, analysis_quote_fallbacks.get(ticker))

        row["warnings"] = _join_warnings(
            m.get("data_quality_warning"),
            m.get("liquidity_warning"),
            fund.get("fundamental_warning"),
            options_score_data.get("options_warning"),
        )
        context_checks = [
            bool(row.get("sector") and str(row.get("sector")).upper() != "UNKNOWN"),
            bool(
                row.get("sector_weekly_macd_state")
                and "UNKNOWN" not in str(row.get("sector_weekly_macd_state")).upper()
            ),
            bool(row.get("macro_context_status")),
            row.get("days_to_earnings") is not None,
            str(row.get("quote_status") or "").upper() == "VALID",
        ]
        row["context_confidence_score"] = round(
            100.0 * sum(context_checks) / len(context_checks),
            2,
        )

        dq = score_data_quality(row, config)
        row.update(dq)
        row["warnings"] = _join_warnings(
            row.get("warnings"),
            dq.get("data_quality_warning"),
        )

        row["pre_veto_signal"] = classify_base_signal(row, config)

        signal, veto = classify_signal(row, config)

        penalty_reasons = []

        if str(row.get("execution_quote_quality") or "").upper().strip() == "LOW":
            if row.get("trigger_confirmed") is True:
                penalty_reasons.append("execution_quote_unconfirmed")

        stop_atr_status = str(row.get("stop_atr_status") or "").upper().strip()

        if stop_atr_status == "BELOW_HARD_MIN":
            penalty_reasons.append("stop_too_tight_below_0_6_atr")
        elif stop_atr_status == "AGGRESSIVE_TIGHT":
            penalty_reasons.append("aggressive_tight_stop")
        elif stop_atr_status == "WIDE":
            penalty_reasons.append("wide_stop")

        row["options_scoring_status"] = "CONTEXT_ONLY_NOT_SCORED"

        row["signal"] = signal
        research_only_veto_reasons = {"rr_below_minimum", "no_valid_setup"}
        hard_veto_reasons = set(veto) - research_only_veto_reasons
        if (
            str(row.get("decision_lane") or "").upper() == "TACTICAL_RESEARCH"
            and not hard_veto_reasons
        ):
            row["signal"] = "WATCHLIST"
            row["recommendation"] = "WATCHLIST_MONITOR"
        scenario_guardrail = apply_scenario_guardrail(row)
        row.update(scenario_guardrail)
        if row.get("scenario_guardrail_reason"):
            penalty_reasons.append(str(row["scenario_guardrail_reason"]))

        row = apply_operational_signal_guardrails(row, penalty_reasons)

        if str(row.get("technical_analysis_lane") or "").upper() == "ADVANCE_RESEARCH_ANALYSIS":
            if row.get("signal") not in {"VETO", "AVOID"}:
                row["signal"] = "WATCHLIST"
            row["scenario_eligible_for_backtest"] = False
            row["scenario_operability"] = "RESEARCH_ONLY"
            row["scenario_guardrail_applied"] = True
            row["scenario_guardrail_reason"] = "research_lane_not_operational"
            row["engine_recommendation"] = "RESEARCH_ONLY"
            row["execution_readiness_status"] = "NOT_OPERABLE"
            row["actionable_entry"] = None
            row["actionable_stop"] = None
            row["actionable_target"] = None
            penalty_reasons.append("research_lane_not_operational")

        row["all_veto_reasons"] = ", ".join(veto)
        row["veto_reasons"] = row["all_veto_reasons"]  # backward compatibility
        row["penalty_reasons"] = ", ".join(penalty_reasons)

        if (
            row["signal"] not in {"VETO", "AVOID"}
            and stop_atr_status == "BELOW_HARD_MIN"
        ):
            row["signal"] = "AVOID"
            row["penalty_reasons"] = _join_warnings(
                row.get("penalty_reasons"),
                "degraded_to_avoid_stop_below_0_6_atr",
            )

        if row["signal"] == "VETO":
            row["actionable_entry"] = None
            row["actionable_stop"] = None
            row["actionable_target"] = None

        row["reason_summary"] = _reason_summary(row)

        priority = calculate_operational_priority(row, config)
        row.update(priority)
        row.update(calculate_operational_readiness(row, config))

        if str(row.get("technical_analysis_lane") or "").upper() == "ADVANCE_RESEARCH_ANALYSIS":
            row["scenario_eligible_for_backtest"] = False
            row["scenario_operability"] = "RESEARCH_ONLY"
            row["execution_readiness_status"] = "NOT_OPERABLE"
            row["operational_status"] = "RESEARCH_ONLY"
            row["operational_readiness_bucket"] = "R_RESEARCH"
            row["engine_block_reason"] = "research_lane_not_operational"
            row["actionable_entry"] = None
            row["actionable_stop"] = None
            row["actionable_target"] = None

        rows.append(row)

    if technical_reject_rows:
        rows.extend(technical_reject_rows)

    out = pd.DataFrame(rows)

    if out.empty:
        _stage_done(performance, "final_scoring_and_guardrails", stage_started)
        return out

    signal_order = {
        "TRIGGER_CONFIRMED": 0,
        "READY_WAIT_TRIGGER": 1,
        "WATCHLIST": 2,
        "AVOID": 3,
        "VETO": 4,
        "BUY_SETUP_ACTIVE": 99,  # legacy/disabled
    }

    recommendation_order = {
        "MANUAL_REVIEW_TRIGGER_CONFIRMED": 0,
        "WAIT_FOR_TRIGGER": 1,
        "WATCHLIST_MONITOR": 2,
        "RECHECK_LIVE_QUOTE": 3,
        "WATCHLIST_MONITOR_QUOTE": 4,
        "WATCHLIST_NO_VALID_SETUP": 5,
        "AVOID_FOR_NOW": 6,
        "DO_NOT_TRADE": 7,
        "REVIEW_MANUALLY": 8,
    }

    quote_quality_order = {
        "HIGH": 0,
        "MEDIUM": 1,
        "LOW": 2,
    }

    out["_signal_order"] = (
        out["signal"]
        .map(signal_order)
        .fillna(99)
        .astype(int)
    )

    if "recommendation" in out.columns:
        out["_recommendation_order"] = (
            out["recommendation"]
            .map(recommendation_order)
            .fillna(99)
            .astype(int)
        )
    else:
        out["_recommendation_order"] = 99

    if "execution_quote_quality" in out.columns:
        out["_quote_quality_order"] = (
            out["execution_quote_quality"]
            .map(quote_quality_order)
            .fillna(99)
            .astype(int)
        )
    else:
        out["_quote_quality_order"] = 99

    # Legacy rank: global old score view.
    if "final_score" in out.columns:
        out["legacy_rank"] = (
            out["final_score"]
            .rank(method="first", ascending=False)
            .astype(int)
        )
    else:
        out["legacy_rank"] = range(1, len(out) + 1)

    # Raw trade-score rank: useful for diagnostics only.
    if "final_trade_score" in out.columns:
        out["trade_score_rank"] = (
            out["final_trade_score"]
            .rank(method="first", ascending=False)
            .astype(int)
        )
    else:
        out["trade_score_rank"] = out["legacy_rank"]

    sort_cols = [
        "_signal_order",
        "_recommendation_order",
        "_quote_quality_order",
        "operational_readiness_score",
        "final_trade_score",
        "setup_quality_score",
        "final_score",
    ]

    sort_cols = [c for c in sort_cols if c in out.columns]

    ascending_map = {
        "_signal_order": True,
        "_recommendation_order": True,
        "_quote_quality_order": True,
        "operational_readiness_score": False,
        "final_trade_score": False,
        "setup_quality_score": False,
        "final_score": False,
    }

    ascending = [ascending_map[c] for c in sort_cols]

    out = out.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)

    out["operational_rank"] = range(1, len(out) + 1)
    out["rank_delta_trade_vs_legacy"] = out["trade_score_rank"] - out["legacy_rank"]

    # Keep existing rank as operational rank from this point.
    # This is safe because signal_order still prevents VETO from rising above operable states.
    out["rank"] = out["operational_rank"]

    out = out.drop(
        columns=[
            "_signal_order",
            "_recommendation_order",
            "_quote_quality_order",
        ],
        errors="ignore",
    )

    performance["counts"]["output_rows"] = int(len(out))
    performance["deep_analysis_tier_counts"] = (
        out.get("deep_analysis_tier", pd.Series(dtype=str))
        .fillna("NONE")
        .astype(str)
        .value_counts()
        .to_dict()
    )
    performance["setup_readiness_state_counts"] = (
        out.get("setup_readiness_state", pd.Series(dtype=str))
        .fillna("UNKNOWN")
        .astype(str)
        .value_counts()
        .to_dict()
    )
    performance["rr_status_counts"] = (
        out.get("rr_status", pd.Series(dtype=str))
        .fillna("UNKNOWN")
        .astype(str)
        .value_counts()
        .to_dict()
    )
    performance["risk_geometry_status_counts"] = (
        out.get("risk_geometry_status", pd.Series(dtype=str))
        .fillna("UNKNOWN")
        .astype(str)
        .value_counts()
        .to_dict()
    )
    performance["market_opportunity_status_counts"] = (
        out.get("market_opportunity_status", pd.Series(dtype=str))
        .fillna("UNKNOWN")
        .astype(str)
        .value_counts()
        .to_dict()
    )
    performance["clean_execution_candidates"] = int(
        out.get("market_opportunity_status", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .eq("EXECUTION_READY_REVIEW")
        .sum()
    )
    _stage_done(performance, "final_scoring_and_guardrails", stage_started)
    return out


def _save_scan_performance(performance: dict, config: dict) -> None:
    performance["_report_path"] = _performance_report_path(config)
    _write_scan_performance(performance)


def run_scan(config: dict, max_candidates: int | None = None) -> pd.DataFrame:
    """
    Run the scanner while preserving the existing output contract.

    Macro context remains informational through macro_context_status,
    macro_risk_flag, macro_notes, macro_source, macro_timestamp and
    macro_data_freshness. Execution guardrails are calculated exclusively
    inside the scanner pipeline and are not changed by performance telemetry.
    """
    started = perf_counter()
    performance = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "RUNNING",
        "counts": {},
        "stage_seconds": {},
        "guardrails_modified": False,
        "_report_path": _performance_report_path(config),
    }
    _write_scan_performance(performance)
    try:
        output = _run_scan_impl(config, max_candidates, performance)
        performance["status"] = "PASS"
        return output
    except Exception as exc:
        performance["status"] = "FAIL"
        performance["error"] = f"{type(exc).__name__}:{exc}"
        raise
    finally:
        performance["finished_at"] = datetime.now(timezone.utc).isoformat()
        performance["total_seconds"] = round(perf_counter() - started, 4)
        _save_scan_performance(performance, config)


def _reason_summary(row: dict) -> str:
    if row.get("signal") == "VETO":
        return f"Veto: {row.get('veto_reasons')}"

    rr = row.get("rr")
    rr_text = round(rr, 2) if rr is not None else "NA"

    options_bias = row.get("options_bias")
    options_text = f" | opt {options_bias}" if options_bias else ""
    options_status = row.get("options_scoring_status") or "CONTEXT_ONLY_NOT_SCORED"
    options_status_text = f" ({options_status})" if options_bias else ""
    scenario_status = row.get("scenario_status")
    scenario_text = f" | scenario {scenario_status}" if scenario_status else ""
    scenario_reason = row.get("scenario_guardrail_reason")
    scenario_reason_text = f" | {scenario_reason}" if scenario_reason else ""

    return (
        f"{row.get('setup_type')} | score {row.get('final_score')} | "
        f"RS {row.get('rs_score')} | trend {row.get('trend_score')} | "
        f"R:R {rr_text}{scenario_text}{scenario_reason_text}"
        f"{options_text}{options_status_text}"
    )
