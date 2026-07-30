from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from data.technical_bars import closed_weekly_close


OPERABLE_TRAJECTORY_STATES = {"ACCELERATING", "IMPROVING_STEADY"}
DECELERATING_TRAJECTORY_STATES = {"IMPROVING_BUT_DECELERATING", "DECLINING"}


def _empty(prefix: str) -> dict[str, Any]:
    return {
        f"{prefix}_macd_trajectory_state": "UNKNOWN",
        f"{prefix}_macd_trajectory_confidence": "UNKNOWN",
        f"{prefix}_macd_hist_normalized": None,
        f"{prefix}_macd_hist_slope": None,
        f"{prefix}_macd_hist_previous_slope": None,
        f"{prefix}_macd_hist_acceleration": None,
        f"{prefix}_macd_hist_noise_band": None,
        f"{prefix}_macd_hist_persistence": None,
        f"{prefix}_macd_non_decelerating": False,
    }


def _weighted_slope(values: np.ndarray) -> tuple[float, float]:
    x = np.arange(len(values), dtype=float)
    weights = np.arange(1, len(values) + 1, dtype=float)
    x_mean = float(np.average(x, weights=weights))
    y_mean = float(np.average(values, weights=weights))
    denominator = float(np.sum(weights * (x - x_mean) ** 2))
    if denominator <= 0:
        return 0.0, 0.0
    slope = float(np.sum(weights * (x - x_mean) * (values - y_mean)) / denominator)
    fitted = y_mean + slope * (x - x_mean)
    residual = float(np.sum(weights * (values - fitted) ** 2))
    total = float(np.sum(weights * (values - y_mean) ** 2))
    r_squared = 1.0 if total <= 1e-15 else max(0.0, 1.0 - residual / total)
    return slope, r_squared


def analyze_histogram_trajectory(
    histogram: pd.Series,
    reference: pd.Series,
    *,
    prefix: str,
    slope_window: int = 4,
    noise_lookback: int = 20,
) -> dict[str, Any]:
    """
    Classify MACD histogram direction using normalized slope, acceleration and noise.

    The histogram is normalized by price so the same algorithm can compare assets
    with different nominal prices. A negative acceleration inside the observed
    noise band is treated as steady improvement, not as a false deceleration.
    """
    if histogram is None or reference is None:
        return _empty(prefix)

    frame = pd.concat(
        [
            pd.to_numeric(histogram, errors="coerce").rename("hist"),
            pd.to_numeric(reference, errors="coerce").rename("reference"),
        ],
        axis=1,
    ).dropna()
    frame = frame[frame["reference"].abs() > 1e-12]
    minimum = max(2 * slope_window + 1, 9)
    if len(frame) < minimum:
        return _empty(prefix)

    normalized = (100.0 * frame["hist"] / frame["reference"].abs()).astype(float)
    values = normalized.to_numpy(dtype=float)
    current_values = values[-slope_window:]
    previous_values = values[-(slope_window + 1) : -1]
    current_slope, current_r2 = _weighted_slope(current_values)
    previous_slope, previous_r2 = _weighted_slope(previous_values)
    acceleration = current_slope - previous_slope

    changes = np.diff(values[-min(len(values), noise_lookback + 1) :])
    if len(changes):
        median_change = float(np.median(changes))
        mad = float(np.median(np.abs(changes - median_change)))
        robust_noise = 1.4826 * mad
    else:
        robust_noise = 0.0
    noise_band = max(robust_noise * 0.35, 1e-8)
    acceleration_band = max(robust_noise * 0.15, 1e-8)

    recent_changes = np.diff(current_values)
    rising_share = float(np.mean(recent_changes > noise_band)) if len(recent_changes) else 0.0
    falling_share = float(np.mean(recent_changes < -noise_band)) if len(recent_changes) else 0.0
    persistence = rising_share - falling_share

    if current_slope > noise_band:
        if acceleration > acceleration_band:
            state = "ACCELERATING"
        elif acceleration >= -acceleration_band:
            state = "IMPROVING_STEADY"
        else:
            state = "IMPROVING_BUT_DECELERATING"
    elif current_slope < -noise_band:
        state = "DECLINING"
    elif robust_noise > 0 and abs(current_slope) <= noise_band and current_r2 < 0.35:
        state = "NOISY"
    else:
        state = "FLAT_NO_EDGE"

    fit_quality = min(current_r2, previous_r2)
    if fit_quality >= 0.75 and abs(persistence) >= 0.50:
        confidence = "HIGH"
    elif fit_quality >= 0.40 or abs(persistence) >= 0.34:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        f"{prefix}_macd_trajectory_state": state,
        f"{prefix}_macd_trajectory_confidence": confidence,
        f"{prefix}_macd_hist_normalized": float(values[-1]),
        f"{prefix}_macd_hist_slope": current_slope,
        f"{prefix}_macd_hist_previous_slope": previous_slope,
        f"{prefix}_macd_hist_acceleration": acceleration,
        f"{prefix}_macd_hist_noise_band": noise_band,
        f"{prefix}_macd_hist_persistence": persistence,
        f"{prefix}_macd_non_decelerating": state in OPERABLE_TRAJECTORY_STATES,
    }


