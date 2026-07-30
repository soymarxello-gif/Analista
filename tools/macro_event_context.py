from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config_loader import load_config
from data.price_client import download_daily_prices
from engine.data_sources.fred_macro import (
    FRED_CSV_URL,
    SERIES_CONFIG,
    DataReaderFn,
    fetch_fred_bundle,
    parse_fred_csv_observations,
    summarize_observations,
)

DEFAULT_CALENDAR = ROOT / "data" / "economic_calendar.csv"
DEFAULT_JSON_OUT = ROOT / "reports" / "macro_event_context_latest.json"
DEFAULT_MARKDOWN_OUT = ROOT / "reports" / "macro_event_context_latest.md"
DEFAULT_FRED_CACHE = ROOT / "cache" / "macro" / "fred_latest.json"
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
    today = as_of or datetime.now(timezone.utc).date()
    observations = parse_fred_csv_observations(text, series_id)
    result = summarize_observations(observations, series_id=series_id, as_of=today)
    if max_age_days is not None and result.get("latest_date"):
        result["max_age_days"] = int(max_age_days)
        result["stale"] = int(result.get("age_days") or 0) > int(max_age_days)
        result["status"] = "WARN" if result["stale"] else "PASS"
        result["issue"] = "fred_series_stale" if result["stale"] else ""
    return result


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
        result["provider"] = "FRED_CSV_DIRECT"
        result["source"] = url
        result["source_url"] = url
        result["cache_status"] = "NOT_USED"
        result["fallback_used"] = True
        result["errors"] = []
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
            "provider": "UNAVAILABLE",
            "source": url,
            "cache_status": "MISS",
            "fallback_used": True,
            "errors": [f"{type(exc).__name__}: {str(exc)[:500]}"],
            "latest_value": None,
            "change_4w": None,
            "stale": True,
        }


def _latest_yahoo_close(frame: pd.DataFrame | None) -> float | None:
    if frame is None or frame.empty or "close" not in frame.columns:
        return None
    values = pd.to_numeric(frame["close"], errors="coerce").dropna()
    return float(values.iloc[-1]) if not values.empty else None


def build_cross_source_diagnostics(
    fred_series: dict[str, dict[str, Any]],
    yahoo_prices: dict[str, pd.DataFrame] | None,
) -> list[dict[str, Any]]:
    mappings = [
        ("DGS10", "^TNX", "yield", 0.25),
        ("DGS30", "^TYX", "yield", 0.25),
        ("VIXCLS", "^VIX", "identity", 2.0),
        ("DCOILWTICO", "CL=F", "identity", 10.0),
    ]
    diagnostics: list[dict[str, Any]] = []
    prices = yahoo_prices or {}
    for fred_id, yahoo_symbol, normalization, tolerance in mappings:
        official = _to_float(fred_series.get(fred_id, {}).get("latest_value"))
        yahoo_raw = _latest_yahoo_close(prices.get(yahoo_symbol))
        if yahoo_raw is None:
            yahoo_value = None
        elif normalization == "yield" and yahoo_raw > 20:
            yahoo_value = yahoo_raw * 0.1
        else:
            yahoo_value = yahoo_raw
        difference = (
            yahoo_value - official
            if yahoo_value is not None and official is not None
            else None
        )
        if difference is None:
            status = "UNAVAILABLE"
        elif abs(difference) <= tolerance:
            status = "ALIGNED"
        else:
            status = "DIVERGENT_REVIEW"
        diagnostics.append(
            {
                "fred_series": fred_id,
                "yahoo_symbol": yahoo_symbol,
                "fred_value": official,
                "yahoo_value_normalized": yahoo_value,
                "difference": difference,
                "tolerance": tolerance,
                "status": status,
                "note": "diagnostic only; sources may differ by timestamp, methodology or futures basis",
            }
        )
    diagnostics.append(
        {
            "fred_series": "DTWEXBGS",
            "yahoo_symbol": "DX-Y.NYB",
            "status": "NOT_DIRECTLY_COMPARABLE",
            "note": "trade-weighted broad dollar index and DXY use different baskets",
        }
    )
    return diagnostics


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


