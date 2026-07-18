from __future__ import annotations

from typing import Any

TRUSTED = "TRUSTED"
DEGRADED = "DEGRADED"
UNUSABLE = "UNUSABLE"

DEFAULT_ESSENTIAL_SOURCES = ("screeners", "price_history_yahoo")


def assess_run_trust(health: dict[str, Any], config: dict) -> dict[str, Any]:
    policy = config.get("telemetry", {}).get("run_trust", {})
    essential_sources = tuple(policy.get("essential_sources", DEFAULT_ESSENTIAL_SOURCES))
    sources = health.get("sources", {})
    reasons: list[str] = []
    critical_essential: list[str] = []
    degraded_sources: list[str] = []

    for source in essential_sources:
        status = str(sources.get(source, {}).get("health_status") or "NO_DATA")
        if status in {"CRITICAL", "NO_DATA"}:
            critical_essential.append(source)
            reasons.append(f"essential_source_{source}_{status.lower()}")
        elif status == "DEGRADED":
            degraded_sources.append(source)
            reasons.append(f"essential_source_{source}_degraded")

    for source, item in sorted(sources.items()):
        if source in essential_sources:
            continue
        status = str(item.get("health_status") or "NO_DATA")
        if status == "CRITICAL":
            degraded_sources.append(source)
            reasons.append(f"supporting_source_{source}_critical")
        elif status == "DEGRADED":
            degraded_sources.append(source)
            reasons.append(f"supporting_source_{source}_degraded")

    if critical_essential:
        status = UNUSABLE
    elif degraded_sources:
        status = DEGRADED
    else:
        status = TRUSTED

    return {
        "run_trust_status": status,
        "run_trust_reasons": reasons,
        "essential_sources": list(essential_sources),
        "critical_essential_sources": critical_essential,
        "degraded_sources": sorted(set(degraded_sources)),
        "manual_review_required": status != TRUSTED,
    }


def attach_run_trust(df, trust: dict[str, Any]):
    result = df.copy()
    result["run_trust_status"] = trust["run_trust_status"]
    result["run_trust_reasons"] = "; ".join(trust.get("run_trust_reasons") or [])
    result["critical_essential_sources"] = "; ".join(
        trust.get("critical_essential_sources") or []
    )
    result["run_manual_review_required"] = bool(trust.get("manual_review_required"))
    return result
