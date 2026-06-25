from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

PROVIDER_STATUSES = {"PASS", "WARN", "FAIL", "DISABLED"}
DATA_FRESHNESS_VALUES = {"REALTIME", "DELAYED_15_MIN", "DELAYED_20_MIN", "EOD", "UNKNOWN"}
PROVIDER_CONFIDENCE_VALUES = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().upper()
    return text if text in allowed else default


@dataclass
class ProviderResponse:
    provider_name: str
    status: str = "WARN"
    source: str = ""
    timestamp: str = field(default_factory=utc_now_iso)
    data_freshness: str = "UNKNOWN"
    confidence: str = "UNKNOWN"
    fields: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.status = _normalize_choice(self.status, PROVIDER_STATUSES, "WARN")
        self.data_freshness = _normalize_choice(
            self.data_freshness,
            DATA_FRESHNESS_VALUES,
            "UNKNOWN",
        )
        self.confidence = _normalize_choice(
            self.confidence,
            PROVIDER_CONFIDENCE_VALUES,
            "UNKNOWN",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_name": str(self.provider_name or "").strip(),
            "status": self.status,
            "source": str(self.source or "").strip(),
            "timestamp": str(self.timestamp or utc_now_iso()),
            "data_freshness": self.data_freshness,
            "confidence": self.confidence,
            "fields": dict(self.fields or {}),
            "errors": list(self.errors or []),
            "notes": list(self.notes or []),
        }


def disabled_provider_response(provider_name: str, *, source: str = "", note: str = "") -> ProviderResponse:
    notes = [note] if note else ["provider disabled in config"]
    return ProviderResponse(
        provider_name=provider_name,
        status="DISABLED",
        source=source,
        confidence="UNKNOWN",
        notes=notes,
    )


def normalize_provider_response(data: dict[str, Any]) -> dict[str, Any]:
    return ProviderResponse(
        provider_name=str(data.get("provider_name", "")),
        status=str(data.get("status", "WARN")),
        source=str(data.get("source", "")),
        timestamp=str(data.get("timestamp") or utc_now_iso()),
        data_freshness=str(data.get("data_freshness", "UNKNOWN")),
        confidence=str(data.get("confidence", "UNKNOWN")),
        fields=data.get("fields") if isinstance(data.get("fields"), dict) else {},
        errors=data.get("errors") if isinstance(data.get("errors"), list) else [],
        notes=data.get("notes") if isinstance(data.get("notes"), list) else [],
    ).to_dict()
