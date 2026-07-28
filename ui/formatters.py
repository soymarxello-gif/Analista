from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd


COLUMN_LABELS_ES = {
    "ticker": "Ticker",
    "company": "Empresa",
    "rank": "Ranking",
    "signal": "Señal interna",
    "recommendation": "Revisión sugerida",
    "checklist_status": "Checklist",
    "operational_state": "Estado operativo",
    "setup_type": "Setup",
    "sector": "Sector",
    "industry": "Industria",
    "final_trade_score": "Score operativo",
    "asset_attractiveness_score": "Score activo",
    "operational_readiness_score": "Readiness",
    "operational_readiness_bucket": "Grupo readiness",
    "timing_quality_score": "Score timing",
    "momentum_confirmation_score": "Score momentum",
    "execution_readiness_status": "Estado operativo",
    "technical_prefilter_status": "Prefiltro técnico",
    "technical_prefilter_reason": "Razón prefiltro",
    "daily_macd_prefilter_status": "MACD diario prefiltro",
    "weekly_macd_prefilter_status": "MACD semanal prefiltro",
    "ema20_extension_prefilter_status": "EMA20 prefiltro",
    "ema20_extension_reference_source": "Referencia extensión",
    "scenario_status": "Diagnóstico escenario",
    "scenario_confidence": "Confianza escenario",
    "scenario_operability": "Operabilidad escenario",
    "momentum_state": "Momentum",
    "extension_state": "Extensión",
    "ema20_extension_status": "Extensión EMA20",
    "entry_timing_status": "Timing entrada",
    "macd_histogram_state": "MACD histograma",
    "weekly_macd_histogram_state": "MACD semanal",
    "weekly_macd_hist_improving": "MACD semanal mejora",
    "weekly_macd_hist": "MACD semanal hist.",
    "weekly_macd_hist_change_1w": "MACD semanal 1s",
    "weekly_macd_hist_change_2w": "MACD semanal 2s",
    "sector_benchmark_symbol": "ETF sector",
    "sector_weekly_macd_hist": "MACD sector hist.",
    "sector_weekly_macd_slope_1w": "MACD sector pendiente",
    "sector_weekly_macd_prev_slope_1w": "MACD sector pendiente previa",
    "sector_weekly_macd_acceleration": "MACD sector aceleración",
    "sector_weekly_macd_state": "MACD semanal sector",
    "sector_weekly_macd_acceleration_state": "Aceleración sector",
    "sector_context_status": "Contexto sector",
    "sector_context_reason": "Razón sector",
    "timing_penalty_reason": "Penalización timing",
    "momentum_penalty_reason": "Penalización momentum",
    "engine_block_reason": "Bloqueo motor",
    "engine_recommendation": "Lectura motor",
    "required_confirmation": "Confirmación requerida",
    "technical_rsi": "RSI técnico",
    "technical_macd_hist": "MACD hist.",
    "technical_macd_hist_change_3d": "MACD hist. 3d",
    "technical_ema20": "EMA20",
    "technical_distance_ema20_atr": "Dist. EMA20 ATR",
    "technical_distance_ema20_pct": "Dist. EMA20 %",
    "technical_ema20_slope_5d_pct": "Pendiente EMA20 5d",
    "technical_distance_sma20_atr": "Dist. SMA20 ATR",
    "technical_trigger_distance_atr": "Dist. gatillo ATR",
    "technical_relative_volume": "Volumen relativo",
    "scenario_entry": "Entrada diagnóstica",
    "scenario_stop": "Stop diagnóstico",
    "scenario_target": "Target diagnóstico",
    "checklist_score": "Score checklist",
    "setup_quality_score": "Calidad setup",
    "asset_quality_score": "Calidad activo",
    "institutional_score": "Score institucional",
    "options_score": "Metrica opciones",
    "options_bias": "Lectura opciones",
    "options_confidence": "Confianza opciones",
    "options_scoring_status": "Uso opciones",
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
    "run_date": "Fecha",
    "path": "Reporte",
    "status": "Estado",
    "exists": "Existe",
    "size_bytes": "Tamaño bytes",
    "modified": "Modificado",
    "error": "Error",
    "series": "Serie",
    "code": "Código",
    "latest": "Último",
    "latest_date": "Fecha dato",
    "age_days": "Edad días",
    "change": "Cambio",
    "provider": "Proveedor",
    "cache_status": "Caché",
    "fallback_used": "Fallback",
    "event_date": "Fecha evento",
    "event_time": "Hora",
    "timezone": "Zona",
    "event": "Evento",
    "description": "Descripción",
    "importance": "Importancia",
    "source": "Fuente",
}

