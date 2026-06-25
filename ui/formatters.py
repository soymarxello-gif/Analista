from __future__ import annotations

import math
from typing import Any

import pandas as pd


COLUMN_LABELS_ES = {
    "ticker": "Ticker",
    "company": "Empresa",
    "rank": "Ranking",
    "signal": "Señal",
    "recommendation": "Recomendación",
    "checklist_status": "Estado checklist",
    "setup_type": "Setup",
    "sector": "Sector",
    "industry": "Industria",
    "final_trade_score": "Score operativo",
    "checklist_score": "Score checklist",
    "setup_quality_score": "Calidad setup",
    "asset_quality_score": "Calidad activo",
    "institutional_score": "Score institucional",
    "options_score": "Score opciones",
    "options_bias": "Lectura opciones",
    "options_confidence": "Confianza opciones",
    "quote_status": "Estado quote",
    "execution_quote_quality": "Calidad ejecución",
    "actionable_entry": "Entrada",
    "actionable_stop": "Stop",
    "actionable_target": "Target",
    "rr": "R/R",
    "stop_atr_status": "Stop vs ATR",
    "earnings_date": "Earnings",
    "next_earnings_date": "Próx. earnings",
    "penalty_reasons": "Penalizaciones",
    "reason_summary": "Resumen",
    "warnings": "Alertas",
    "manual_decision": "Decisión manual",
    "followup_status": "Estado seguimiento",
    "followup_decision": "Decisión seguimiento",
    "journal_id": "ID journal",
    "run_date": "Fecha",
    "path": "Reporte",
    "status": "Estado",
    "exists": "Existe",
    "size_bytes": "Tamaño bytes",
    "modified": "Modificado",
    "error": "Error",
}

NEGATIVE_TRADING_VALUES = {
    "AVOID",
    "VETO",
    "LOW",
    "MISSING",
    "INVALID",
    "STALE_POSSIBLE",
    "BLOCKED",
    "DATA_UNAVAILABLE",
    "AVOID_EXECUTION_RISK",
    "STOP_HIT_REVIEW_CLOSE",
    "INVALIDATED_REVIEW",
    "FAIL",
}

WARNING_TRADING_VALUES = {
    "WARN",
    "WATCHLIST",
    "RECHECK_LIVE_QUOTE",
    "NEEDS_LIVE_QUOTE_RECHECK",
    "REVIEW_MANUALLY",
    "KEEP_RECHECK",
    "REVIEW_NEAR_STOP",
    "REVIEW_NEAR_TARGET",
}

POSITIVE_TRADING_VALUES = {
    "PASS",
    "VALID",
    "HIGH",
    "HIGH_QUALITY_REVIEW",
    "EXECUTION_OK_REVIEW_MANUALLY",
    "HOLD_PAPER",
    "TARGET_HIT_REVIEW_CLOSE",
}


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
    return f"{number:,.2f}"


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
    return "N/A" if number is None else f"{number:.2f}"


def compact_reason_list(value: Any) -> str:
    if _is_missing(value):
        return "Sin datos"
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
    return "Sin datos" if not items else "; ".join(items[:5])


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


def spanish_column_label(column: Any) -> str:
    text = str(column)
    return COLUMN_LABELS_ES.get(text, text.replace("_", " ").strip().capitalize())


def is_negative_trading_value(value: Any) -> bool:
    text = safe_display_text(value).upper()
    if text in NEGATIVE_TRADING_VALUES:
        return True
    return any(token in text for token in ["VETO", "BLOCKED", "INVALID", "UNAVAILABLE", "RISK"])


def is_warning_trading_value(value: Any) -> bool:
    text = safe_display_text(value).upper()
    if is_negative_trading_value(text):
        return False
    return text in WARNING_TRADING_VALUES or any(token in text for token in ["RECHECK", "REVIEW", "WARN"])


def trading_value_class(value: Any) -> str:
    text = safe_display_text(value).upper()
    if is_negative_trading_value(text):
        return "negative"
    if is_warning_trading_value(text):
        return "warning"
    if text in POSITIVE_TRADING_VALUES:
        return "positive"
    return "neutral"


def format_cell_value(value: Any) -> Any:
    number = _to_float(value)
    if number is None:
        return safe_display_text(value)
    return f"{number:,.2f}"


def prepare_display_dataframe(df: pd.DataFrame, *, columns: list[str] | None = None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if columns:
        selected = [column for column in columns if column in out.columns]
        out = out[selected] if selected else out
    for column in out.columns:
        numeric = pd.to_numeric(out[column], errors="coerce")
        if numeric.notna().any() and numeric.notna().sum() >= max(1, int(len(out) * 0.5)):
            out[column] = numeric.round(2)
    return out.rename(columns={column: spanish_column_label(column) for column in out.columns})


def dataframe_column_config(df: pd.DataFrame) -> dict:
    config = {}
    price_words = {"entrada", "stop", "target", "precio", "bid", "ask"}
    percent_words = {"pct", "porcentaje", "%", "spread"}
    for column in df.columns:
        lower = str(column).lower()
        if pd.api.types.is_numeric_dtype(df[column]):
            if any(word in lower for word in price_words):
                config[column] = {"format": "$%.2f"}
            elif any(word in lower for word in percent_words):
                config[column] = {"format": "%.2f"}
            else:
                config[column] = {"format": "%.2f"}
    return config


def style_negative_trading_values(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def _style(value: Any) -> str:
        value_class = trading_value_class(value)
        if value_class == "negative":
            return "color: #F87171; font-weight: 700;"
        if value_class == "warning":
            return "color: #FBBF24; font-weight: 650;"
        if value_class == "positive":
            return "color: #34D399; font-weight: 650;"
        return ""

    return df.style.map(_style).format(precision=2, na_rep="N/A")
