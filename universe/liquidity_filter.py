from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_float(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _clip01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _ratio_score(value: float, threshold: float) -> float:
    if threshold <= 0:
        return 1.0
    return _clip01(value / threshold)


def _market_cap_tier(market_cap: float | None, cfg: dict) -> str:
    tiers = cfg.get("market_cap_tiers", {})
    mega = float(tiers.get("mega", 100_000_000_000) or 100_000_000_000)
    large = float(tiers.get("large", 10_000_000_000) or 10_000_000_000)
    mid = float(tiers.get("mid", 2_500_000_000) or 2_500_000_000)
    if market_cap is None or market_cap <= 0:
        return "unknown"
    if market_cap >= mega:
        return "mega"
    if market_cap >= large:
        return "large"
    if market_cap >= mid:
        return "mid"
    return "small"


def _turnover_floor(cfg: dict, key: str, tier: str) -> float | None:
    floors = cfg.get(key, {})
    if not isinstance(floors, dict):
        return None
    value = floors.get(tier, floors.get("default"))
    try:
        return float(value)
    except Exception:
        return None


def _validate_bid_ask(close: float, metadata: dict, cfg: dict) -> dict:
    bid = _safe_float(metadata.get("bid"))
    ask = _safe_float(metadata.get("ask"))

    max_quote_distance_pct = cfg.get("max_quote_distance_pct", 0.10)
    max_spread = cfg.get("max_bid_ask_spread_pct", None)

    warning = ""
    bid_ask_valid = False
    spread_validated_pct = None
    quote_status = "MISSING"
    execution_quote_quality = "LOW"

    if bid is None or ask is None:
        warning = "bid/ask no disponible"
        quote_status = "MISSING"
        execution_quote_quality = "LOW"

    elif bid <= 0 or ask <= 0:
        warning = "bid/ask inválido: cero o negativo"
        quote_status = "INVALID"
        execution_quote_quality = "LOW"

    elif ask <= bid:
        warning = "bid/ask inválido: ask <= bid"
        quote_status = "INVALID"
        execution_quote_quality = "LOW"

    elif close <= 0:
        warning = "precio inválido para validar bid/ask"
        quote_status = "INVALID"
        execution_quote_quality = "LOW"

    else:
        bid_distance = abs(bid - close) / close
        ask_distance = abs(ask - close) / close

        if bid_distance > max_quote_distance_pct or ask_distance > max_quote_distance_pct:
            warning = "bid/ask alejado del precio; posible quote stale"
            quote_status = "STALE_POSSIBLE"
            execution_quote_quality = "LOW"

        else:
            bid_ask_valid = True
            spread_validated_pct = (ask - bid) / close

            if max_spread is not None and spread_validated_pct > max_spread:
                warning = "spread validado sobre máximo configurado"
                quote_status = "WIDE_OR_INCOHERENT"
                execution_quote_quality = "LOW"
            else:
                quote_status = "VALID"
                execution_quote_quality = "HIGH"

    return {
        "bid": bid,
        "ask": ask,
        "bid_ask_valid": bid_ask_valid,
        "bid_ask_warning": warning,
        "spread_validated_pct": spread_validated_pct,
        "quote_status": quote_status,
        "execution_quote_quality": execution_quote_quality,
    }


def compute_liquidity(ticker: str, df: pd.DataFrame, config: dict, metadata: dict | None = None) -> dict:
    cfg = config.get("liquidity", {})
    metadata = metadata or {}

    if df is None or df.empty or len(df) < 60:
        return {
            "ticker": ticker,
            "liquidity_pass": False,
            "liquidity_core_pass": False,
            "liquidity_spread_pass": False,
            "liquidity_score": 0.0,
            "liquidity_warning": "historial insuficiente",
            "bid_ask_valid": False,
            "bid_ask_warning": "historial insuficiente",
            "spread_validated_pct": None,
            "quote_status": "MISSING",
            "execution_quote_quality": "LOW",
            "execution_spread_status": "UNKNOWN",
            "execution_spread_score": 0.0,
        }

    close = float(df["close"].iloc[-1])
    avg20 = float(df["volume"].tail(20).mean())
    avg60 = float(df["volume"].tail(60).mean())
    med20 = float(df["volume"].tail(20).median())
    mean20 = float(df["volume"].tail(20).mean())
    dollar20 = close * avg20
    dollar60 = close * avg60
    ratio = med20 / mean20 if mean20 else 0
    market_cap = _safe_float(metadata.get("market_cap"))
    market_cap_tier = _market_cap_tier(market_cap, cfg)
    turnover20 = dollar20 / market_cap if market_cap and market_cap > 0 else None
    turnover60 = dollar60 / market_cap if market_cap and market_cap > 0 else None

    min_price = config.get("filters", {}).get("min_price", cfg.get("min_price", 10))
    min_dollar20 = cfg.get("min_dollar_volume_20d", 20000000)
    min_dollar60 = cfg.get("min_dollar_volume_60d", 15000000)
    min_ratio = cfg.get("min_median_to_mean_volume_ratio", 0.5)
    max_spread = cfg.get("max_bid_ask_spread_pct", None)
    use_market_cap_adjusted = bool(cfg.get("use_market_cap_adjusted_liquidity", False))
    turnover_floor20 = _turnover_floor(cfg, "min_turnover_20d", market_cap_tier)
    turnover_floor60 = _turnover_floor(cfg, "min_turnover_60d", market_cap_tier)

    bid_ask = _validate_bid_ask(close, metadata, cfg)
    spread_validated_pct = bid_ask["spread_validated_pct"]

    dollar20_pass = dollar20 >= min_dollar20
    dollar60_pass = dollar60 >= min_dollar60
    turnover20_pass = (
        use_market_cap_adjusted
        and turnover20 is not None
        and turnover_floor20 is not None
        and turnover20 >= turnover_floor20
    )
    turnover60_pass = (
        use_market_cap_adjusted
        and turnover60 is not None
        and turnover_floor60 is not None
        and turnover60 >= turnover_floor60
    )

    core_checks = {
        "price": close >= min_price,
        "liquidity_20d": dollar20_pass or turnover20_pass,
        "liquidity_60d": dollar60_pass or turnover60_pass,
        "volume_consistency": ratio >= min_ratio,
    }

    spread_pass = True
    if max_spread is not None and bid_ask["bid_ask_valid"]:
        spread_pass = spread_validated_pct <= max_spread

    # Universe liquidity is structural. Execution spread is evaluated separately
    # because Yahoo bid/ask can be stale or internally inconsistent.
    liquidity_core_pass = bool(all(core_checks.values()))
    liquidity_pass = liquidity_core_pass

    price_score = _ratio_score(close, min_price)
    dollar20_score = _ratio_score(dollar20, min_dollar20)
    dollar60_score = _ratio_score(dollar60, min_dollar60)
    turnover20_score = _ratio_score(turnover20 or 0.0, turnover_floor20 or 0.0)
    turnover60_score = _ratio_score(turnover60 or 0.0, turnover_floor60 or 0.0)
    adjusted20_score = max(dollar20_score, turnover20_score if use_market_cap_adjusted else 0.0)
    adjusted60_score = max(dollar60_score, turnover60_score if use_market_cap_adjusted else 0.0)
    consistency_score = _ratio_score(ratio, min_ratio)

    if bid_ask["bid_ask_valid"] and max_spread is not None and spread_validated_pct is not None:
        spread_score = _clip01(max_spread / spread_validated_pct) if spread_validated_pct > 0 else 1.0
    elif bid_ask["bid_ask_valid"]:
        spread_score = 0.85
    else:
        # Stale/missing quotes should reduce confidence, not automatically veto.
        spread_score = cfg.get("invalid_bid_ask_score", 0.50)

    liquidity_score = (
        0.40 * adjusted20_score
        + 0.30 * adjusted60_score
        + 0.18 * consistency_score
        + 0.12 * price_score
    )
    liquidity_score = float(np.clip(liquidity_score, 0, 1))
    quote_status = str(bid_ask["quote_status"] or "MISSING").upper()
    execution_spread_status = (
        "VALID"
        if quote_status == "VALID" and spread_pass
        else "WIDE"
        if quote_status == "WIDE_OR_INCOHERENT" or not spread_pass
        else quote_status
    )

    warnings = []
    if not all(core_checks.values()):
        failed = [k for k, ok in core_checks.items() if not ok]
        warnings.append("falló liquidez core: " + ",".join(failed))

    if bid_ask["bid_ask_warning"]:
        warnings.append(bid_ask["bid_ask_warning"])

    if max_spread is not None and bid_ask["bid_ask_valid"] and not spread_pass:
        warnings.append("spread validado sobre máximo")

    return {
        "ticker": ticker,
        "price": close,
        "avg_volume_20d": avg20,
        "avg_volume_60d": avg60,
        "dollar_volume_20d": dollar20,
        "dollar_volume_60d": dollar60,
        "liquidity_turnover_20d": turnover20,
        "liquidity_turnover_60d": turnover60,
        "liquidity_market_cap_tier": market_cap_tier,
        "liquidity_required_turnover_20d": turnover_floor20,
        "liquidity_required_turnover_60d": turnover_floor60,
        "liquidity_formula_pass_20d": turnover20_pass,
        "liquidity_formula_pass_60d": turnover60_pass,
        "liquidity_dollar_pass_20d": dollar20_pass,
        "liquidity_dollar_pass_60d": dollar60_pass,
        "liquidity_core_pass": liquidity_core_pass,
        "liquidity_spread_pass": spread_pass,
        "execution_spread_status": execution_spread_status,
        "execution_spread_score": spread_score,
        "median_volume_20d": med20,
        "mean_volume_20d": mean20,
        "median_to_mean_volume_ratio": ratio,
        # raw metadata fields
        "spread_pct": metadata.get("spread_pct"),
        "bid": bid_ask["bid"],
        "ask": bid_ask["ask"],
        # validated quote fields
        "bid_ask_valid": bid_ask["bid_ask_valid"],
        "bid_ask_warning": bid_ask["bid_ask_warning"],
        "spread_validated_pct": spread_validated_pct,
        "quote_status": bid_ask["quote_status"],
        "execution_quote_quality": bid_ask["execution_quote_quality"],
        "average_volume_yf": metadata.get("average_volume"),
        "average_volume_10d_yf": metadata.get("average_volume_10d"),
        "regular_market_volume_yf": metadata.get("regular_market_volume"),
        "liquidity_pass": liquidity_pass,
        "liquidity_score": liquidity_score,
        "liquidity_warning": "; ".join(warnings),
    }