NEGATIVE_TRADING_VALUES = {
    "AVOID",
    "VETO",
    "ROJO",
    "LOW",
    "MISSING",
    "INVALID",
    "STALE_POSSIBLE",
    "BLOCKED",
    "DATA_UNAVAILABLE",
    "AVOID_EXECUTION_RISK",
    "EXECUTION_DATA_BLOCKED",
    "NOT_OPERABLE",
    "STOP_HIT_REVIEW_CLOSE",
    "INVALIDATED_REVIEW",
    "FAIL",
    "NASDAQ_SYSTEMIC_SIGMA",
    "NASDAQ_CAPITULATION_PHI",
    "LATE_ENTRY_OVEREXTENDED",
    "WEAK_MOMENTUM",
    "STRUCTURE_INVALID",
    "CONTEXT_CONFLICT",
    "OVEREXTENDED",
    "LATE_ENTRY",
    "DECELERATING",
    "MACD_HIST_DETERIORATING",
    "WEEKLY_MACD_HIST_BEARISH",
    "WEEKLY_MACD_HIST_DECELERATING",
    "SECTOR_MACD_BEARISH",
    "SECTOR_MACD_DECELERATING",
    "RISK",
    "TECHNICAL_PREFILTER_FAILED",
    "RR_BELOW_MINIMUM",
}

WARNING_TRADING_VALUES = {
    "WARN",
    "WATCHLIST",
    "AMARILLO",
    "RECHECK_LIVE_QUOTE",
    "NEEDS_LIVE_QUOTE_RECHECK",
    "REVIEW_MANUALLY",
    "KEEP_RECHECK",
    "REVIEW_NEAR_STOP",
    "REVIEW_NEAR_TARGET",
    "WITHIN_3_DAYS",
    "WITHIN_1_DAY",
    "TODAY",
    "NASDAQ_DISTRIBUTION_OMEGA",
    "WAIT_FOR_CONFIRMATION",
    "CAUTION",
    "MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO",
    "MACD_HIST_FLATTENING",
    "MACD_HIST_MIXED",
    "WEEKLY_MACD_HIST_MIXED",
    "WEEKLY_MACD_HIST_UNKNOWN",
    "SECTOR_MACD_IMPROVING_BUT_DECELERATING",
    "SECTOR_MACD_MIXED",
    "SECTOR_MACD_UNKNOWN",
    "WATCH",
    "UNKNOWN",
}

POSITIVE_TRADING_VALUES = {
    "PASS",
    "VALID",
    "VERDE",
    "CLEAR",
    "HIGH",
    "HIGH_QUALITY_REVIEW",
    "EXECUTION_OK_REVIEW_MANUALLY",
    "EXECUTION_READY_REVIEW",
    "TARGET_HIT_REVIEW_CLOSE",
    "NASDAQ_NORMAL",
    "VALID_TRIGGER",
    "HEALTHY",
    "ON_TIME",
    "STRONG",
    "IMPROVING",
    "MACD_HIST_POSITIVE_EXPANDING",
    "WEEKLY_MACD_HIST_IMPROVING",
    "SECTOR_MACD_ACCELERATING",
    "SECTOR_MACD_IMPROVING",
    "SUPPORTIVE",
    "ACCELERATING",
}

