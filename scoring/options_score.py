from __future__ import annotations

import pandas as pd


def _num(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _metric(metrics: dict, *keys: str, default=None):
    for key in keys:
        if key in metrics:
            value = _num(metrics.get(key), None)
            if value is not None:
                return value
    return default


def _clip01(x: float) -> float:
    return max(0.0, min(float(x), 1.0))


def _confidence_multiplier(confidence: str) -> float:
    confidence = _text(confidence).upper()
    if confidence == "HIGH":
        return 1.0
    if confidence == "MEDIUM":
        return 0.70
    if confidence == "LOW":
        return 0.35
    return 0.0


def _liquidity_multiplier(liquidity_score: float | None) -> float:
    liquidity_score = _num(liquidity_score, None)
    if liquidity_score is None:
        return 0.80
    if liquidity_score < 0.25:
        return 0.35
    if liquidity_score < 0.50:
        return 0.60
    if liquidity_score < 0.70:
        return 0.80
    return 1.0


def calculate_options_score_adjustment(options_data: dict, config: dict | None = None) -> dict:
    """
    Convert options bias/confidence/liquidity into a conservative score adjustment.

    The returned adjustment is intentionally small and must never be interpreted
    as a trading signal or an execution gate.
    """
    config = config or {}
    cfg = config.get("options_flow", {})
    max_abs_adjustment = float(cfg.get("max_score_adjustment", 0.08))

    bias = _text(options_data.get("options_bias")).upper() or "UNKNOWN_OPTIONS_FLOW"
    confidence = _text(options_data.get("options_confidence")).upper() or "UNKNOWN"
    liquidity_score = _num(options_data.get("options_liquidity_score"), None)
    base_score = _num(options_data.get("options_score"), 0.5)

    confidence_mult = _confidence_multiplier(confidence)
    liquidity_mult = _liquidity_multiplier(liquidity_score)
    impact_mult = confidence_mult * liquidity_mult

    raw_adjustment = 0.0
    contrarian_adjustment = 0.0
    score_reason = "options_neutral"
    contrarian_reason = ""
    risk_flag = ""

    if bias == "UNKNOWN_OPTIONS_FLOW":
        score_reason = "options_unknown"
    elif bias == "NO_OPTIONS_AVAILABLE":
        score_reason = "options_not_listed_neutral"
    elif bias == "NEUTRAL_WITH_DATA":
        if confidence in {"MEDIUM", "HIGH"} and (liquidity_score or 0.0) >= 0.65:
            raw_adjustment = 0.01
            score_reason = "options_neutral_liquid_slight_positive"
        else:
            score_reason = "options_neutral_with_data"
    elif bias == "BULLISH_WITH_DATA":
        raw_adjustment = 0.06
        score_reason = "options_bullish_moderate"
    elif bias == "BEARISH_WITH_DATA":
        raw_adjustment = -0.06
        score_reason = "options_bearish_moderate"
        risk_flag = "options_bearish_with_data"
    elif bias == "CROWDED_BULLISH":
        raw_adjustment = -0.07
        contrarian_adjustment = raw_adjustment
        score_reason = "crowded_bullish_contrarian"
        contrarian_reason = "crowded_bullish_contrarian"
        risk_flag = "crowded_bullish_contrarian"
    elif bias == "CROWDED_BEARISH":
        raw_adjustment = 0.03
        contrarian_adjustment = raw_adjustment
        score_reason = "crowded_bearish_contrarian"
        contrarian_reason = "crowded_bearish_contrarian"

    adjustment = raw_adjustment * impact_mult
    adjustment = max(-max_abs_adjustment, min(max_abs_adjustment, adjustment))

    if confidence == "UNKNOWN":
        adjustment = 0.0
        contrarian_adjustment = 0.0
    elif contrarian_adjustment:
        contrarian_adjustment = adjustment

    adjusted_score = _clip01((base_score or 0.5) + adjustment)

    return {
        "options_score_raw": round(base_score or 0.5, 4),
        "options_score_adjusted": round(adjusted_score, 4),
        "options_score_adjustment": round(adjustment, 4),
        "options_score_reason": score_reason,
        "options_contrarian_adjustment": round(contrarian_adjustment, 4),
        "options_contrarian_reason": contrarian_reason,
        "options_risk_flag": risk_flag,
        "options_adjustment_impact_multiplier": round(impact_mult, 4),
    }


def _score_put_call_volume_ratio(pc: float | None) -> float:
    """
    Long-only interpretation:
    - moderately low P/C is bullish
    - extremely low P/C can be crowded/euphoric, so penalize
    - high P/C is defensive/bearish
    """
    if pc is None:
        return 0.5

    if pc < 0.35:
        return 0.35
    if 0.35 <= pc <= 0.70:
        return 1.0
    if 0.70 < pc <= 1.00:
        return 0.75
    if 1.00 < pc <= 1.30:
        return 0.50
    if 1.30 < pc <= 1.80:
        return 0.30
    return 0.15


def _score_call_share(share: float | None) -> float:
    if share is None:
        return 0.5
    return _clip01((share - 0.40) / 0.35)


def _score_near_call_oi_share(share: float | None) -> float:
    if share is None:
        return 0.5
    return _clip01((share - 0.45) / 0.35)


def _score_call_wall_position(max_call_oi_strike: float | None, spot: float | None) -> float:
    if max_call_oi_strike is None or spot is None or spot <= 0:
        return 0.5

    dist = (max_call_oi_strike - spot) / spot

    if dist < -0.02:
        return 0.25
    if -0.02 <= dist <= 0.015:
        return 0.45
    if 0.015 < dist <= 0.10:
        return 0.80
    if 0.10 < dist <= 0.25:
        return 0.65
    return 0.50


def _score_iv(atm_iv: float | None) -> float:
    if atm_iv is None:
        return 0.5
    if atm_iv < 0.30:
        return 0.80
    if atm_iv < 0.60:
        return 0.70
    if atm_iv < 0.90:
        return 0.55
    if atm_iv < 1.20:
        return 0.35
    return 0.20


def _score_options_liquidity(total_volume: float | None, total_oi: float | None, config: dict) -> float:
    cfg = config.get("options_flow", {})
    medium_volume = cfg.get("medium_total_option_volume", 300)
    medium_oi = cfg.get("medium_total_option_open_interest", 1000)
    high_volume = cfg.get("high_total_option_volume", 1000)
    high_oi = cfg.get("high_total_option_open_interest", 5000)

    total_volume = total_volume or 0
    total_oi = total_oi or 0

    if total_volume >= high_volume and total_oi >= high_oi:
        return 1.0
    if total_volume >= medium_volume and total_oi >= medium_oi:
        return 0.65

    volume_score = _clip01(total_volume / medium_volume) if medium_volume else 0.5
    oi_score = _clip01(total_oi / medium_oi) if medium_oi else 0.5
    return 0.40 * volume_score + 0.60 * oi_score


def _options_confidence(total_volume: float | None, total_oi: float | None, config: dict) -> str:
    cfg = config.get("options_flow", {})
    total_volume = total_volume or 0
    total_oi = total_oi or 0

    high_volume = cfg.get("high_total_option_volume", 1000)
    high_oi = cfg.get("high_total_option_open_interest", 5000)
    medium_volume = cfg.get("medium_total_option_volume", 300)
    medium_oi = cfg.get("medium_total_option_open_interest", 1000)

    if total_volume >= high_volume and total_oi >= high_oi:
        return "HIGH"
    if total_volume >= medium_volume and total_oi >= medium_oi:
        return "MEDIUM"
    return "LOW"


def score_options_flow(metrics: dict, spot: float | None, config: dict) -> dict:
    """
    Convert option-chain metrics into a 0-1 confirmation score.
    This is not a trading signal by itself.

    Phase 1.2:
    - Extremely low put/call can no longer remain strongly BULLISH.
    bias = cfg.get("crowded_bullish_bias", "CROWDED_BULLISH")
    """
    if not config.get("options_flow", {}).get("enabled", False):
        return {
            "options_score": 0.5,
            "options_bias": "UNKNOWN_OPTIONS_FLOW",
            "options_confidence": "UNKNOWN",
            "options_crowded_bullish": False,
            "options_crowded_bearish": False,
            "options_liquidity_score": 0.0,
            "options_warning": "options_flow desactivado",
            "options_notes": "options_flow desactivado; no se usa como señal operativa",
        }

    options_available = bool(
        metrics
        and metrics.get("options_available", metrics.get("options_data_available", False))
    )

    if not metrics or not options_available:
        error = _text(metrics.get("options_error")) if metrics else ""
        warning = _text(metrics.get("options_warning")) if metrics else "sin datos de opciones"
        no_options_errors = {"no_options_listed", "no_expirations", "no_options_available"}
        bias = "NO_OPTIONS_AVAILABLE" if error in no_options_errors else "UNKNOWN_OPTIONS_FLOW"
        notes = warning
        if bias == "NO_OPTIONS_AVAILABLE":
            notes = "sin opciones listadas o sin vencimientos disponibles en Yahoo"
        elif error:
            notes = f"datos de opciones no disponibles: {error}; {warning}".strip("; ")

        return {
            "options_score": 0.5,
            "options_bias": bias,
            "options_confidence": "UNKNOWN",
            "options_crowded_bullish": False,
            "options_crowded_bearish": False,
            "options_liquidity_score": 0.0,
            "options_warning": warning,
            "options_notes": notes,
        }

    cfg = config.get("options_flow", {})

    pc_volume = _num(metrics.get("put_call_volume_ratio"))
    pc_oi = _metric(metrics, "options_put_call_oi_ratio", "put_call_oi_ratio")
    call_volume_share = _num(metrics.get("call_volume_share"))
    near_call_oi_share = _metric(metrics, "near_call_oi_share")
    max_call_oi_strike = _metric(metrics, "options_top_call_strike", "max_call_oi_strike")
    atm_iv = _num(metrics.get("atm_implied_volatility"))
    total_volume = _num(metrics.get("total_option_volume"), 0)
    total_call_oi = _metric(metrics, "options_total_call_oi", "call_open_interest", default=0)
    total_put_oi = _metric(metrics, "options_total_put_oi", "put_open_interest", default=0)
    total_oi = _num(metrics.get("total_option_open_interest"), None)
    if total_oi is None:
        total_oi = (total_call_oi or 0) + (total_put_oi or 0)

    pc_score = _score_put_call_volume_ratio(pc_volume)
    call_share_score = _score_call_share(call_volume_share)
    near_oi_score = _score_near_call_oi_share(near_call_oi_share)
    call_wall_score = _score_call_wall_position(max_call_oi_strike, spot)
    iv_score = _score_iv(atm_iv)
    liquidity_score = _score_options_liquidity(total_volume, total_oi, config)

    weights = cfg.get("weights", {})
    score = (
        weights.get("put_call_volume_ratio", 0.25) * pc_score
        + weights.get("call_volume_share", 0.20) * call_share_score
        + weights.get("near_call_oi_share", 0.20) * near_oi_score
        + weights.get("call_wall_position", 0.15) * call_wall_score
        + weights.get("iv_risk", 0.10) * iv_score
        + weights.get("options_liquidity", 0.10) * liquidity_score
    )

    score = _clip01(score)

    warning = metrics.get("options_warning") or ""
    notes = metrics.get("options_notes") or warning or ""

    crowded_bullish = False
    crowded_bearish = False

    bullish_crowded_threshold = cfg.get("extreme_bullish_put_call_below", 0.35)
    bearish_crowded_threshold = cfg.get("extreme_bearish_put_call_above", 1.80)
    ratio_for_sentiment = pc_oi if pc_oi is not None else pc_volume

    if ratio_for_sentiment is not None and ratio_for_sentiment < bullish_crowded_threshold:
        crowded_bullish = True
        warning = (warning + "; " if warning else "") + "put/call extremadamente bajo: posible crowded trade / crowded bullish trade"
        notes = (
            (notes + "; " if notes else "")
            + "Extremo bullish en opciones; lectura contrarian: no tratar como confirmacion limpia."
        )

        # Crowded bullish flow should not be labelled clean bullish.
        cap = cfg.get("crowded_bullish_score_cap", 0.60)
        score = min(score, cap)

    if ratio_for_sentiment is not None and ratio_for_sentiment > bearish_crowded_threshold:
        crowded_bearish = True
        warning = (warning + "; " if warning else "") + "put/call extremadamente alto: posible crowded bearish trade"
        notes = (
            (notes + "; " if notes else "")
            + "Extremo bearish en opciones; lectura contrarian: posible pesimismo crowded, requiere confirmacion de precio."
        )

    confidence = _options_confidence(total_volume, total_oi, config)
    min_total_volume = cfg.get("min_total_option_volume", 0)
    min_total_oi = cfg.get("min_total_option_open_interest", 0)
    low_liquidity = total_volume < min_total_volume or total_oi < min_total_oi

    if low_liquidity:
        bias = "NEUTRAL_WITH_DATA"
        confidence = "LOW"
        score = 0.5
        notes = (
            (notes + "; " if notes else "")
            + "datos disponibles pero con liquidez/OI bajo; se informa neutral y no se usa como confirmacion fuerte"
        )
    elif crowded_bullish:
        bias = "CROWDED_BULLISH"
    elif crowded_bearish:
        bias = "CROWDED_BEARISH"
    elif score >= 0.65:
        bias = "BULLISH_WITH_DATA"
    elif score <= 0.40:
        bias = "BEARISH_WITH_DATA"
    else:
        bias = "NEUTRAL_WITH_DATA"

    return {
        "options_score": round(score, 4),
        "options_bias": bias,
        "options_confidence": confidence,
        "options_crowded_bullish": crowded_bullish,
        "options_crowded_bearish": crowded_bearish,
        "options_liquidity_score": round(liquidity_score, 4),
        "options_warning": warning,
        "options_notes": notes,
    }
