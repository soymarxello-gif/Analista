from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from .models import SignalEvent
from .store import InstitutionalStore


class ContextAdvisory:
    """Attach late context without changing technical selection or trade geometry."""

    VERSION = "context-advisory-1"
    EXPECTED_FRED_SERIES = 7

    def __init__(self, store: InstitutionalStore) -> None:
        self.store = store

    def annotate(self, signals: tuple[SignalEvent, ...], as_of: datetime) -> tuple[SignalEvent, ...]:
        rows = self.store.context_as_of(as_of)
        macro_rows = [row for row in rows if row["source"] == "FRED_ALFRED"]
        annotated = []
        for signal in signals:
            fundamental_rows = [
                row for row in rows
                if row["source"] == "SEC_COMPANYFACTS" and row["series"] == signal.symbol
            ]
            option_rows = [
                row for row in rows
                if row["source"] == "ALPACA_OPTIONS" and row["series"] == signal.symbol
            ]
            support = {
                "macro": self._domain(macro_rows, expected=self.EXPECTED_FRED_SERIES, missing="Sin datos macro"),
                "fundamentals": self._domain(fundamental_rows, expected=1, missing="Sin datos fundamentales"),
                "options": self._domain(option_rows, expected=1, missing="Sin datos de opciones"),
            }
            warnings = [value["message"] for value in support.values() if value["status"] != "AVAILABLE"]
            metadata = {
                **signal.metadata,
                "selection_basis": "TECHNICAL_SETUP_ONLY",
                "context_role": "ADVISORY_ONLY_NEVER_FILTERS_OR_PENALIZES",
                "context_support": support,
                "context_warnings": warnings,
                "context_advisory_version": self.VERSION,
            }
            annotated_signal = replace(signal, metadata=metadata)
            self.store.put_signal(annotated_signal)
            annotated.append(annotated_signal)
        return tuple(annotated)

    @staticmethod
    def _domain(rows: list[dict[str, object]], *, expected: int, missing: str) -> dict[str, object]:
        if not rows:
            return {"status": "NO_DATA", "message": missing, "observations": 0}
        statuses = {str(row["status"]).upper() for row in rows}
        if "ERROR" in statuses:
            return {"status": "ERROR", "message": f"{missing}: error de fuente", "observations": len(rows)}
        if len(rows) < expected or statuses != {"COMPLETE"}:
            return {
                "status": "PARTIAL",
                "message": f"Datos parciales ({len(rows)}/{expected})",
                "observations": len(rows),
            }
        return {"status": "AVAILABLE", "message": "Datos disponibles", "observations": len(rows)}
