from __future__ import annotations

import pandas as pd

VIEW_STATUSES = {"PASS", "WARN", "FAIL", "MISSING", "EMPTY", "UNKNOWN"}

CANDIDATE_COLUMNS = [
    "ticker",
    "company",
    "sector",
    "industry",
    "signal",
    "recommendation",
    "checklist_status",
    "setup_type",
    "final_trade_score",
    "asset_attractiveness_score",
    "operational_readiness_score",
    "operational_readiness_bucket",
    "timing_quality_score",
    "momentum_confirmation_score",
    "execution_readiness_status",
    "technical_prefilter_status",
    "technical_prefilter_reason",
    "daily_macd_prefilter_status",
    "weekly_macd_prefilter_status",
    "ema20_extension_prefilter_status",
    "ema20_extension_reference_source",
    "checklist_score",
    "quote_status",
    "execution_quote_quality",
    "actionable_entry",
    "actionable_stop",
    "actionable_target",
    "rr",
    "scenario_status",
    "scenario_confidence",
    "momentum_state",
    "extension_state",
    "ema20_extension_status",
    "entry_timing_status",
    "macd_histogram_state",
    "weekly_macd_histogram_state",
    "weekly_macd_hist_improving",
    "weekly_macd_hist",
    "weekly_macd_hist_change_1w",
    "weekly_macd_hist_change_2w",
    "sector_benchmark_symbol",
    "sector_weekly_macd_state",
    "sector_weekly_macd_acceleration_state",
    "sector_weekly_macd_slope_1w",
    "sector_weekly_macd_acceleration",
    "sector_context_status",
    "sector_context_reason",
    "timing_penalty_reason",
    "momentum_penalty_reason",
    "engine_block_reason",
    "engine_recommendation",
    "scenario_thesis",
    "scenario_evidence",
    "scenario_contradictions",
    "required_confirmation",
    "technical_rsi",
    "technical_macd_hist",
    "technical_macd_hist_change_3d",
    "technical_ema20",
    "technical_distance_ema20_atr",
    "technical_distance_ema20_pct",
    "technical_distance_sma20_atr",
    "technical_trigger_distance_atr",
    "technical_relative_volume",
    "scenario_entry",
    "scenario_stop",
    "scenario_target",
    "stop_atr_status",
    "options_bias",
    "options_confidence",
    "options_notes",
    "earnings_date",
    "days_to_earnings",
    "revenue_growth",
    "earnings_growth",
    "operating_margins",
    "profit_margins",
    "debt_to_equity",
    "return_on_equity",
    "macro_risk_flag",
    "macro_notes",
    "macro_regime_mode",
    "macro_event_risk",
    "metadata_source",
    "quote_source",
    "options_source",
    "warnings",
    "penalty_reasons",
    "reason_summary",
]


def _model(title: str, status: str = "UNKNOWN", summary: dict | None = None, rows_count: int = 0, warnings=None, errors=None, data=None) -> dict:
    status = str(status or "UNKNOWN").upper()
    if status not in VIEW_STATUSES:
        status = "UNKNOWN"
    return {
        "status": status,
        "title": title,
        "summary": summary or {},
        "rows_count": int(rows_count or 0),
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "data": data if data is not None else {},
    }


def _sources(sources: dict) -> dict:
    return (sources or {}).get("sources", sources or {})


def _source(sources: dict, name: str) -> dict:
    return _sources(sources).get(name, {}) or {}


def _df(sources: dict, name: str) -> pd.DataFrame:
    df = _source(sources, name).get("dataframe")
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _json_data(sources: dict, name: str) -> dict:
    data = _source(sources, name).get("data", {})
    return data if isinstance(data, dict) else {}


def _status_from_source(source: dict) -> str:
    status = str(source.get("status", "MISSING")).upper()
    if status == "AVAILABLE":
        return "PASS"
    if status in {"MISSING", "EMPTY", "INVALID"}:
        return status
    return status if status in VIEW_STATUSES else "UNKNOWN"


def _count_values(df: pd.DataFrame, column: str) -> dict:
    if df.empty or column not in df.columns:
        return {}
    return df[column].fillna("").astype(str).replace("", "MISSING").value_counts().to_dict()


def build_status_overview(sources) -> dict:
    summary = (sources or {}).get("summary", {})
    source_map = _sources(sources)
    invalid = [name for name, source in source_map.items() if source.get("status") == "INVALID"]
    missing = [
        name
        for name, source in source_map.items()
        if source.get("status") == "MISSING" and not source.get("optional", False)
    ]
    status = "FAIL" if invalid else "WARN" if missing else "PASS"
    return _model(
        "Status overview",
        status=status,
        summary={
            "available_sources": summary.get("available_sources", 0),
            "missing_sources": summary.get("missing_sources", len(missing)),
            "optional_missing_sources": summary.get("optional_missing_sources", 0),
            "invalid_sources": summary.get("invalid_sources", len(invalid)),
            "empty_sources": summary.get("empty_sources", 0),
        },
        warnings=[f"missing:{name}" for name in missing],
        errors=[f"invalid:{name}" for name in invalid],
        data={"sources": {name: source.get("status", "UNKNOWN") for name, source in source_map.items()}},
    )


