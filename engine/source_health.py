from __future__ import annotations

from typing import Any

DEFAULT_THRESHOLDS = {
    "degraded_failure_rate_pct": 10.0,
    "critical_failure_rate_pct": 35.0,
    "degraded_coverage_pct": 85.0,
    "critical_coverage_pct": 50.0,
    "degraded_latency_ms_avg": 3000.0,
    "critical_latency_ms_avg": 10000.0,
    "degraded_retry_rate_pct": 15.0,
    "critical_retry_rate_pct": 50.0,
}

STATUS_RANK = {"NO_DATA": 0, "HEALTHY": 1, "DEGRADED": 2, "CRITICAL": 3}


def _thresholds(config: dict) -> dict[str, float]:
    configured = config.get("telemetry", {}).get("health", {})
    return {
        key: float(configured.get(key, default))
        for key, default in DEFAULT_THRESHOLDS.items()
    }


def assess_source_health(summary: dict[str, Any], config: dict) -> dict[str, Any]:
    calls = int(summary.get("calls") or 0)
    requested = int(summary.get("requested_items") or 0)
    failures = int(summary.get("failures") or 0)
    retries = int(summary.get("retries") or 0)
    circuit_opens = int(summary.get("circuit_opens") or 0)
    blocked_calls = int(summary.get("blocked_calls") or 0)
    latency = float(summary.get("latency_ms_avg") or 0.0)
    coverage = summary.get("coverage_pct")

    if calls == 0 and requested == 0 and blocked_calls == 0:
        return {"health_status": "NO_DATA", "health_score": None, "health_reasons": []}

    thresholds = _thresholds(config)
    failure_rate = 100.0 * failures / calls if calls else 0.0
    retry_rate = 100.0 * retries / calls if calls else 0.0
    reasons: list[str] = []
    severity = "HEALTHY"
    penalties = 0.0

    def flag(condition: bool, status: str, reason: str, penalty: float) -> None:
        nonlocal severity, penalties
        if condition:
            reasons.append(reason)
            penalties += penalty
            if STATUS_RANK[status] > STATUS_RANK[severity]:
                severity = status

    flag(circuit_opens > 0, "CRITICAL", "circuit_opened", 45.0)
    flag(blocked_calls > 0, "CRITICAL", "calls_blocked", 25.0)
    flag(
        failure_rate >= thresholds["critical_failure_rate_pct"],
        "CRITICAL",
        "high_failure_rate",
        40.0,
    )
    flag(
        thresholds["degraded_failure_rate_pct"] <= failure_rate < thresholds["critical_failure_rate_pct"],
        "DEGRADED",
        "elevated_failure_rate",
        20.0,
    )
    if coverage is not None:
        coverage_value = float(coverage)
        flag(
            coverage_value < thresholds["critical_coverage_pct"],
            "CRITICAL",
            "very_low_coverage",
            40.0,
        )
        flag(
            thresholds["critical_coverage_pct"] <= coverage_value < thresholds["degraded_coverage_pct"],
            "DEGRADED",
            "low_coverage",
            20.0,
        )
    flag(
        latency >= thresholds["critical_latency_ms_avg"],
        "CRITICAL",
        "very_high_latency",
        30.0,
    )
    flag(
        thresholds["degraded_latency_ms_avg"] <= latency < thresholds["critical_latency_ms_avg"],
        "DEGRADED",
        "high_latency",
        15.0,
    )
    flag(
        retry_rate >= thresholds["critical_retry_rate_pct"],
        "CRITICAL",
        "very_high_retry_rate",
        25.0,
    )
    flag(
        thresholds["degraded_retry_rate_pct"] <= retry_rate < thresholds["critical_retry_rate_pct"],
        "DEGRADED",
        "high_retry_rate",
        12.0,
    )

    return {
        "health_status": severity,
        "health_score": round(max(0.0, 100.0 - penalties), 1),
        "health_reasons": reasons,
        "failure_rate_pct": round(failure_rate, 2),
        "retry_rate_pct": round(retry_rate, 2),
    }


def build_health_summary(source_summaries: dict[str, dict[str, Any]], config: dict) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    global_status = "NO_DATA"
    for name, summary in sorted(source_summaries.items()):
        health = assess_source_health(summary, config)
        sources[name] = health
        status = health["health_status"]
        if STATUS_RANK[status] > STATUS_RANK[global_status]:
            global_status = status
    return {
        "overall_status": global_status,
        "degraded_sources": [
            name for name, item in sources.items() if item["health_status"] in {"DEGRADED", "CRITICAL"}
        ],
        "sources": sources,
    }


def format_health_log(health: dict[str, Any]) -> list[str]:
    lines = [f"Salud de datos: {health.get('overall_status', 'NO_DATA')}"]
    for name, item in health.get("sources", {}).items():
        reasons = ",".join(item.get("health_reasons") or []) or "none"
        score = item.get("health_score")
        score_text = "n/a" if score is None else f"{score:.1f}"
        lines.append(
            f"Fuente {name}: {item.get('health_status')} | score={score_text} | reasons={reasons}"
        )
    return lines
