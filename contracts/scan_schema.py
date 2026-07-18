from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

SCHEMA_VERSION = "2.0"
ALLOWED_SIGNALS = {
    "VETO",
    "AVOID",
    "WATCHLIST",
    "READY_WAIT_TRIGGER",
    "TRIGGER_CONFIRMED",
}
ALLOWED_QUOTE_STATUS = {
    "VALID",
    "INVALID",
    "STALE_POSSIBLE",
    "MISSING",
    "WIDE_OR_INCOHERENT",
}
ALLOWED_QUOTE_QUALITY = {"HIGH", "MEDIUM", "LOW"}

REQUIRED_COLUMNS = {
    "ticker",
    "signal",
    "final_score",
    "final_trade_score",
    "quote_status",
    "execution_quote_quality",
    "all_veto_reasons",
    "penalty_reasons",
    "actionable_entry",
    "actionable_stop",
    "actionable_target",
    "theoretical_entry",
    "theoretical_stop",
    "theoretical_target",
    "legacy_rank",
    "trade_rank",
    "rank_delta",
}


@dataclass(frozen=True)
class SchemaViolation:
    code: str
    detail: str


def _missing_columns(columns: Iterable[str]) -> set[str]:
    return REQUIRED_COLUMNS.difference(set(columns))


def validate_scan_schema(df: pd.DataFrame) -> list[SchemaViolation]:
    violations: list[SchemaViolation] = []
    missing = _missing_columns(df.columns)
    if missing:
        violations.append(SchemaViolation("missing_columns", ", ".join(sorted(missing))))
        return violations

    invalid_signals = sorted(set(df["signal"].dropna()) - ALLOWED_SIGNALS)
    if invalid_signals:
        violations.append(SchemaViolation("invalid_signal", ", ".join(map(str, invalid_signals))))

    invalid_quote_status = sorted(set(df["quote_status"].dropna()) - ALLOWED_QUOTE_STATUS)
    if invalid_quote_status:
        violations.append(SchemaViolation("invalid_quote_status", ", ".join(map(str, invalid_quote_status))))

    invalid_quote_quality = sorted(set(df["execution_quote_quality"].dropna()) - ALLOWED_QUOTE_QUALITY)
    if invalid_quote_quality:
        violations.append(SchemaViolation("invalid_quote_quality", ", ".join(map(str, invalid_quote_quality))))

    veto = df["signal"].eq("VETO")
    for column in ("actionable_entry", "actionable_stop", "actionable_target"):
        if df.loc[veto, column].notna().any():
            violations.append(SchemaViolation("veto_actionable_level", column))

    confirmed = df["signal"].eq("TRIGGER_CONFIRMED")
    if (confirmed & ~df["trigger_confirmed"].fillna(False).astype(bool)).any():
        violations.append(SchemaViolation("trigger_without_confirmation", "trigger_confirmed"))
    if (confirmed & df["execution_quote_quality"].eq("LOW")).any():
        violations.append(SchemaViolation("trigger_with_low_quote", "execution_quote_quality"))
    if (confirmed & pd.to_numeric(df["rr"], errors="coerce").lt(2.0)).any():
        violations.append(SchemaViolation("trigger_rr_below_minimum", "rr"))

    ready = df["signal"].eq("READY_WAIT_TRIGGER")
    if (ready & df["trigger_confirmed"].fillna(False).astype(bool)).any():
        violations.append(SchemaViolation("ready_with_confirmed_trigger", "trigger_confirmed"))

    return violations


def assert_scan_schema(df: pd.DataFrame) -> None:
    violations = validate_scan_schema(df)
    if violations:
        detail = "; ".join(f"{item.code}: {item.detail}" for item in violations)
        raise ValueError(f"Scan schema validation failed: {detail}")
