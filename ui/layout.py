from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ui import formatters, guards


def render_status_message(status: Any, text: str = "") -> None:
    status_text = formatters.format_status_badge(status)
    message = text or f"Status: {status_text}"
    level = formatters.status_to_streamlit_level(status_text)
    if level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    elif level == "success":
        st.success(message)
    else:
        st.info(message)


def render_empty_state(message: str = "No data available.") -> None:
    st.info(message)


def render_guardrail_notice() -> None:
    disabled_setup = "_".join(["BUY", "SETUP", "ACTIVE"])
    trigger_state = "_".join(["TRIGGER", "CONFIRMED"])
    st.markdown(
        "\n".join(
            [
                f"- `{disabled_setup}` disabled",
                "- No automatic trading",
                f"- `{trigger_state}` requires quote_status `VALID` and execution_quote_quality `HIGH`",
                "- `RECHECK_LIVE_QUOTE` is not entry",
            ]
        )
    )


def render_no_real_order_notice() -> None:
    st.warning("Manual review only. Paper trading only. No real orders.")
    st.caption(guards.NO_REAL_ORDER_NOTICE)


def render_source_status_table(sources: dict) -> pd.DataFrame:
    report_rows = []
    for source in (sources or {}).get("sources", {}).values():
        report_rows.append(
            {
                "path": source.get("path", ""),
                "status": source.get("status", "UNKNOWN"),
                "exists": source.get("exists", False),
                "size_bytes": source.get("size_bytes", 0),
                "modified": source.get("modified"),
                "error": source.get("error", ""),
            }
        )
    reports_df = pd.DataFrame(report_rows)
    if reports_df.empty:
        render_empty_state("No report sources available.")
        return reports_df
    st.dataframe(reports_df, use_container_width=True, hide_index=True)
    missing_invalid = reports_df[reports_df["status"].isin(["MISSING", "INVALID"])]
    if not missing_invalid.empty:
        st.warning("Missing or invalid sources detected.")
        st.dataframe(missing_invalid, use_container_width=True, hide_index=True)
    return reports_df
