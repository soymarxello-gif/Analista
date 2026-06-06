from __future__ import annotations
import pandas as pd


def _num(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _clip01(x: float) -> float:
    return max(0.0, min(float(x), 1.0))


def _score_put_call_volume_ratio(pc: float | None) -> float:
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
    cfg = config.get('options_flow', {})
    min_volume = cfg.get('min_total_option_volume', 100)
    min_oi = cfg.get('min_total_option_open_interest', 1000)
    total_volume = total_volume or 0
    total_oi = total_oi or 0
    volume_score = _clip01(total_volume / min_volume) if min_volume else 0.5
    oi_score = _clip01(total_oi / min_oi) if min_oi else 0.5
    return 0.50 * volume_score + 0.50 * oi_score


def score_options_flow(metrics: dict, spot: float | None, config: dict) -> dict:
    if not config.get('options_flow', {}).get('enabled', False):
        return {'options_score': 0.5, 'options_bias': 'NEUTRAL_DISABLED', 'options_confidence': 'LOW', 'options_warning': 'options_flow desactivado'}
    if not metrics or not metrics.get('options_data_available', False):
        return {'options_score': 0.5, 'options_bias': 'NEUTRAL_NO_DATA', 'options_confidence': 'LOW', 'options_warning': metrics.get('options_warning', 'sin datos de opciones') if metrics else 'sin datos de opciones'}

    pc_volume = _num(metrics.get('put_call_volume_ratio'))
    call_volume_share = _num(metrics.get('call_volume_share'))
    near_call_oi_share = _num(metrics.get('near_call_oi_share'))
    max_call_oi_strike = _num(metrics.get('max_call_oi_strike'))
    atm_iv = _num(metrics.get('atm_implied_volatility'))
    total_volume = _num(metrics.get('total_option_volume'), 0)
    total_oi = _num(metrics.get('total_option_open_interest'), 0)

    pc_score = _score_put_call_volume_ratio(pc_volume)
    call_share_score = _score_call_share(call_volume_share)
    near_oi_score = _score_near_call_oi_share(near_call_oi_share)
    call_wall_score = _score_call_wall_position(max_call_oi_strike, spot)
    iv_score = _score_iv(atm_iv)
    liquidity_score = _score_options_liquidity(total_volume, total_oi, config)

    weights = config.get('options_flow', {}).get('weights', {})
    score = (
        weights.get('put_call_volume_ratio', 0.25) * pc_score +
        weights.get('call_volume_share', 0.20) * call_share_score +
        weights.get('near_call_oi_share', 0.20) * near_oi_score +
        weights.get('call_wall_position', 0.15) * call_wall_score +
        weights.get('iv_risk', 0.10) * iv_score +
        weights.get('options_liquidity', 0.10) * liquidity_score
    )
    score = _clip01(score)
    bias = 'BULLISH' if score >= 0.65 else 'BEARISH' if score <= 0.40 else 'NEUTRAL'
    confidence = 'HIGH' if liquidity_score >= 0.80 else 'MEDIUM' if liquidity_score >= 0.45 else 'LOW'
    warning = metrics.get('options_warning') or ''
    crowded = False
    if pc_volume is not None and pc_volume < config.get('options_flow', {}).get('extreme_bullish_put_call_below', 0.35):
        crowded = True
        warning = (warning + '; ' if warning else '') + 'put/call extremadamente bajo: posible crowded trade'
    return {'options_score': round(score, 4), 'options_bias': bias, 'options_confidence': confidence, 'options_crowded_bullish': crowded, 'options_warning': warning}