def build_candidate_table_model(sources) -> dict:
    df = _df(sources, "manual_review_top")
    source_name = "manual_review_top"
    if df.empty:
        df = _df(sources, "manual_review_latest")
        source_name = "manual_review_latest"
    if df.empty:
        return _model(
            "Candidate table",
            status="EMPTY",
            summary={"source": source_name, "columns": []},
            warnings=["candidate_source_empty_or_missing"],
            data={"columns": CANDIDATE_COLUMNS, "rows": []},
        )

    scan_df = _df(sources, "latest_scan_audited")
    if not scan_df.empty and "ticker" in df.columns and "ticker" in scan_df.columns:
        enrichment_columns = [
            col for col in CANDIDATE_COLUMNS if col in scan_df.columns and col not in df.columns
        ]
        if enrichment_columns:
            scan_subset = scan_df[["ticker", *enrichment_columns]].drop_duplicates("ticker")
            df = df.merge(scan_subset, on="ticker", how="left")
    columns = [col for col in CANDIDATE_COLUMNS if col in df.columns]
    table = df[columns].copy() if columns else pd.DataFrame()
    return _model(
        "Candidate table",
        status="PASS",
        summary={"source": source_name, "columns": columns},
        rows_count=len(table),
        data={"columns": columns, "rows": table.to_dict(orient="records")},
    )


def build_quality_gate_model(sources) -> dict:
    data = _json_data(sources, "daily_quality_gate")
    source = _source(sources, "daily_quality_gate")
    status = str(data.get("status") or _status_from_source(source)).upper()
    return _model(
        "Quality gate",
        status=status,
        summary={
            "manual_review_allowed": data.get("manual_review_allowed", ""),
            "manual_review_mode": data.get("manual_review_mode", ""),
            "issues": data.get("issues", 0),
            "scan_freshness_status": data.get("scan_freshness_status", "UNKNOWN"),
            "scan_age_hours": data.get("scan_age_hours"),
            "manual_review_age_hours": data.get("manual_review_age_hours"),
            "macro_age_hours": data.get("macro_age_hours"),
            "scan_is_current_local_date": data.get("scan_is_current_local_date", False),
        },
        data=data,
    )


def _macro_series_rows(data: dict) -> list[dict]:
    series = data.get("fred_series", {}) if isinstance(data, dict) else {}
    rows = []
    if not isinstance(series, dict):
        return rows
    labels = {
        "M2SL": "M2",
        "RRPONTSYD": "Reverse repo",
        "DFF": "Fed funds",
        "DGS10": "US10Y",
        "DGS30": "US30Y",
        "T10Y2Y": "Curva 10Y-2Y",
        "T10Y3M": "Curva 10Y-3M",
        "VIXCLS": "VIX",
        "BAMLH0A0HYM2": "High yield spread",
        "DTWEXBGS": "Dólar amplio",
        "DCOILWTICO": "WTI",
        "CPIAUCSL": "CPI",
        "PAYEMS": "Payrolls",
        "UNRATE": "Desempleo",
        "M2V": "Velocidad M2",
    }
    for code, payload in series.items():
        if not isinstance(payload, dict):
            continue
        rows.append(
            {
                "series": labels.get(str(code), str(code)),
                "code": str(code),
                "status": payload.get("status", "UNKNOWN"),
                "latest": payload.get("latest_value", payload.get("latest")),
                "latest_date": payload.get("latest_date"),
                "age_days": payload.get("age_days"),
                "change": payload.get("change_value", payload.get("change_4w", payload.get("change"))),
                "provider": payload.get("provider", ""),
                "cache_status": payload.get("cache_status", ""),
                "fallback_used": payload.get("fallback_used", False),
            }
        )
    return rows


def _macro_event_rows(data: dict) -> list[dict]:
    calendar_payload = data.get("economic_calendar", []) if isinstance(data, dict) else []
    calendar = (
        calendar_payload.get("upcoming_events", [])
        if isinstance(calendar_payload, dict)
        else calendar_payload
    )
    rows = []
    if not isinstance(calendar, list):
        return rows
    for item in calendar:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "event_date": item.get("event_date", item.get("date", "")),
                "event_time": item.get("event_time", item.get("time", "")),
                "timezone": item.get("timezone", ""),
                "event": item.get("event_type", item.get("event", "")),
                "description": item.get("event_name", item.get("description", "")),
                "importance": item.get("importance", ""),
                "source": item.get("source_url", item.get("source", "")),
            }
        )
    return rows