STATUS_LABELS_ES = {
    "AVOID": "Evitar",
    "VETO": "Veto",
    "LOW": "Baja",
    "MISSING": "Sin datos",
    "INVALID": "Inválido",
    "STALE_POSSIBLE": "Posible dato antiguo",
    "BLOCKED": "Bloqueado",
    "DATA_UNAVAILABLE": "Datos no disponibles",
    "WATCHLIST": "Monitoreo",
    "RECHECK_LIVE_QUOTE": "Revisar quote en vivo",
    "NEEDS_LIVE_QUOTE_RECHECK": "Requiere quote en vivo",
    "REVIEW_MANUALLY": "Revisión manual",
    "HIGH_QUALITY_REVIEW": "Alta calidad para revisión",
    "EXECUTION_READY_REVIEW": "Listo para revisión",
    "EXECUTION_DATA_BLOCKED": "Ejecución bloqueada por datos",
    "NOT_OPERABLE": "No operable",
    "VALID": "Válido",
    "HIGH": "Alta",
    "PASS": "Correcto",
    "WARN": "Atención",
    "FAIL": "Fallo",
    "VERDE": "Verde",
    "AMARILLO": "Amarillo",
    "ROJO": "Rojo",
    "CLEAR": "Despejado",
    "WITHIN_3_DAYS": "Evento en 3 días",
    "WITHIN_1_DAY": "Evento en 1 día",
    "TODAY": "Evento hoy",
    "NASDAQ_NORMAL": "Nasdaq normal",
    "NASDAQ_DISTRIBUTION_OMEGA": "Distribución Nasdaq",
    "NASDAQ_SYSTEMIC_SIGMA": "Riesgo sistémico Nasdaq",
    "NASDAQ_CAPITULATION_PHI": "Capitulación Nasdaq",
    "VALID_TRIGGER": "Escenario válido",
    "WAIT_FOR_CONFIRMATION": "Esperar confirmación",
    "LATE_ENTRY_OVEREXTENDED": "Entrada tardía / sobreextendida",
    "WEAK_MOMENTUM": "Momentum débil",
    "STRUCTURE_INVALID": "Estructura inválida",
    "CONTEXT_CONFLICT": "Conflicto de contexto",
    "HEALTHY": "Sano",
    "CAUTION": "Precaución",
    "OVEREXTENDED": "Sobreextendido",
    "LATE_ENTRY": "Entrada tardía",
    "ON_TIME": "A tiempo",
    "STRONG": "Fuerte",
    "IMPROVING": "Mejorando",
    "DETERIORATING": "Deteriorando",
    "MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO": "Histograma MACD girando bajo cero",
    "MACD_HIST_POSITIVE_EXPANDING": "Histograma MACD positivo y expandiendo",
    "MACD_HIST_FLATTENING": "Histograma MACD plano",
    "MACD_HIST_DETERIORATING": "Histograma MACD deteriorando",
    "MACD_HIST_MIXED": "Histograma MACD mixto",
    "MACD_HIST_UNKNOWN": "Histograma MACD desconocido",
    "WEEKLY_MACD_HIST_IMPROVING": "MACD semanal mejorando",
    "WEEKLY_MACD_HIST_DECELERATING": "MACD semanal desacelerando",
    "WEEKLY_MACD_HIST_BEARISH": "MACD semanal bajista",
    "WEEKLY_MACD_HIST_MIXED": "MACD semanal mixto",
    "WEEKLY_MACD_HIST_UNKNOWN": "MACD semanal desconocido",
    "SECTOR_MACD_ACCELERATING": "Sector acelerando",
    "SECTOR_MACD_IMPROVING": "Sector mejorando",
    "SECTOR_MACD_IMPROVING_BUT_DECELERATING": "Sector mejora pero desacelera",
    "SECTOR_MACD_DECELERATING": "Sector desacelerando",
    "SECTOR_MACD_BEARISH": "Sector bajista",
    "SECTOR_MACD_MIXED": "Sector mixto",
    "SECTOR_MACD_UNKNOWN": "Sector desconocido",
    "SUPPORTIVE": "Apoyo sectorial",
    "WATCH": "Monitorear sector",
    "RISK": "Riesgo sectorial",
    "ACCELERATING": "Acelerando",
    "DECELERATING": "Desacelerando",
    "STABLE": "Estable",
    "FLAT": "Plano",
    "TECHNICAL_PREFILTER_FAILED": "Prefiltro técnico fallido",
    "NOT_REQUESTED_TECHNICAL_PREFILTER": "No solicitado por prefiltro",
    "OHLCV_TECHNICAL_PREFILTER": "OHLCV prefiltro técnico",
    "SMA20_FALLBACK": "Respaldo SMA20",
    "EMA20": "EMA20",
}