def classify_macro_regime(result: dict[str, Any]) -> dict[str, Any]:
    event_risk = str(result.get("event_risk_status") or "UNKNOWN").upper()
    liquidity = str(result.get("liquidity_context") or "UNKNOWN").upper()
    vix = _to_float(result.get("vix_official"))
    hy_spread = _to_float(result.get("high_yield_spread"))
    curve_10y2y = _to_float(result.get("yield_curve_10y2y"))

    notes: list[str] = []
    risk_points = 0
    supportive_points = 0

    if event_risk in {"TODAY", "WITHIN_1_DAY", "WITHIN_3_DAYS"}:
        risk_points += 2 if event_risk in {"TODAY", "WITHIN_1_DAY"} else 1
        notes.append(f"macro_event_risk_{event_risk.lower()}")
    if liquidity == "EXPANDING":
        supportive_points += 1
        notes.append("liquidity_expanding")
    elif liquidity == "CONTRACTING":
        risk_points += 1
        notes.append("liquidity_contracting")
    elif liquidity == "MIXED":
        notes.append("liquidity_mixed")
    if vix is not None:
        if vix >= 25:
            risk_points += 2
            notes.append("vix_elevated")
        elif vix <= 18:
            supportive_points += 1
            notes.append("vix_calm")
    if hy_spread is not None:
        if hy_spread >= 4.5:
            risk_points += 1
            notes.append("high_yield_spread_elevated")
        elif hy_spread <= 3.5:
            supportive_points += 1
            notes.append("credit_spread_calm")
    if curve_10y2y is not None and curve_10y2y < -0.5:
        risk_points += 1
        notes.append("yield_curve_deeply_inverted")

    if event_risk in {"TODAY", "WITHIN_1_DAY"}:
        mode = "EVENT_RISK_ELEVATED"
    elif liquidity == "CONTRACTING" and risk_points >= supportive_points:
        mode = "LIQUIDITY_CONFLICT"
    elif risk_points >= 3:
        mode = "DEFENSIVE"
    elif supportive_points >= 2 and risk_points == 0:
        mode = "RISK_ON_SUPPORTIVE"
    elif risk_points == 0 and supportive_points == 0:
        mode = "UNKNOWN"
    else:
        mode = "BALANCED_MACRO"

    confidence = "HIGH" if vix is not None and liquidity != "UNKNOWN" and event_risk != "UNKNOWN" else "MEDIUM"
    if mode == "UNKNOWN":
        confidence = "UNKNOWN"
    return {
        "macro_regime_mode": mode,
        "macro_regime_confidence": confidence,
        "macro_event_risk": event_risk,
        "macro_liquidity_bias": liquidity,
        "macro_regime_notes": "; ".join(notes) or "macro_context_insufficient",
    }


