from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CALENDAR = ROOT / "data" / "economic_calendar.csv"
DEFAULT_JSON_OUT = ROOT / "reports" / "macro_event_context_latest.json"
DEFAULT_MARKDOWN_OUT = ROOT / "reports" / "macro_event_context_latest.md"
FRED_CSV_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv"
    "?id={series_id}&cosd={start_date}&coed={end_date}"
)
SERIES_CONFIG = {
    "M2SL": {"name": "M2 money stock", "max_age_days": 65, "change_kind": "pct"},
    "RRPONTSYD": {"name": "Overnight reverse repos", "max_age_days": 10, "change_kind": "pct"},
    "DFF": {"name": "Effective federal funds rate", "max_age_days": 10, "change_kind": "points"},
}
NO_EXECUTION_NOTICE = "read-only macro context; no automatic trading or broker execution"

RequestFn = Callable[[str, int], tuple[int, str]]


def urllib_request_text(url: str, timeout_seconds: int) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Analista-macro-event-context/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text or text in {".", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_fred_csv(
    text: str,
    *,
    series_id: str,
    as_of: date | None = None,
    max_age_days: int | None = None,
) -> dict[str, Any]:
    rows = list(csv.DictReader(io.StringIO(text)))
    observations: list[tuple[date, float]] = []
    for row in rows:
        observation_date = _parse_date(row.get("DATE") or row.get("observation_date"))
        value = _to_float(row.get(series_id) or row.get("value"))
        if observation_date is not None and value is not None:
            observations.append((observation_date, value))

    observations.sort(key=lambda item: item[0])
    if not observations:
        return {
            "series_id": series_id,
            "status": "WARN",
            "issue": "fred_empty_or_invalid_series",
            "observations": 0,
            "latest_date": "",
            "latest_value": None,
            "change_4w": None,
            "age_days": None,
            "stale": True,
        }

    today = as_of or datetime.now(timezone.utc).date()
    latest_date, latest_value = observations[-1]
    comparison_target = latest_date - timedelta(days=28)
    comparison = next(
        ((obs_date, value) for obs_date, value in reversed(observations) if obs_date <= comparison_target),
        None,
    )
    change_4w = None
    if comparison is not None:
        previous_value = comparison[1]
        kind = SERIES_CONFIG.get(series_id, {}).get("change_kind", "pct")
        if kind == "points":
            change_4w = latest_value - previous_value
        elif previous_value != 0:
            change_4w = ((latest_value / previous_value) - 1.0) * 100.0

    age_days = max((today - latest_date).days, 0)
    allowed_age = int(
        max_age_days
        if max_age_days is not None
        else SERIES_CONFIG.get(series_id, {}).get("max_age_days", 10)
    )
    stale = age_days > allowed_age
    return {
        "series_id": series_id,
        "series_name": SERIES_CONFIG.get(series_id, {}).get("name", series_id),
        "status": "WARN" if stale else "PASS",
        "issue": "fred_series_stale" if stale else "",
        "observations": len(observations),
        "latest_date": latest_date.isoformat(),
        "latest_value": latest_value,
        "change_4w": change_4w,
        "change_4w_unit": "percentage_points"
        if SERIES_CONFIG.get(series_id, {}).get("change_kind") == "points"
        else "percent",
        "comparison_date": comparison[0].isoformat() if comparison else "",
        "age_days": age_days,
        "max_age_days": allowed_age,
        "stale": stale,
    }


def fetch_fred_series(
    series_id: str,
    *,
    timeout_seconds: int,
    request_fn: RequestFn,
    as_of: date,
) -> dict[str, Any]:
    url = FRED_CSV_URL.format(
        series_id=series_id,
        start_date=(as_of - timedelta(days=180)).isoformat(),
        end_date=as_of.isoformat(),
    )
    try:
        http_status, text = request_fn(url, timeout_seconds)
        if not 200 <= int(http_status) < 300:
            return {
                "series_id": series_id,
                "series_name": SERIES_CONFIG[series_id]["name"],
                "status": "WARN",
                "issue": "fred_http_unavailable",
                "http_status": int(http_status),
                "source_url": url,
                "latest_value": None,
                "change_4w": None,
                "stale": True,
            }
        result = parse_fred_csv(text, series_id=series_id, as_of=as_of)
        result["http_status"] = int(http_status)
        result["source_url"] = url
        return result
    except Exception as exc:
        return {
            "series_id": series_id,
            "series_name": SERIES_CONFIG[series_id]["name"],
            "status": "WARN",
            "issue": "fred_request_or_parse_exception",
            "message": f"{type(exc).__name__}: {str(exc)[:500]}",
            "http_status": 0,
            "source_url": url,
            "latest_value": None,
            "change_4w": None,
            "stale": True,
        }


def load_economic_calendar(
    path: Path,
    *,
    as_of: datetime | None = None,
    max_update_age_days: int = 45,
) -> dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    if not path.exists():
        return {
            "status": "WARN",
            "issue": "economic_calendar_missing",
            "path": str(path),
            "rows": 0,
            "events": [],
            "next_event": {},
            "event_risk_status": "UNKNOWN",
            "calendar_age_days": None,
            "stale": True,
        }

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except Exception as exc:
        return {
            "status": "WARN",
            "issue": "economic_calendar_read_error",
            "message": f"{type(exc).__name__}: {str(exc)[:500]}",
            "path": str(path),
            "rows": 0,
            "events": [],
            "next_event": {},
            "event_risk_status": "UNKNOWN",
            "calendar_age_days": None,
            "stale": True,
        }

    required = {
        "event_date",
        "event_time",
        "timezone",
        "event_type",
        "event_name",
        "importance",
        "source_url",
        "updated_at",
    }
    columns = set(rows[0].keys()) if rows else set()
    missing_columns = sorted(required - columns)
    if not rows or missing_columns:
        return {
            "status": "WARN",
            "issue": "economic_calendar_schema_invalid" if missing_columns else "economic_calendar_empty",
            "missing_columns": missing_columns,
            "path": str(path),
            "rows": len(rows),
            "events": [],
            "next_event": {},
            "event_risk_status": "UNKNOWN",
            "calendar_age_days": None,
            "stale": True,
        }

    events: list[dict[str, Any]] = []
    update_dates: list[date] = []
    invalid_rows = 0
    for row in rows:
        event_date = _parse_date(row.get("event_date"))
        updated_at = _parse_date(row.get("updated_at"))
        if event_date is None:
            invalid_rows += 1
            continue
        if updated_at is not None:
            update_dates.append(updated_at)
        try:
            event_time = time.fromisoformat(str(row.get("event_time") or "00:00").strip())
            event_zone = ZoneInfo(str(row.get("timezone") or "America/New_York").strip())
            event_at = datetime.combine(event_date, event_time, tzinfo=event_zone)
        except Exception:
            invalid_rows += 1
            continue

        events.append(
            {
                "event_date": event_date.isoformat(),
                "event_time": event_time.strftime("%H:%M"),
                "timezone": str(row.get("timezone") or "America/New_York").strip(),
                "event_type": str(row.get("event_type") or "").strip().upper(),
                "event_name": str(row.get("event_name") or "").strip(),
                "importance": str(row.get("importance") or "").strip().upper(),
                "source_url": str(row.get("source_url") or "").strip(),
                "updated_at": updated_at.isoformat() if updated_at else "",
                "_event_at": event_at,
            }
        )

    events.sort(key=lambda item: item["_event_at"])
    future_events = [item for item in events if item["_event_at"] >= now.astimezone(item["_event_at"].tzinfo)]
    next_event = future_events[0] if future_events else {}
    days_to_event = None
    event_risk_status = "UNKNOWN"
    if next_event:
        local_now = now.astimezone(next_event["_event_at"].tzinfo)
        days_to_event = (next_event["_event_at"].date() - local_now.date()).days
        if days_to_event <= 0:
            event_risk_status = "TODAY"
        elif days_to_event <= 1:
            event_risk_status = "WITHIN_1_DAY"
        elif days_to_event <= 3:
            event_risk_status = "WITHIN_3_DAYS"
        else:
            event_risk_status = "CLEAR"

    latest_update = max(update_dates) if update_dates else None
    calendar_age_days = max((now.date() - latest_update).days, 0) if latest_update else None
    stale = calendar_age_days is None or calendar_age_days > int(max_update_age_days)
    issue = ""
    if invalid_rows:
        issue = "economic_calendar_invalid_rows"
    if stale:
        issue = "economic_calendar_stale"
    if not next_event:
        issue = "economic_calendar_no_future_events"

    clean_events = [{key: value for key, value in item.items() if key != "_event_at"} for item in events]
    clean_next = {key: value for key, value in next_event.items() if key != "_event_at"}
    if clean_next:
        clean_next["days_to_event"] = days_to_event

    return {
        "status": "WARN" if issue else "PASS",
        "issue": issue,
        "path": str(path),
        "rows": len(events),
        "invalid_rows": invalid_rows,
        "events": clean_events,
        "upcoming_events": [
            {key: value for key, value in item.items() if key != "_event_at"}
            for item in future_events[:10]
        ],
        "next_event": clean_next,
        "event_risk_status": event_risk_status,
        "latest_update": latest_update.isoformat() if latest_update else "",
        "calendar_age_days": calendar_age_days,
        "max_update_age_days": int(max_update_age_days),
        "stale": stale,
    }


def classify_liquidity_context(series: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    notes: list[str] = []
    signals: list[int] = []
    m2_change = _to_float(series.get("M2SL", {}).get("change_4w"))
    rrp_change = _to_float(series.get("RRPONTSYD", {}).get("change_4w"))

    if m2_change is not None:
        m2_signal = 1 if m2_change > 0.1 else -1 if m2_change < -0.1 else 0
        signals.append(m2_signal)
        notes.append(f"M2 4w change {m2_change:.2f}%")
    if rrp_change is not None:
        rrp_signal = 1 if rrp_change < -5.0 else -1 if rrp_change > 5.0 else 0
        signals.append(rrp_signal)
        notes.append(f"reverse repo 4w change {rrp_change:.2f}%")

    if not signals:
        return "UNKNOWN", ["insufficient M2/reverse repo history"]
    if 1 in signals and -1 in signals:
        return "MIXED", notes
    score = sum(signals)
    if score > 0:
        return "EXPANDING", notes
    if score < 0:
        return "CONTRACTING", notes
    return "MIXED", notes


def run_report(
    *,
    calendar_path: Path = DEFAULT_CALENDAR,
    timeout_seconds: int = 20,
    request_fn: RequestFn = urllib_request_text,
    as_of: datetime | None = None,
    calendar_max_update_age_days: int = 45,
) -> dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    with ThreadPoolExecutor(max_workers=len(SERIES_CONFIG)) as executor:
        futures = {
            series_id: executor.submit(
                fetch_fred_series,
                series_id,
                timeout_seconds=timeout_seconds,
                request_fn=request_fn,
                as_of=now.date(),
            )
            for series_id in SERIES_CONFIG
        }
        series = {series_id: future.result() for series_id, future in futures.items()}
    calendar = load_economic_calendar(
        calendar_path,
        as_of=now,
        max_update_age_days=calendar_max_update_age_days,
    )
    liquidity_context, liquidity_notes = classify_liquidity_context(series)
    issues = sorted(
        {
            item.get("issue")
            for item in [calendar, *series.values()]
            if item.get("issue")
        }
    )
    status = "PASS" if calendar.get("status") == "PASS" and all(
        item.get("status") == "PASS" for item in series.values()
    ) else "WARN"
    next_event = calendar.get("next_event", {}) or {}

    return {
        "status": status,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "read_only": True,
        "execution_enabled": False,
        "notice": NO_EXECUTION_NOTICE,
        "source": "FRED_AND_AUDITABLE_ECONOMIC_CALENDAR",
        "data_freshness": "MIXED_OFFICIAL_RELEASE_FREQUENCIES",
        "economic_calendar": calendar,
        "next_critical_event": next_event.get("event_name", ""),
        "next_critical_event_date": next_event.get("event_date", ""),
        "days_to_critical_event": next_event.get("days_to_event"),
        "event_risk_status": calendar.get("event_risk_status", "UNKNOWN"),
        "fred_series": series,
        "m2_latest": series["M2SL"].get("latest_value"),
        "m2_change_4w_pct": series["M2SL"].get("change_4w"),
        "reverse_repo_latest": series["RRPONTSYD"].get("latest_value"),
        "reverse_repo_change_4w_pct": series["RRPONTSYD"].get("change_4w"),
        "effective_fed_funds_rate": series["DFF"].get("latest_value"),
        "liquidity_context": liquidity_context,
        "macro_event_status": status,
        "macro_event_notes": "; ".join(liquidity_notes),
        "issues": issues,
        "guardrails": {
            "scanner_rows_modified": False,
            "scoring_modified": False,
            "signals_modified": False,
            "thresholds_modified": False,
            "broker_execution": False,
        },
    }


def build_markdown(result: dict[str, Any]) -> str:
    calendar = result.get("economic_calendar", {}) or {}
    lines = [
        "# Analista - Macro event and liquidity context",
        "",
        f"- status: {result.get('status', 'UNKNOWN')}",
        f"- generated_at: {result.get('generated_at', '')}",
        f"- mode: {result.get('mode', 'READ_ONLY')}",
        f"- source: {result.get('source', '')}",
        f"- data_freshness: {result.get('data_freshness', '')}",
        f"- notice: {result.get('notice', NO_EXECUTION_NOTICE)}",
        "",
        "## Event risk",
        "",
        f"- next_critical_event: {result.get('next_critical_event', '') or 'UNKNOWN'}",
        f"- next_critical_event_date: {result.get('next_critical_event_date', '') or 'UNKNOWN'}",
        f"- days_to_critical_event: {result.get('days_to_critical_event')}",
        f"- event_risk_status: {result.get('event_risk_status', 'UNKNOWN')}",
        f"- calendar_latest_update: {calendar.get('latest_update', '')}",
        f"- calendar_age_days: {calendar.get('calendar_age_days')}",
        "",
        "## Liquidity",
        "",
        f"- liquidity_context: {result.get('liquidity_context', 'UNKNOWN')}",
        f"- M2 latest: {result.get('m2_latest')}",
        f"- M2 change 4w pct: {result.get('m2_change_4w_pct')}",
        f"- reverse repo latest: {result.get('reverse_repo_latest')}",
        f"- reverse repo change 4w pct: {result.get('reverse_repo_change_4w_pct')}",
        f"- effective fed funds rate: {result.get('effective_fed_funds_rate')}",
        f"- notes: {result.get('macro_event_notes', '')}",
        "",
        "## Official series",
        "",
    ]
    for series_id, item in (result.get("fred_series", {}) or {}).items():
        lines.append(
            f"- {series_id}: status={item.get('status', 'UNKNOWN')} "
            f"latest={item.get('latest_value')} date={item.get('latest_date', '')} "
            f"age_days={item.get('age_days')} change_4w={item.get('change_4w')} "
            f"source={item.get('source_url', '')}"
        )
    lines.extend(["", "## Upcoming critical events", ""])
    for event in calendar.get("upcoming_events", []) or []:
        lines.append(
            f"- {event.get('event_date')} {event.get('event_time')} {event.get('timezone')} | "
            f"{event.get('event_type')} | {event.get('event_name')} | {event.get('source_url')}"
        )
    if not calendar.get("upcoming_events"):
        lines.append("- none")
    lines.extend(["", "## Issues", ""])
    lines.extend([f"- {issue}" for issue in result.get("issues", [])] or ["- none"])
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Context only; scanner rows, scoring, signals and thresholds remain unchanged.",
            "- No automatic trading and no broker execution.",
        ]
    )
    return "\n".join(lines)


def save_reports(result: dict[str, Any], *, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(result), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera contexto macro, eventos y liquidez read-only.")
    parser.add_argument("--calendar", default=str(DEFAULT_CALENDAR))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--calendar-max-update-age-days", type=int, default=45)
    args = parser.parse_args()

    result = run_report(
        calendar_path=Path(args.calendar),
        timeout_seconds=args.timeout_seconds,
        calendar_max_update_age_days=args.calendar_max_update_age_days,
    )
    save_reports(result, json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))
    print("=== ANALISTA MACRO EVENT CONTEXT ===")
    print(f"Status: {result.get('status')}")
    print(f"Next event: {result.get('next_critical_event') or 'UNKNOWN'}")
    print(f"Event risk: {result.get('event_risk_status')}")
    print(f"Liquidity context: {result.get('liquidity_context')}")
    print(f"Issues: {', '.join(result.get('issues', []) or ['none'])}")
    print(f"JSON: {Path(args.json_out)}")
    print(f"Markdown: {Path(args.markdown_out)}")
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
