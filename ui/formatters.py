from __future__ import annotations

import math
from typing import Any


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except Exception:
        pass
    text = str(value).strip()
    return text.lower() in {"", "nan", "none", "null"}


def _to_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    return None if math.isnan(number) else number


def safe_display_text(value: Any) -> str:
    return "N/A" if _is_missing(value) else str(value).strip()


def format_status_badge(status: Any) -> str:
    text = safe_display_text(status).upper()
    if text == "N/A":
        return "UNKNOWN"
    return text


def format_number(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "N/A"
    return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"


def format_percent(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "N/A"
    if abs(number) <= 1:
        number *= 100
    return f"{number:.2f}%"


def format_price(value: Any) -> str:
    number = _to_float(value)
    return "N/A" if number is None else f"${number:,.2f}"


def format_score(value: Any) -> str:
    number = _to_float(value)
    return "N/A" if number is None else f"{number:.1f}"


def compact_reason_list(value: Any) -> str:
    if _is_missing(value):
        return "None"
    if isinstance(value, list):
        items = [safe_display_text(item) for item in value if not _is_missing(item)]
    else:
        text = str(value)
        separators = [";", "|", ","]
        for separator in separators:
            if separator in text:
                items = [item.strip() for item in text.split(separator) if item.strip()]
                break
        else:
            items = [text.strip()]
    return "None" if not items else "; ".join(items[:5])


def status_to_streamlit_level(status: Any) -> str:
    text = format_status_badge(status)
    if text == "FAIL":
        return "error"
    if text == "WARN":
        return "warning"
    if text in {"PASS", "AVAILABLE"}:
        return "success"
    if text in {"MISSING", "EMPTY"}:
        return "info"
    return "warning"