STATUS_VALUE_COLUMNS = {
    "signal",
    "recommendation",
    "checklist_status",
    "operational_state",
    "execution_readiness_status",
    "technical_prefilter_status",
    "daily_macd_prefilter_status",
    "weekly_macd_prefilter_status",
    "ema20_extension_prefilter_status",
    "quote_status",
    "execution_quote_quality",
    "options_bias",
    "options_confidence",
    "scenario_status",
    "scenario_confidence",
    "scenario_operability",
    "momentum_state",
    "extension_state",
    "ema20_extension_status",
    "entry_timing_status",
    "macd_histogram_state",
    "weekly_macd_histogram_state",
    "sector_weekly_macd_state",
    "sector_weekly_macd_acceleration_state",
    "sector_context_status",
    "engine_recommendation",
    "manual_decision",
    "followup_status",
    "followup_decision",
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


def display_status_label(status: Any) -> str:
    text = format_status_badge(status)
    return STATUS_LABELS_ES.get(text, text.replace("_", " ").title())


def display_status_with_code(status: Any) -> str:
    code = format_status_badge(status)
    label = display_status_label(code)
    return label if label.upper() == code else f"{label} ({code})"


def _status_code(value: Any) -> str:
    text = safe_display_text(value).upper()
    if text.endswith(")") and "(" in text:
        return text.rsplit("(", 1)[1][:-1].strip()
    return text


def format_number(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "N/A"
    return f"{number:,.2f}"


def format_count(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "N/A"
    return f"{int(round(number)):,}"


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
    text = _status_code(value)
    if text in NEGATIVE_TRADING_VALUES:
        return True
    return (
        text.startswith(("VETO_", "BLOCKED_", "INVALID_", "AVOID_"))
        or text.endswith(("_INVALID", "_UNAVAILABLE", "_BLOCKED"))
    )


def is_warning_trading_value(value: Any) -> bool:
    text = _status_code(value)
    if is_negative_trading_value(text):
        return False
    return text in WARNING_TRADING_VALUES or any(token in text for token in ["RECHECK", "REVIEW", "WARN"])


def trading_value_class(value: Any) -> str:
    text = _status_code(value)
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


def format_metric_value(label: Any, value: Any) -> str:
    label_text = str(label).lower()
    number = _to_float(value)
    if number is None:
        return safe_display_text(value)
    count_tokens = {
        "filas",
        "candidatos",
        "abiertos",
        "cerrados",
        "pendientes",
        "exports",
        "outcomes",
        "decisions",
        "warnings",
        "sesiones",
        "trades",
        "count",
        "ready",
        "recheck",
        "bloqueados",
        "quote valid",
        "listos",
    }
    if any(token in label_text for token in count_tokens):
        return format_count(number)
    return format_number(number)


def format_timestamp(value: Any, timezone_name: str = "America/Santiago") -> str:
    if _is_missing(value):
        return "N/A"
    parsed: datetime | None = None
    number = _to_float(value)
    try:
        if number is not None:
            parsed = datetime.fromtimestamp(number, tz=timezone.utc)
        else:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(ZoneInfo(timezone_name))
    except (OSError, OverflowError, ValueError, TypeError):
        return safe_display_text(value)
    return parsed.strftime("%d-%m-%Y %H:%M")


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
        elif column in STATUS_VALUE_COLUMNS:
            out[column] = out[column].map(display_status_label)
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
