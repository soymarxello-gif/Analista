from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

import pandas as pd
from loguru import logger

from data.data_quality import score_data_quality
from data.fundamentals_client import enrich_metadata
from data.options_client import fetch_options_metrics
from data.price_client import download_daily_prices
from data.screener_client import run_screeners
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
from indicators.pipeline import add_all_indicators
from market.market_regime import classify_market_regime
from market.sector_rotation import calculate_sector_rotation
from scoring.final_score import calculate_final_score, calculate_trade_score_breakdown
from scoring.fundamental_score import score_fundamentals
from scoring.momentum_score import score_momentum
from scoring.operational_priority import calculate_operational_priority
from scoring.options_score import calculate_options_score_adjustment, score_options_flow
from scoring.relative_strength import add_relative_strength_scores
from scoring.risk_reward_score import score_risk_reward
from scoring.signal_classifier import classify_base_signal, classify_signal
from scoring.structure_score import score_structure
from scoring.trend_score import score_trend
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


def _stage_done(performance: dict, name: str, started: float) -> None:
    performance.setdefault("stage_seconds", {})[name] = round(perf_counter() - started, 4)


def _run_scan_impl(
    config: dict,
    max_candidates: int | None,
    performance: dict,
) -> pd.DataFrame:
    logger.info("Iniciando scanner Analista MVP.")

    # 1. Screener and first universe validation.
    stage_started = perf_counter()
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
    raw_prices = download_daily_prices(
        tickers,
        period=price_cfg.get("daily_period", "1y"),
        interval=price_cfg.get("daily_interval", "1d"),
        batch_size=int(price_cfg.get("batch_size", 150)),
        retry_batch_size=int(price_cfg.get("retry_batch_size", 50)),
        timeout_seconds=int(price_cfg.get("timeout_seconds", 15)),
        max_individual_fallbacks=int(price_cfg.get("max_individual_fallbacks", 10)),
        stats=price_stats,
    )
    performance["price_download"] = price_stats
    _stage_done(performance, "bulk_price_download", stage_started)

    prices: dict[str, pd.DataFrame] = {}
    pre_liquidity_rows: list[dict] = []
    scan_timestamp = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    base_rows: list[dict] = []

    # 3. Fast in-memory liquidity funnel. Bid/ask is intentionally excluded here.
    stage_started = perf_counter()
    for ticker in tickers:
        df = raw_prices.get(ticker)

        if df is None or df.empty:
            logger.warning(f"Sin precios para {ticker}.")
            continue

        ind = add_all_indicators(df, config)
        prices[ticker] = ind
        pre_liquidity_rows.append(
            compute_liquidity(
                ticker,
                ind,
                config,
                metadata={},
            )
        )

    pre_liquidity = pd.DataFrame(pre_liquidity_rows)

    if pre_liquidity.empty:
        logger.warning("No hay datos de liquidez. Retornando DataFrame vacío.")
        return pd.DataFrame()

    pre_liquid_tickers = set(
        pre_liquidity.loc[pre_liquidity["liquidity_pass"], "ticker"].astype(str)
    )
    meta = meta[meta["ticker"].astype(str).isin(pre_liquid_tickers)].copy()
    pre_metrics = pre_liquidity[pre_liquidity["ticker"].astype(str).isin(pre_liquid_tickers)].copy()
    meta = meta.drop(columns=["price"], errors="ignore").merge(pre_metrics, on="ticker", how="inner")
    prices = {ticker: frame for ticker, frame in prices.items() if ticker in pre_liquid_tickers}
    performance["counts"]["price_history_rows"] = int(len(prices))
    performance["counts"]["pre_liquidity_rows"] = int(len(meta))
    _stage_done(performance, "technical_preliquidity", stage_started)

    if meta.empty:
        logger.warning("Todos los tickers fallaron preliquidez.")
        return pd.DataFrame()

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
    meta = enrich_metadata(meta, config, stats=metadata_stats)
    performance["metadata_enrichment"] = metadata_stats
    _stage_done(performance, "metadata_and_fundamentals", stage_started)

    # 4b. Strict universe validation after enrichment.
    stage_started = perf_counter()
    meta = validate_universe(meta, config, strict_metadata=True)
    performance["counts"]["post_metadata_rows"] = int(len(meta))
    _stage_done(performance, "strict_universe_validation", stage_started)
    if meta.empty:
        logger.warning("No hay tickers tras enriquecimiento y revalidación de universo.")
        return pd.DataFrame()

    tickers = meta["ticker"].dropna().astype(str).str.upper().unique().tolist()
    logger.info(f"Tickers tras screener/liquidez/enriquecimiento: {len(tickers)}")

    # 5. Final liquidity/quote evaluation with enriched bid/ask.
    stage_started = perf_counter()
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
        return pd.DataFrame()
    liquidity_columns = [column for column in final_liquidity.columns if column != "ticker"]
    meta = meta.drop(columns=liquidity_columns, errors="ignore")
    meta = meta.merge(final_liquidity, on="ticker", how="inner")
    meta = meta[meta["liquidity_pass"]].reset_index(drop=True)
    tickers = meta["ticker"].dropna().astype(str).str.upper().tolist()
    prices = {ticker: frame for ticker, frame in prices.items() if ticker in set(tickers)}
    performance["counts"]["final_liquidity_rows"] = int(len(meta))
    _stage_done(performance, "final_quote_liquidity", stage_started)
    logger.info(f"Tickers tras liquidez: {len(tickers)}")

    if meta.empty:
        logger.warning("Todos los tickers fallaron liquidez.")
        return pd.DataFrame()

    analysis_quote_tickers = select_analysis_quote_fallback_tickers(meta.to_dict(orient="records"))
    analysis_quote_fallbacks = build_analysis_quote_fallbacks(analysis_quote_tickers, config)

    # 4. Market regime and sector rotation.
    regime = classify_market_regime(config)

    sector_df = calculate_sector_rotation(meta, prices)
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

        ret20 = df["close"].iloc[-1] / df["close"].iloc[-21] - 1 if len(df) >= 21 else 0
        ret63 = df["close"].iloc[-1] / df["close"].iloc[-64] - 1 if len(df) >= 64 else ret20

        base_rows.append(
            {
                "ticker": ticker,
                "ret20": ret20,
                "ret63": ret63,
            }
        )

    base_rows = add_relative_strength_scores(base_rows)
    rs_map = {r["ticker"]: r.get("rs_score", 0.5) for r in base_rows}

    # 6. Options configuration.
    # Options are used only as confirmation/penalty, not as a direct trade trigger.
    options_enabled = config.get("options_flow", {}).get("enabled", False)
    max_options_tickers = config.get("options_flow", {}).get("max_tickers_per_run", 50)

    # Build an option-neutral candidate ranking before spending the network budget.
    # This prevents arbitrary universe order from consuming option queries on early VETO rows.
    prepared: dict[str, dict] = {}
    selection_candidates: list[dict] = []
    for _, m in meta.iterrows():
        ticker = m["ticker"]
        df = prices.get(ticker)
        if df is None or df.empty:
            continue

        trend_score, trend_status = score_trend(df, config)
        volume_score = score_volume(df)
        structure = score_structure(df, config)
        rr_data = score_risk_reward(df, structure, config)
        momentum_score = score_momentum(df, config)
        fund = score_fundamentals(m, config)
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
            "trigger_confirmed": structure.get("trigger_confirmed", False),
            "price": spot,
            "market_cap": m.get("market_cap"),
            "quote_type": m.get("quote_type"),
            "liquidity_pass": bool(m.get("liquidity_pass", False)),
            "trend_score": trend_score,
            "setup_type": structure.get("setup_type"),
            "earnings_veto": fund.get("earnings_veto", False),
            "quote_status": m.get("quote_status"),
            "execution_quote_quality": m.get("execution_quote_quality"),
            "universe_veto_reasons": m.get("universe_veto_reasons"),
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
                "rr": rr_data.get("rr"),
                "quote_status": m.get("quote_status"),
                "execution_quote_quality": m.get("execution_quote_quality"),
                "sector": m.get("sector") or sector_info.get("sector"),
                "trend_score": trend_score,
                "momentum_score": momentum_score,
                "liquidity_score": float(m.get("liquidity_score", 0.5)),
                "source_quality_score": float(m.get("source_quality_score", 0.5) or 0.5),
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

    options_selection_candidates = [
        row for row in selection_candidates if row.get("ticker") in deep_analysis_set
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

    # 7. Full scoring pass.
    scan_timestamp = datetime.now(timezone.utc).isoformat()

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
        scenario = analyze_scenario(
            df,
            setup_type=structure.get("setup_type"),
            trigger_level=structure.get("trigger_level"),
            market_regime=regime.get("regime", ""),
            selected=deep_selected,
        )
        shadow_levels = calculate_shadow_levels(
            df,
            scenario=scenario,
            setup_type=structure.get("setup_type"),
            rr_data=rr_data,
            config=config,
        )

        if ticker in options_metrics_by_ticker:
            options_metrics = options_metrics_by_ticker[ticker]
            options_score_data = score_options_flow(options_metrics, spot, config)
        else:
            selection_error = (
                "options_flow_disabled"
                if not options_enabled
                else "not_selected_by_priority_budget"
                if ticker not in selected_options_set
                else "missing_spot"
            )
            options_metrics = {
                "options_data_available": False,
                "options_available": False,
                "options_source": "disabled_or_limit",
                "options_error": selection_error,
                "options_warning": "options flow no consultado por límite priorizado, desactivación o spot faltante",
                "options_notes": "options flow no consultado por límite priorizado, desactivación o spot faltante",
            }
            options_score_data = score_options_flow(options_metrics, spot, config)

        if options_metrics.get("options_data_available") is True:
            options_coverage_status = "AVAILABLE"
        elif options_metrics.get("options_error") == "not_selected_by_priority_budget":
            options_coverage_status = "NOT_SELECTED_BY_BUDGET"
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
            "options_score": options_score_data.get("options_score", 0.5),
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
            "asset_quality_score": trade_scores["asset_quality_score"],
            "setup_quality_score": trade_scores["setup_quality_score"],
            "context_score": trade_scores["context_score"],
            "institutional_score": trade_scores["institutional_score"],
            "final_trade_score": trade_scores["final_trade_score"],
            "score_breakdown": trade_scores["score_breakdown_json"],
            "deep_analysis_selected": deep_selected,
            "deep_analysis_rank": deep_analysis_audit.get(ticker, {}).get("deep_analysis_rank"),
            "deep_analysis_score": deep_analysis_audit.get(ticker, {}).get("deep_analysis_score"),
            "deep_analysis_reason": deep_analysis_audit.get(ticker, {}).get(
                "deep_analysis_reason",
                "outside_deep_analysis_budget",
            ),
            "rs_score": round(scores["rs_score"], 3),
            "trend_score": round(trend_score, 3),
            "trend_status": trend_status,
            "volume_score": round(volume_score, 3),
            "sector_score": round(sector_score, 3),
            "structure_score": round(structure.get("structure_score", 0.5), 3),
            "rr_score": round(rr_data.get("rr_score", 0.0), 3),
            "liquidity_pass": bool(m.get("liquidity_pass", False)),
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
            "relative_volume": latest.get("relative_volume"),
            "price": latest.get("close"),
            "avg_volume_20d": m.get("avg_volume_20d"),
            "avg_volume_60d": m.get("avg_volume_60d"),
            "median_volume_20d": m.get("median_volume_20d"),
            "mean_volume_20d": m.get("mean_volume_20d"),
            "dollar_volume_20d": m.get("dollar_volume_20d"),
            "dollar_volume_60d": m.get("dollar_volume_60d"),
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

        options_risk_flag = str(row.get("options_risk_flag") or "").strip()
        if options_risk_flag == "crowded_bullish_contrarian":
            penalty_reasons.append("crowded_bullish_contrarian")
        elif options_risk_flag == "options_bearish_with_data":
            penalty_reasons.append("options_bearish_with_data")

        row["signal"] = signal
        scenario_guardrail = apply_scenario_guardrail(row)
        row.update(scenario_guardrail)
        if row.get("scenario_guardrail_reason"):
            penalty_reasons.append(str(row["scenario_guardrail_reason"]))
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

        rows.append(row)

    out = pd.DataFrame(rows)

    if out.empty:
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
        "final_trade_score",
        "setup_quality_score",
        "final_score",
    ]

    sort_cols = [c for c in sort_cols if c in out.columns]

    ascending_map = {
        "_signal_order": True,
        "_recommendation_order": True,
        "_quote_quality_order": True,
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
    return out


def _save_scan_performance(performance: dict, config: dict) -> None:
    relative_path = (
        config.get("performance", {}).get(
            "scan_report_path",
            "reports/scan_performance_latest.json",
        )
    )
    path = Path(relative_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(performance, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning(f"No se pudo guardar scan performance: {exc}")


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
    }
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
    options_reason = row.get("options_score_reason")
    options_reason_text = f" | {options_reason}" if options_reason else ""
    scenario_status = row.get("scenario_status")
    scenario_text = f" | scenario {scenario_status}" if scenario_status else ""
    scenario_reason = row.get("scenario_guardrail_reason")
    scenario_reason_text = f" | {scenario_reason}" if scenario_reason else ""

    return (
        f"{row.get('setup_type')} | score {row.get('final_score')} | "
        f"RS {row.get('rs_score')} | trend {row.get('trend_score')} | "
        f"R:R {rr_text}{scenario_text}{scenario_reason_text}"
        f"{options_text}{options_reason_text}"
    )
