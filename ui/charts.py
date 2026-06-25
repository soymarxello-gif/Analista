from __future__ import annotations

from typing import Any

import pandas as pd

NO_CHART_DATA = "No data available for this chart."


def _chart(status: str, dataframe: pd.DataFrame | None = None, message: str = "") -> dict:
    dataframe = dataframe if isinstance(dataframe, pd.DataFrame) else pd.DataFrame()
    status = "EMPTY" if dataframe.empty else str(status or "PASS").upper()
    return {
        "status": status,
        "message": message or (NO_CHART_DATA if dataframe.empty else ""),
        "dataframe": dataframe,
        "rows": dataframe.to_dict(orient="records") if not dataframe.empty else [],
    }


def _rows(model: dict | None) -> list[dict]:
    data = (model or {}).get("data", {})
    rows = data.get("rows", []) if isinstance(data, dict) else []
    return rows if isinstance(rows, list) else []


def _frame(model: dict | None) -> pd.DataFrame:
    rows = _rows(model)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).fillna("")


def _count_column(df: pd.DataFrame, column: str, *, metric: str | None = None) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=["metric", "value", "count"])
    counts = (
        df[column]
        .fillna("")
        .astype(str)
        .replace("", "MISSING")
        .value_counts()
        .rename_axis("value")
        .reset_index(name="count")
    )
    counts.insert(0, "metric", metric or column)
    return counts


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def build_signal_distribution_chart_data(model: dict | None) -> dict:
    return _chart("PASS", _count_column(_frame(model), "signal", metric="signal"))


def build_recommendation_distribution_chart_data(model: dict | None) -> dict:
    return _chart("PASS", _count_column(_frame(model), "recommendation", metric="recommendation"))


def build_quote_quality_chart_data(model: dict | None) -> dict:
    df = _frame(model)
    parts = [
        _count_column(df, "quote_status", metric="quote_status"),
        _count_column(df, "execution_quote_quality", metric="execution_quote_quality"),
    ]
    non_empty_parts = [part for part in parts if not part.empty]
    out = pd.concat(non_empty_parts, ignore_index=True) if non_empty_parts else pd.DataFrame()
    return _chart("PASS", out)


def build_candidate_score_chart_data(model: dict | None) -> dict:
    df = _frame(model)
    if df.empty or "final_trade_score" not in df.columns:
        return _chart("EMPTY")
    out = df.copy()
    out["final_trade_score"] = _numeric(out["final_trade_score"])
    out = out.dropna(subset=["final_trade_score"]).sort_values(
        ["final_trade_score", "ticker"] if "ticker" in out.columns else ["final_trade_score"],
        ascending=[False, True] if "ticker" in out.columns else [False],
    )
    columns = [column for column in ["ticker", "final_trade_score"] if column in out.columns]
    return _chart("PASS", out[columns].head(20))


def build_paper_status_chart_data(model: dict | None) -> dict:
    df = _frame(model)
    parts = [
        _count_column(df, "manual_decision", metric="manual_decision"),
        _count_column(df, "followup_status", metric="followup_status"),
    ]
    non_empty_parts = [part for part in parts if not part.empty]
    out = pd.concat(non_empty_parts, ignore_index=True) if non_empty_parts else pd.DataFrame()
    if not out.empty:
        return _chart("PASS", out)

    summary = (model or {}).get("summary", {})
    if not isinstance(summary, dict):
        return _chart("EMPTY")
    keys = [
        "pending_review",
        "paper_watch",
        "paper_enter",
        "blocked",
        "closed_paper",
        "pending_export",
        "exported_outcomes",
    ]
    rows = [
        {"metric": "paper_status", "value": key, "count": int(summary.get(key, 0) or 0)}
        for key in keys
        if int(summary.get(key, 0) or 0) > 0
    ]
    return _chart("PASS", pd.DataFrame(rows))


def build_followup_decision_chart_data(model: dict | None) -> dict:
    df = _frame(model)
    out = _count_column(df, "followup_decision", metric="followup_decision")
    if not out.empty:
        return _chart("PASS", out)
    decisions = ((model or {}).get("summary", {}) or {}).get("decisions", {})
    if not isinstance(decisions, dict):
        return _chart("EMPTY")
    rows = [
        {"metric": "followup_decision", "value": key, "count": int(value or 0)}
        for key, value in decisions.items()
        if int(value or 0) > 0
    ]
    return _chart("PASS", pd.DataFrame(rows))


def build_closed_outcomes_chart_data(model: dict | None) -> dict:
    summary = (model or {}).get("summary", {})
    if not isinstance(summary, dict):
        return _chart("EMPTY")
    keys = ["closed_paper_count", "pending_export_count", "exported_count", "duplicate_outcome_ids"]
    if not any(key in summary for key in keys):
        return _chart("EMPTY")
    rows = [
        {"metric": "paper_cycle", "value": key, "count": int(summary.get(key, 0) or 0)}
        for key in keys
    ]
    return _chart("PASS", pd.DataFrame(rows))


def build_r_multiple_chart_data(model: dict | None) -> dict:
    df = _frame(model)
    if df.empty:
        data = (model or {}).get("data", {})
        raw_rows: Any = data.get("rows", []) if isinstance(data, dict) else []
        df = pd.DataFrame(raw_rows) if isinstance(raw_rows, list) else pd.DataFrame()
    if df.empty or "r_multiple" not in df.columns:
        return _chart("EMPTY")
    out = df.copy()
    out["r_multiple"] = _numeric(out["r_multiple"])
    out = out.dropna(subset=["r_multiple"]).reset_index(drop=True)
    out["trade_number"] = out.index + 1
    return _chart("PASS", out[["trade_number", "r_multiple"]])


def build_calibration_bucket_chart_data(model: dict | None) -> dict:
    data = (model or {}).get("data", {})
    rows = data.get("rows", []) if isinstance(data, dict) else []
    df = pd.DataFrame(rows) if isinstance(rows, list) else pd.DataFrame()
    if df.empty:
        return _chart("EMPTY")
    bucket_columns = [column for column in df.columns if "bucket" in str(column).lower()]
    value_column = "avg_r_multiple" if "avg_r_multiple" in df.columns else "closed_trades" if "closed_trades" in df.columns else ""
    if not bucket_columns or not value_column:
        return _chart("EMPTY")
    out = df[[bucket_columns[0], value_column]].copy()
    out[value_column] = _numeric(out[value_column]).fillna(0)
    out = out.rename(columns={bucket_columns[0]: "bucket", value_column: "value"})
    return _chart("PASS", out)