def run_report(
    *,
    calendar_path: Path = DEFAULT_CALENDAR,
    timeout_seconds: int = 20,
    request_fn: RequestFn | None = None,
    datareader_fn: DataReaderFn | None = None,
    cache_path: Path = DEFAULT_FRED_CACHE,
    retries: int = 3,
    backoff_factor: float = 0.6,
    yahoo_prices_fn: Callable[..., dict[str, pd.DataFrame]] | None = None,
    as_of: datetime | None = None,
    calendar_max_update_age_days: int = 45,
) -> dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if request_fn is not None and datareader_fn is None:
        def injected_csv_only(*args, **kwargs):
            raise RuntimeError("pandas_datareader_disabled_for_injected_csv_request")

        datareader_fn = injected_csv_only

    fred_bundle = fetch_fred_bundle(
        as_of=now.date(),
        timeout_seconds=timeout_seconds,
        cache_path=cache_path,
        datareader_fn=datareader_fn,
        request_fn=request_fn,
        retries=retries,
        backoff_factor=backoff_factor,
    )
    series = fred_bundle["series"]
    yahoo_prices: dict[str, pd.DataFrame] = {}
    yahoo_error = ""
    if yahoo_prices_fn is not None:
        try:
            yahoo_prices = yahoo_prices_fn(
                ["^TNX", "^TYX", "^VIX", "CL=F"],
                period="3mo",
                interval="1d",
            )
        except Exception as exc:
            yahoo_error = f"{type(exc).__name__}: {str(exc)[:500]}"
    cross_source_diagnostics = build_cross_source_diagnostics(series, yahoo_prices)
    calendar = load_economic_calendar(
        calendar_path,
        as_of=now,
        max_update_age_days=calendar_max_update_age_days,
    )
    liquidity_context, liquidity_notes = classify_liquidity_context(series)
    peripheral_series = {"M2V"}
    critical_issues = sorted(
        {
            item.get("issue")
            for item in [calendar]
            if item.get("issue")
        }
        | {
            item.get("issue")
            for series_id, item in series.items()
            if series_id not in peripheral_series and item.get("issue")
        }
    )
    peripheral_issues = sorted(
        {
            f"{series_id}:{item.get('issue')}"
            for series_id, item in series.items()
            if series_id in peripheral_series and item.get("issue")
        }
    )
    issues = [*critical_issues, *peripheral_issues]
    status = "PASS" if not critical_issues else "WARN"
    next_event = calendar.get("next_event", {}) or {}

    result = {
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
        "fred_provider_counts": fred_bundle.get("provider_counts", {}),
        "fred_cache_path": fred_bundle.get("cache_path", str(cache_path)),
        "fred_cache_updated": fred_bundle.get("cache_updated", False),
        "cross_source_diagnostics": cross_source_diagnostics,
        "cross_source_yahoo_error": yahoo_error,
        "m2_latest": series["M2SL"].get("latest_value"),
        "m2_change_4w_pct": series["M2SL"].get("change_4w"),
        "reverse_repo_latest": series["RRPONTSYD"].get("latest_value"),
        "reverse_repo_change_4w_pct": series["RRPONTSYD"].get("change_4w"),
        "effective_fed_funds_rate": series["DFF"].get("latest_value"),
        "us10y_official": series["DGS10"].get("latest_value"),
        "us30y_official": series["DGS30"].get("latest_value"),
        "yield_curve_10y2y": series["T10Y2Y"].get("latest_value"),
        "yield_curve_10y3m": series["T10Y3M"].get("latest_value"),
        "vix_official": series["VIXCLS"].get("latest_value"),
        "high_yield_spread": series["BAMLH0A0HYM2"].get("latest_value"),
        "cpi_index": series["CPIAUCSL"].get("latest_value"),
        "nonfarm_payrolls": series["PAYEMS"].get("latest_value"),
        "unemployment_rate": series["UNRATE"].get("latest_value"),
        "m2_velocity": series["M2V"].get("latest_value"),
        "liquidity_context": liquidity_context,
        "macro_event_status": status,
        "macro_event_notes": "; ".join(liquidity_notes),
        "issues": issues,
        "critical_issues": critical_issues,
        "peripheral_issues": peripheral_issues,
        "peripheral_series_do_not_reduce_regime_confidence": sorted(peripheral_series),
        "guardrails": {
            "scanner_rows_modified": False,
            "scoring_modified": False,
            "signals_modified": False,
            "thresholds_modified": False,
            "broker_execution": False,
        },
    }
    result.update(classify_macro_regime(result))
    return result


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
        f"- macro_regime_mode: {result.get('macro_regime_mode', 'UNKNOWN')}",
        f"- macro_regime_confidence: {result.get('macro_regime_confidence', 'UNKNOWN')}",
        f"- macro_event_risk: {result.get('macro_event_risk', 'UNKNOWN')}",
        f"- macro_liquidity_bias: {result.get('macro_liquidity_bias', 'UNKNOWN')}",
        f"- macro_regime_notes: {result.get('macro_regime_notes', '')}",
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
        f"- US10Y official: {result.get('us10y_official')}",
        f"- US30Y official: {result.get('us30y_official')}",
        f"- yield curve 10y-2y: {result.get('yield_curve_10y2y')}",
        f"- yield curve 10y-3m: {result.get('yield_curve_10y3m')}",
        f"- high yield spread: {result.get('high_yield_spread')}",
        f"- notes: {result.get('macro_event_notes', '')}",
        "",
        "## Official series",
        "",
    ]
    for series_id, item in (result.get("fred_series", {}) or {}).items():
        lines.append(
            f"- {series_id}: status={item.get('status', 'UNKNOWN')} "
            f"latest={item.get('latest_value')} date={item.get('latest_date', '')} "
            f"age_days={item.get('age_days')} change={item.get('change_value')} "
            f"provider={item.get('provider', '')} cache={item.get('cache_status', '')} "
            f"fallback={item.get('fallback_used')} source={item.get('source_url', '')}"
        )
    lines.extend(["", "## Yahoo / FRED diagnostics", ""])
    for item in result.get("cross_source_diagnostics", []) or []:
        lines.append(
            f"- {item.get('fred_series')} vs {item.get('yahoo_symbol')}: "
            f"status={item.get('status')} fred={item.get('fred_value')} "
            f"yahoo={item.get('yahoo_value_normalized')} difference={item.get('difference')} "
            f"note={item.get('note', '')}"
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
    lines.extend(["", "## Issue severity", ""])
    lines.append(
        "- critical: "
        + (", ".join(result.get("critical_issues", [])) or "none")
    )
    lines.append(
        "- peripheral: "
        + (", ".join(result.get("peripheral_issues", [])) or "none")
    )
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
    parser.add_argument("--cache-path", default=str(DEFAULT_FRED_CACHE))
    parser.add_argument("--calendar-max-update-age-days", type=int, default=45)
    args = parser.parse_args()

    config = load_config()
    fred_config = (
        config.get("data_sources", {})
        .get("providers", {})
        .get("fred", {})
    )
    result = run_report(
        calendar_path=Path(args.calendar),
        timeout_seconds=int(fred_config.get("timeout_seconds", args.timeout_seconds)),
        cache_path=ROOT / str(fred_config.get("cache_path", args.cache_path)),
        retries=int(fred_config.get("retries", 3)),
        backoff_factor=float(fred_config.get("backoff_factor", 0.6)),
        yahoo_prices_fn=download_daily_prices,
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
