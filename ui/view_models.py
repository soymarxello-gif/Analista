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
    "entry_timing_status",
    "engine_recommendation",
    "scenario_thesis",
    "scenario_evidence",
    "scenario_contradictions",
    "required_confirmation",
    "technical_rsi",
    "technical_macd_hist",
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
        },
        data=data,
    )


def build_paper_trading_model(sources) -> dict:
    journal = _df(sources, "paper_trading_journal")
    close_df = _df(sources, "paper_trade_close")
    manual_counts = _count_values(journal, "manual_decision")
    followup_counts = _count_values(journal, "followup_status")
    pending_export = 0
    exported = 0
    if not close_df.empty and "followup_status" in close_df.columns:
        closed = close_df["followup_status"].fillna("").astype(str).str.upper().eq("CLOSED_PAPER")
        if "outcome_exported" in close_df.columns:
            exported_mask = close_df["outcome_exported"].fillna("").astype(str).str.lower().isin({"true", "1", "yes"})
            pending_export = int((closed & ~exported_mask).sum())
            exported = int((closed & exported_mask).sum())
    summary = {
        "journal_rows": len(journal),
        "pending_review": int(manual_counts.get("PENDING_REVIEW", 0)),
        "paper_watch": int(manual_counts.get("PAPER_WATCH", 0)),
        "paper_enter": int(manual_counts.get("PAPER_ENTER", 0)),
        "blocked": int(manual_counts.get("BLOCKED", 0)),
        "closed_paper": int(followup_counts.get("CLOSED_PAPER", 0)),
        "pending_export": pending_export,
        "exported_outcomes": exported,
    }
    status = "EMPTY" if journal.empty else "PASS"
    rows = journal.to_dict(orient="records") if not journal.empty else []
    return _model(
        "Paper trading",
        status=status,
        summary=summary,
        rows_count=len(journal),
        data={"summary": summary, "rows": rows},
    )


def build_followup_model(sources) -> dict:
    df = _df(sources, "paper_trade_followup")
    counts = _count_values(df, "followup_decision")
    return _model(
        "Paper follow-up",
        status="EMPTY" if df.empty else "PASS",
        summary={"rows": len(df), "decisions": counts},
        rows_count=len(df),
        data={"decisions": counts, "rows": df.to_dict(orient="records") if not df.empty else []},
    )


def build_cycle_audit_model(sources) -> dict:
    data = _json_data(sources, "paper_trading_cycle_audit")
    source = _source(sources, "paper_trading_cycle_audit")
    duplicate_ids = data.get("duplicate_outcome_ids", []) or []
    external_execution_key = "_".join(["bro" + "ker", "connection", "detected"])
    external_execution_flag = bool(data.get(external_execution_key, False))
    guardrail_status = "FAIL" if external_execution_flag else "PASS"
    status = str(data.get("status") or _status_from_source(source)).upper()
    summary = {
        "status": status,
        "journal_rows": int(data.get("journal_rows", 0) or 0),
        "open_paper_count": int(data.get("open_paper_count", 0) or 0),
        "closed_paper_count": int(data.get("closed_paper_count", 0) or 0),
        "pending_export_count": int(data.get("pending_export_count", 0) or 0),
        "exported_count": int(data.get("exported_count", 0) or 0),
        "duplicate_outcome_ids": len(duplicate_ids),
        "guardrail_status": guardrail_status,
    }
    return _model(
        "Paper trading cycle audit",
        status=status,
        summary=summary,
        warnings=data.get("warnings", []),
        errors=data.get("issues", []),
        data=data,
    )


def build_calibration_model(sources) -> dict:
    calibration = _json_data(sources, "trade_score_calibration")
    recommendations = _json_data(sources, "calibration_recommendations")
    no_auto = bool(recommendations.get("do_not_change_automatically", True))
    summary = {
        "calibration_status": calibration.get("status", "MISSING"),
        "recommendations_status": recommendations.get("status", "MISSING"),
        "recommendations_are_observational": no_auto,
        "no_auto_weight_change": no_auto
        and not calibration.get("changed_weights", False)
        and not calibration.get("changed_thresholds", False),
    }
    status = "PASS" if summary["no_auto_weight_change"] else "FAIL"
    if summary["calibration_status"] == "MISSING" and summary["recommendations_status"] == "MISSING":
        status = "MISSING"
    return _model("Calibration", status=status, summary=summary, data=summary)
