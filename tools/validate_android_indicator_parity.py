from __future__ import annotations

import json
import math
from pathlib import Path


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "android"
    / "app"
    / "src"
    / "test"
    / "resources"
    / "canonical_indicator_parity.json"
)


def ema_series(values: list[float], period: int) -> list[float]:
    if period <= 0 or len(values) < period:
        raise ValueError("invalid EMA period")
    result = [math.nan] * len(values)
    previous = sum(values[:period]) / period
    result[period - 1] = previous
    alpha = 2.0 / (period + 1.0)
    for index in range(period, len(values)):
        previous = alpha * values[index] + (1.0 - alpha) * previous
        result[index] = previous
    return result


def rsi_wilder(values: list[float], period: int) -> float:
    if len(values) <= period:
        raise ValueError("insufficient RSI history")
    changes = [current - previous for previous, current in zip(values, values[1:])]
    average_gain = sum(max(change, 0.0) for change in changes[:period]) / period
    average_loss = sum(max(-change, 0.0) for change in changes[:period]) / period
    for change in changes[period:]:
        average_gain = ((period - 1) * average_gain + max(change, 0.0)) / period
        average_loss = ((period - 1) * average_loss + max(-change, 0.0)) / period
    if average_loss == 0.0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def atr_wilder(closes: list[float], high_offset: float, low_offset: float, period: int) -> float:
    true_ranges: list[float] = []
    for index, close in enumerate(closes):
        high = close + high_offset
        low = close - low_offset
        if index == 0:
            true_range = high - low
        else:
            previous_close = closes[index - 1]
            true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
        true_ranges.append(true_range)
    atr = sum(true_ranges[:period]) / period
    for true_range in true_ranges[period:]:
        atr = ((period - 1) * atr + true_range) / period
    return atr


def macd(values: list[float]) -> tuple[float, float]:
    ema12 = ema_series(values, 12)
    ema26 = ema_series(values, 26)
    macd_values = [ema12[index] - ema26[index] for index in range(25, len(values))]
    signal = ema_series(macd_values, 9)
    return macd_values[-1], signal[-1]


def validate() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fixture.get("schemaVersion") != "canonical-indicator-parity-1":
        raise AssertionError("unexpected parity fixture version")
    closes = [float(value) for value in fixture["closes"]]
    expected = fixture["expected"]
    tolerance = float(fixture["tolerance"])
    macd_value, signal_value = macd(closes)
    actual = {
        "rsi6": rsi_wilder(closes, 6),
        "rsi14": rsi_wilder(closes, 14),
        "ema20": ema_series(closes, 20)[-1],
        "ema50": ema_series(closes, 50)[-1],
        "atr14": atr_wilder(closes, float(fixture["highOffset"]), float(fixture["lowOffset"]), 14),
        "macd": macd_value,
        "macdSignal": signal_value,
    }
    failures = {
        key: (float(expected[key]), value)
        for key, value in actual.items()
        if not math.isclose(float(expected[key]), value, rel_tol=0.0, abs_tol=tolerance)
    }
    if failures:
        raise AssertionError(f"Android/Python indicator parity mismatch: {failures}")
    print(f"canonical indicator parity OK: {len(actual)} metrics")


if __name__ == "__main__":
    validate()
