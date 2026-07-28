from __future__ import annotations

from typing import Any

import altair as alt
import math
import pandas as pd

from ui import formatters

NO_CHART_DATA = "No data available for this chart."

SEMANTIC_COLORS = {
    "negative": "#F87171",
    "warning": "#FBBF24",
    "positive": "#34D399",
    "neutral": "#38BDF8",
}


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


def _chart_label_frame(chart: dict | None, value_column: str) -> pd.DataFrame:
    dataframe = (chart or {}).get("dataframe")
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return pd.DataFrame()
    out = dataframe.copy()
    if {"metric", "value"}.issubset(out.columns):
        metric_count = out["metric"].astype(str).nunique()
        out["label"] = out["value"].map(formatters.display_status_with_code)
        if metric_count > 1:
            out["label"] = (
                out["metric"].map(formatters.spanish_column_label)
                + " · "
                + out["label"].astype(str)
            )
    elif "ticker" in out.columns:
        out["label"] = out["ticker"].astype(str)
    elif "bucket" in out.columns:
        out["label"] = out["bucket"].astype(str)
    else:
        return pd.DataFrame()
    if value_column not in out.columns:
        return pd.DataFrame()
    out[value_column] = pd.to_numeric(out[value_column], errors="coerce")
    out = out[out[value_column].map(lambda value: value is not None and math.isfinite(value))]
    if out.empty or not out[value_column].abs().gt(0).any():
        return pd.DataFrame()
    out["semantic_class"] = out.get("value", out["label"]).map(formatters.trading_value_class)
    out["color"] = out["semantic_class"].map(SEMANTIC_COLORS).fillna(SEMANTIC_COLORS["neutral"])
    return out.sort_values([value_column, "label"], ascending=[False, True]).reset_index(drop=True)


def build_horizontal_bar_chart(
    chart: dict | None,
    *,
    value_column: str = "count",
    selected_label: str = "",
) -> alt.LayerChart | None:
    out = _chart_label_frame(chart, value_column)
    if out.empty:
        return None
    if selected_label:
        out["color"] = out.apply(
            lambda row: "#F8FAFC" if str(row["label"]) == str(selected_label) else row["color"],
            axis=1,
        )
    height = min(520, max(150, 34 * len(out)))
    y = alt.Y(
        "label:N",
        sort=alt.SortField(field=value_column, order="descending"),
        title=None,
        axis=alt.Axis(labelLimit=280, labelColor="#CBD5E1", ticks=False, domain=False),
    )
    x = alt.X(
        f"{value_column}:Q",
        title=None,
        axis=alt.Axis(gridColor="#1E293B", labelColor="#94A3B8", tickCount=5),
    )
    tooltip = [
        alt.Tooltip("label:N", title="Categoría"),
        alt.Tooltip(f"{value_column}:Q", title="Valor", format=".2f"),
    ]
    base = alt.Chart(out).encode(y=y, x=x, tooltip=tooltip)
    bars = base.mark_bar(cornerRadiusEnd=4, size=20).encode(
        color=alt.Color("color:N", scale=None, legend=None)
    )
    labels = base.mark_text(
        align="left",
        baseline="middle",
        dx=6,
        color="#E5E7EB",
        fontSize=12,
    ).encode(text=alt.Text(f"{value_column}:Q", format=".2f"))
    return (bars + labels).properties(height=height).configure_view(stroke=None)


def build_r_multiple_line_chart(chart: dict | None) -> alt.Chart | None:
    dataframe = (chart or {}).get("dataframe")
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return None
    out = dataframe.copy()
    out["trade_number"] = pd.to_numeric(out.get("trade_number"), errors="coerce")
    out["r_multiple"] = pd.to_numeric(out.get("r_multiple"), errors="coerce")
    out = out.dropna(subset=["trade_number", "r_multiple"])
    if out.empty:
        return None
    return (
        alt.Chart(out)
        .mark_line(point=True, color="#38BDF8")
        .encode(
            x=alt.X("trade_number:Q", title="Trade"),
            y=alt.Y("r_multiple:Q", title="R multiple"),
            tooltip=[
                alt.Tooltip("trade_number:Q", title="Trade", format=".0f"),
                alt.Tooltip("r_multiple:Q", title="R", format=".2f"),
            ],
        )
        .properties(height=260)
        .configure_view(stroke=None)
    )


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