def build_macro_context_model(sources) -> dict:
    data = _json_data(sources, "macro_event_context")
    source = _source(sources, "macro_event_context")
    nasdaq_data = _json_data(sources, "nasdaq_risk_regime")
    nasdaq_source = _source(sources, "nasdaq_risk_regime")
    status = str(data.get("status") or _status_from_source(source)).upper()
    issues = data.get("issues", []) or []
    if status == "PASS" and issues:
        status = "WARN"
    nasdaq_status = str(nasdaq_data.get("status") or _status_from_source(nasdaq_source)).upper()
    if status == "PASS" and nasdaq_status == "WARN":
        status = "WARN"
    summary = {
        "status": status,
        "source": data.get("source", source.get("path", "")),
        "data_freshness": data.get("data_freshness", "UNKNOWN"),
        "generated_at": data.get("generated_at", ""),
        "next_critical_event": data.get("next_critical_event", "UNKNOWN"),
        "next_critical_event_date": data.get("next_critical_event_date", ""),
        "days_to_critical_event": data.get("days_to_critical_event", ""),
        "event_risk_status": data.get("event_risk_status", "UNKNOWN"),
        "liquidity_context": data.get("liquidity_context", "UNKNOWN"),
        "macro_regime_mode": data.get("macro_regime_mode", "UNKNOWN"),
        "macro_regime_confidence": data.get("macro_regime_confidence", "UNKNOWN"),
        "macro_event_risk": data.get("macro_event_risk", "UNKNOWN"),
        "macro_liquidity_bias": data.get("macro_liquidity_bias", "UNKNOWN"),
        "macro_regime_notes": data.get("macro_regime_notes", ""),
        "m2_change_4w_pct": data.get("m2_change_4w_pct", ""),
        "reverse_repo_change_4w_pct": data.get("reverse_repo_change_4w_pct", ""),
        "effective_fed_funds_rate": data.get("effective_fed_funds_rate", ""),
        "us10y_official": data.get("us10y_official", ""),
        "us30y_official": data.get("us30y_official", ""),
        "vix_official": data.get("vix_official", ""),
        "yield_curve_10y2y": data.get("yield_curve_10y2y", ""),
        "high_yield_spread": data.get("high_yield_spread", ""),
        "notice": data.get("notice", "read-only macro context"),
        "nasdaq_status": nasdaq_status,
        "nasdaq_macro_regime_mode": nasdaq_data.get("macro_regime_mode", "UNKNOWN"),
        "nasdaq_macro_regime_confidence": nasdaq_data.get("macro_regime_confidence", "UNKNOWN"),
        "nasdaq_macro_risk_flag": nasdaq_data.get("macro_risk_flag", "UNKNOWN"),
        "nasdaq_risk_score": nasdaq_data.get("nasdaq_risk_score", ""),
        "nasdaq_risk_semaforo": nasdaq_data.get("nasdaq_risk_semaforo", "UNKNOWN"),
        "nasdaq_dominant_regime": nasdaq_data.get("dominant_regime", "UNKNOWN"),
        "nasdaq_regime_notes": nasdaq_data.get("macro_regime_notes", ""),
    }
    return _model(
        "Macro context",
        status=status,
        summary=summary,
        rows_count=len(_macro_series_rows(data)),
        warnings=issues,
        data={
            **data,
            "summary": summary,
            "series_rows": _macro_series_rows(data),
            "event_rows": _macro_event_rows(data),
            "nasdaq_risk_regime": nasdaq_data,
        },
    )


def build_calibration_model(sources) -> dict:
    calibration = _json_data(sources, "trade_score_calibration")
    recommendations = _json_data(sources, "calibration_recommendations")
    simple_posttest = _json_data(sources, "simple_candidate_posttest")
    no_auto = bool(recommendations.get("do_not_change_automatically", True))
    horizons = simple_posttest.get("horizon_summary", {}) or {}
    summary = {
        "calibration_status": calibration.get("status", "MISSING"),
        "recommendations_status": recommendations.get("status", "MISSING"),
        "simple_posttest_status": simple_posttest.get("status", "MISSING"),
        "simple_posttest_rows": int(simple_posttest.get("rows", 0) or 0),
        "simple_posttest_win_rate_5": (horizons.get("5", {}) or {}).get("win_rate", ""),
        "simple_posttest_win_rate_10": (horizons.get("10", {}) or {}).get("win_rate", ""),
        "simple_posttest_win_rate_15": (horizons.get("15", {}) or {}).get("win_rate", ""),
        "simple_posttest_avg_return_5": (horizons.get("5", {}) or {}).get("avg_return_pct", ""),
        "simple_posttest_avg_return_10": (horizons.get("10", {}) or {}).get("avg_return_pct", ""),
        "simple_posttest_avg_return_15": (horizons.get("15", {}) or {}).get("avg_return_pct", ""),
        "recommendations_are_observational": no_auto,
        "no_auto_weight_change": no_auto
        and not calibration.get("changed_weights", False)
        and not calibration.get("changed_thresholds", False),
    }
    status = "PASS" if summary["no_auto_weight_change"] else "FAIL"
    if summary["calibration_status"] == "MISSING" and summary["recommendations_status"] == "MISSING":
        status = "MISSING"
    return _model("Calibration", status=status, summary=summary, data=summary)