def _weekly_macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    weekly_close = pd.to_numeric(close, errors="coerce").dropna()
    if not isinstance(weekly_close.index, pd.DatetimeIndex):
        return pd.Series(dtype=float), pd.Series(dtype=float)
    weekly_close, _ = closed_weekly_close(weekly_close)
    if len(weekly_close) < 35:
        return pd.Series(dtype=float), weekly_close
    macd = weekly_close.ewm(span=12, adjust=False).mean() - weekly_close.ewm(
        span=26, adjust=False
    ).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    return (macd - signal).dropna(), weekly_close


def analyze_multitimeframe_macd(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty or "close" not in df.columns or "macd_hist" not in df.columns:
        return {
            **_empty("daily"),
            **_empty("weekly"),
            "momentum_alignment": "UNCONFIRMED",
            "momentum_alignment_confidence": "UNKNOWN",
            "momentum_acceleration_score": 0.0,
            "momentum_persistence_score": 0.0,
            "momentum_operability_status": "INSUFFICIENT_DATA",
        }

    daily = analyze_histogram_trajectory(
        df["macd_hist"],
        df["close"],
        prefix="daily",
        slope_window=4,
        noise_lookback=20,
    )
    weekly_hist, weekly_close = _weekly_macd(df["close"])
    weekly = analyze_histogram_trajectory(
        weekly_hist,
        weekly_close,
        prefix="weekly",
        slope_window=3,
        noise_lookback=12,
    )

    daily_state = str(daily["daily_macd_trajectory_state"])
    weekly_state = str(weekly["weekly_macd_trajectory_state"])
    daily_ok = daily_state in OPERABLE_TRAJECTORY_STATES
    weekly_ok = weekly_state in OPERABLE_TRAJECTORY_STATES

    if daily_ok and weekly_ok:
        if daily_state == weekly_state == "ACCELERATING":
            alignment = "SYNCHRONIZED_ACCELERATION"
        else:
            alignment = "SYNCHRONIZED_IMPROVEMENT"
        operability = "CONFIRMED_NON_DECELERATING"
    elif daily_ok and weekly_state in {"FLAT_NO_EDGE", "NOISY", "UNKNOWN"}:
        alignment = "DAILY_LEADS_WEEKLY"
        operability = "MONITOR_MOMENTUM"
    elif weekly_ok and daily_state in {"FLAT_NO_EDGE", "NOISY", "UNKNOWN"}:
        alignment = "WEEKLY_LEADS_DAILY"
        operability = "MONITOR_MOMENTUM"
    elif (
        daily_state in DECELERATING_TRAJECTORY_STATES
        or weekly_state in DECELERATING_TRAJECTORY_STATES
    ):
        alignment = "DECELERATION_CONFLICT"
        operability = "REJECT_MOMENTUM"
    elif daily_state == "UNKNOWN" or weekly_state == "UNKNOWN":
        alignment = "UNCONFIRMED"
        operability = "INSUFFICIENT_DATA"
    else:
        alignment = "UNCONFIRMED"
        operability = "MONITOR_MOMENTUM"

    confidences = {
        str(daily["daily_macd_trajectory_confidence"]),
        str(weekly["weekly_macd_trajectory_confidence"]),
    }
    alignment_confidence = (
        "HIGH"
        if confidences == {"HIGH"}
        else "MEDIUM"
        if "UNKNOWN" not in confidences and "LOW" not in confidences
        else "LOW"
    )
    acceleration_values = [
        value
        for value in (
            daily.get("daily_macd_hist_acceleration"),
            weekly.get("weekly_macd_hist_acceleration"),
        )
        if value is not None
    ]
    persistence_values = [
        value
        for value in (
            daily.get("daily_macd_hist_persistence"),
            weekly.get("weekly_macd_hist_persistence"),
        )
        if value is not None
    ]
    acceleration_score = (
        50.0
        + 50.0
        * float(
            np.tanh(
                np.mean(acceleration_values)
                / max(
                    np.mean(
                        [
                            daily.get("daily_macd_hist_noise_band") or 1e-8,
                            weekly.get("weekly_macd_hist_noise_band") or 1e-8,
                        ]
                    ),
                    1e-8,
                )
            )
        )
        if acceleration_values
        else 0.0
    )
    persistence_score = (
        50.0 + 50.0 * float(np.mean(persistence_values))
        if persistence_values
        else 0.0
    )

    return {
        **daily,
        **weekly,
        "momentum_alignment": alignment,
        "momentum_alignment_confidence": alignment_confidence,
        "momentum_acceleration_score": round(max(0.0, min(100.0, acceleration_score)), 2),
        "momentum_persistence_score": round(max(0.0, min(100.0, persistence_score)), 2),
        "momentum_operability_status": operability,
    }
