from __future__ import annotations

from loguru import logger
import pandas as pd

from data.screener_client import run_screeners
from data.price_client import download_daily_prices
from data.fundamentals_client import enrich_metadata
from data.options_client import fetch_options_metrics

from universe.equity_validator import validate_universe
from universe.liquidity_filter import compute_liquidity

from indicators.pipeline import add_all_indicators

from market.market_regime import classify_market_regime
from market.sector_rotation import calculate_sector_rotation

from scoring.relative_strength import add_relative_strength_scores
from scoring.trend_score import score_trend
from scoring.volume_score import score_volume
from scoring.structure_score import score_structure
from scoring.risk_reward_score import score_risk_reward
from scoring.momentum_score import score_momentum
from scoring.fundamental_score import score_fundamentals
from scoring.options_score import score_options_flow
from scoring.final_score import calculate_final_score
from scoring.signal_classifier import classify_signal


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


def run_scan(config: dict, max_candidates: int | None = None) -> pd.DataFrame:
    logger.info("Iniciando scanner Analista MVP.")

    # 1. Screener and first universe validation.
    screen = run_screeners(config)
    meta = validate_universe(screen.dataframe, config)

    if max_candidates:
        meta = meta.head(max_candidates)

    if meta.empty:
        logger.warning("No hay tickers tras screener/validación inicial.")
        return pd.DataFrame()

    # 2. Metadata/fundamentals enrichment.
    logger.info("Enriqueciendo metadata: sector, industry, earnings y fundamentales tácticos.")
    meta = enrich_metadata(meta, config)

    # 2b. Revalidate after enrichment.
    # Some screeners return incomplete quote_type/metadata. This second pass reduces
    # the chance of ETFs, preferreds, units, warrants or funds reaching the scanner.
    meta = validate_universe(meta, config)

    if meta.empty:
        logger.warning("No hay tickers tras enriquecimiento y revalidación de universo.")
        return pd.DataFrame()

    tickers = meta["ticker"].dropna().astype(str).str.upper().unique().tolist()
    logger.info(f"Tickers tras screener/validación/enriquecimiento: {len(tickers)}")

    # 3. Prices.
    price_cfg = config.get("price_data", {})
    raw_prices = download_daily_prices(
        tickers,
        period=price_cfg.get("daily_period", "1y"),
        interval=price_cfg.get("daily_interval", "1d"),
    )

    prices: dict[str, pd.DataFrame] = {}
    liquidity_rows: list[dict] = []
    base_rows: list[dict] = []

    meta_by_ticker = meta.set_index("ticker").to_dict(orient="index")

    for ticker in tickers:
        df = raw_prices.get(ticker)

        if df is None or df.empty:
            logger.warning(f"Sin precios para {ticker}.")
            continue

        ind = add_all_indicators(df, config)
        prices[ticker] = ind

        liquidity_rows.append(
            compute_liquidity(
                ticker,
                ind,
                config,
                metadata=meta_by_ticker.get(ticker, {}),
            )
        )

    liquidity = pd.DataFrame(liquidity_rows)

    if liquidity.empty:
        logger.warning("No hay datos de liquidez. Retornando DataFrame vacío.")
        return pd.DataFrame()

    # Avoid duplicate fields before merging liquidity.
    drop_cols = [c for c in ["price", "spread_pct", "bid", "ask"] if c in meta.columns]
    meta = meta.drop(columns=drop_cols, errors="ignore")
    meta = meta.merge(liquidity, on="ticker", how="inner")

    # Keep only liquid names, but preserve liquidity_pass in output.
    meta = meta[meta["liquidity_pass"] == True].reset_index(drop=True)
    tickers = meta["ticker"].dropna().astype(str).str.upper().tolist()

    logger.info(f"Tickers tras liquidez: {len(tickers)}")

    if meta.empty:
        logger.warning("Todos los tickers fallaron liquidez.")
        return pd.DataFrame()

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
    options_counter = 0

    # 7. Full scoring pass.
    rows: list[dict] = []

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

        if options_enabled and options_counter < max_options_tickers and spot is not None:
            options_metrics = fetch_options_metrics(ticker, spot, config)
            options_score_data = score_options_flow(options_metrics, spot, config)
            options_counter += 1
        else:
            options_metrics = {
                "options_data_available": False,
                "options_source": "disabled_or_limit",
                "options_warning": "options_flow desactivado, sin spot válido o límite max_tickers_per_run alcanzado",
            }
            options_score_data = score_options_flow(options_metrics, spot, config)

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
            "sentiment_score": 0.5,
        }

        final_score = calculate_final_score(scores, config)

        row = {
            "ticker": ticker,
            "company": m.get("company"),
            "exchange": m.get("exchange"),
            "quote_type": m.get("quote_type"),
            "country": m.get("country"),
            "sector": m.get("sector") or sector_info.get("sector"),
            "industry": m.get("industry"),
            "market_cap": m.get("market_cap"),
            "market_regime": regime.get("regime"),

            "final_score": round(final_score, 2),
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
            "options_bias": options_score_data.get("options_bias"),
            "options_confidence": options_score_data.get("options_confidence"),
            "options_crowded_bullish": options_score_data.get("options_crowded_bullish", False),

            "setup_type": structure.get("setup_type"),
            "trigger_confirmed": structure.get("trigger_confirmed", False),
            "trigger_level": structure.get("trigger_level"),
            "entry": rr_data.get("entry"),
            "stop": rr_data.get("stop"),
            "target": rr_data.get("target"),
            "rr": rr_data.get("rr"),
            "atr_pct": latest.get("atr_pct"),
            "relative_volume": latest.get("relative_volume"),
            "price": latest.get("close"),

            "avg_volume_20d": m.get("avg_volume_20d"),
            "avg_volume_60d": m.get("avg_volume_60d"),
            "median_volume_20d": m.get("median_volume_20d"),
            "mean_volume_20d": m.get("mean_volume_20d"),
            "dollar_volume_20d": m.get("dollar_volume_20d"),
            "median_to_mean_volume_ratio": m.get("median_to_mean_volume_ratio"),
            "spread_pct": m.get("spread_pct"),
            "bid": m.get("bid"),
            "ask": m.get("ask"),
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
            "options_source": options_metrics.get("options_source"),
            "options_expirations_used": options_metrics.get("options_expirations_used"),
            "call_volume": options_metrics.get("call_volume"),
            "put_volume": options_metrics.get("put_volume"),
            "call_open_interest": options_metrics.get("call_open_interest"),
            "put_open_interest": options_metrics.get("put_open_interest"),
            "put_call_volume_ratio": options_metrics.get("put_call_volume_ratio"),
            "put_call_oi_ratio": options_metrics.get("put_call_oi_ratio"),
            "call_volume_share": options_metrics.get("call_volume_share"),
            "call_oi_share": options_metrics.get("call_oi_share"),
            "near_call_volume": options_metrics.get("near_call_volume"),
            "near_put_volume": options_metrics.get("near_put_volume"),
            "near_call_open_interest": options_metrics.get("near_call_open_interest"),
            "near_put_open_interest": options_metrics.get("near_put_open_interest"),
            "near_put_call_volume_ratio": options_metrics.get("near_put_call_volume_ratio"),
            "near_put_call_oi_ratio": options_metrics.get("near_put_call_oi_ratio"),
            "near_call_oi_share": options_metrics.get("near_call_oi_share"),
            "max_call_oi_strike": options_metrics.get("max_call_oi_strike"),
            "max_call_oi": options_metrics.get("max_call_oi"),
            "max_put_oi_strike": options_metrics.get("max_put_oi_strike"),
            "max_put_oi": options_metrics.get("max_put_oi"),
            "max_pain_approx": options_metrics.get("max_pain_approx"),
            "atm_implied_volatility": options_metrics.get("atm_implied_volatility"),
            "call_volume_to_oi": options_metrics.get("call_volume_to_oi"),
            "put_volume_to_oi": options_metrics.get("put_volume_to_oi"),
            "total_option_volume": options_metrics.get("total_option_volume"),
            "total_option_open_interest": options_metrics.get("total_option_open_interest"),

            "warnings": _join_warnings(
                m.get("data_quality_warning"),
                m.get("liquidity_warning"),
                fund.get("fundamental_warning"),
                options_score_data.get("options_warning"),
            ),
        }

        signal, veto = classify_signal(row, config)
        row["signal"] = signal
        row["veto_reasons"] = ", ".join(veto)
        row["reason_summary"] = _reason_summary(row)

        rows.append(row)

    out = pd.DataFrame(rows)

    if out.empty:
        return out

    signal_order = {
        "BUY_SETUP_ACTIVE": 0,
        "READY_WAIT_TRIGGER": 1,
        "WATCHLIST": 2,
        "AVOID": 3,
        "VETO": 4,
    }

    out["_signal_order"] = out["signal"].map(signal_order).fillna(9)
    out = (
        out.sort_values(["_signal_order", "final_score"], ascending=[True, False])
        .drop(columns=["_signal_order"])
        .reset_index(drop=True)
    )
    out.insert(0, "rank", range(1, len(out) + 1))

    return out


def _reason_summary(row: dict) -> str:
    if row.get("signal") == "VETO":
        return f"Veto: {row.get('veto_reasons')}"

    rr = row.get("rr")
    rr_text = round(rr, 2) if rr is not None else "NA"

    options_bias = row.get("options_bias")
    options_text = f" | opt {options_bias}" if options_bias else ""

    return (
        f"{row.get('setup_type')} | score {row.get('final_score')} | "
        f"RS {row.get('rs_score')} | trend {row.get('trend_score')} | "
        f"R:R {rr_text}{options_text}"
    )
