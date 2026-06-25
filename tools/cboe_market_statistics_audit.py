from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.data_sources.provider_contract import ProviderResponse

DEFAULT_JSON_OUT = ROOT / "reports" / "cboe_market_statistics_latest.json"
DEFAULT_MARKDOWN_OUT = ROOT / "reports" / "cboe_market_statistics_latest.md"
DEFAULT_MARKET_SHARE_URL = "https://www.cboe.com/us/options/market_share/market/csv/"
DEFAULT_TOTAL_PUT_CALL_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv"
DEFAULT_EQUITIES_MARKET_VOLUME_URL = (
    "https://cdn.cboe.com/resources/us/equities/market-statistics/historical-market-volume/market_history_2026.csv"
)
NO_REAL_ORDER_NOTICE = "read-only Cboe market statistics audit; no real order"

RequestFn = Callable[[str, int], tuple[int, str]]


def urllib_request_text(url: str, timeout_seconds: int) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Analista-cboe-market-statistics-audit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return int(response.status), payload
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), payload


def _to_float(value: Any) -> float | None:
    text = str(value or "").replace(",", "").replace("%", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _date_age_days(value: date | None, *, today: date | None = None) -> int | None:
    if value is None:
        return None
    return max(((today or datetime.now(timezone.utc).date()) - value).days, 0)


def _latest_rows(rows: list[dict[str, str]]) -> tuple[date | None, list[dict[str, str]]]:
    dated: list[tuple[date, dict[str, str]]] = []
    for row in rows:
        parsed = _parse_date(row.get("Day") or row.get("DAY") or row.get("Date") or row.get("DATE"))
        if parsed is not None:
            dated.append((parsed, row))
    if not dated:
        return None, []
    latest_date = max(item[0] for item in dated)
    return latest_date, [row for parsed, row in dated if parsed == latest_date]


def _find_csv_header(text: str, required_columns: set[str]) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        normalized = {part.strip().upper() for part in line.split(",")}
        if required_columns.issubset(normalized):
            return "\n".join(lines[index:])
    return text


def _rows_from_csv(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader if any(str(value or "").strip() for value in row.values())]


def parse_market_share_csv(text: str) -> dict[str, Any]:
    rows = _rows_from_csv(_find_csv_header(text, {"DAY", "MARKET PARTICIPANT"}))
    if not rows:
        return {"status": "WARN", "rows": 0, "latest_date": "", "total_option_contracts": None}
    latest_date, current_rows = _latest_rows(rows)
    total_volume = 0.0
    for row in current_rows:
        number = _to_float(row.get("Total Option Contracts"))
        if number is not None:
            total_volume += number
    return {
        "status": "PASS" if latest_date and total_volume > 0 else "WARN",
        "rows": len(current_rows),
        "all_rows": len(rows),
        "latest_date": latest_date.isoformat() if latest_date else "",
        "age_days": _date_age_days(latest_date),
        "total_option_contracts": total_volume if total_volume > 0 else None,
        "columns": list(rows[0].keys()),
    }


def parse_put_call_csv(text: str) -> dict[str, Any]:
    csv_text = _find_csv_header(text, {"DATE"})
    rows = _rows_from_csv(csv_text)
    if not rows:
        return {"status": "WARN", "rows": 0, "latest_date": "", "put_call_ratio": None}

    latest_date, latest_rows = _latest_rows(rows)
    latest = latest_rows[0] if latest_rows else {}
    keys = {str(key).lower(): key for key in latest.keys()}
    ratio_key = next(
        (key for lower, key in keys.items() if "ratio" in lower and ("p/c" in lower or "put" in lower)),
        "",
    )
    put_key = next((key for lower, key in keys.items() if lower in {"puts", "put volume", "total put volume"}), "")
    call_key = next((key for lower, key in keys.items() if lower in {"calls", "call volume", "total call volume"}), "")
    put_value = _to_float(latest.get(put_key)) if put_key else None
    call_value = _to_float(latest.get(call_key)) if call_key else None
    ratio_value = _to_float(latest.get(ratio_key)) if ratio_key else None
    if ratio_value is None and put_value is not None and call_value:
        ratio_value = put_value / call_value
    return {
        "status": "PASS" if ratio_value is not None else "WARN",
        "rows": len(rows),
        "latest_date": latest_date.isoformat() if latest_date else "",
        "age_days": _date_age_days(latest_date),
        "put_volume": put_value,
        "call_volume": call_value,
        "put_call_ratio": ratio_value,
        "columns": list(latest.keys()),
    }


def parse_equities_market_volume_csv(text: str) -> dict[str, Any]:
    rows = _rows_from_csv(_find_csv_header(text, {"DAY", "MARKET PARTICIPANT"}))
    if not rows:
        return {"status": "WARN", "rows": 0, "latest_date": "", "total_shares": None}
    latest_date, current_rows = _latest_rows(rows)
    total_shares = sum(
        number
        for number in (_to_float(row.get("Total Shares")) for row in current_rows)
        if number is not None
    )
    return {
        "status": "PASS" if latest_date and total_shares > 0 else "WARN",
        "rows": len(current_rows),
        "all_rows": len(rows),
        "latest_date": latest_date.isoformat() if latest_date else "",
        "age_days": _date_age_days(latest_date),
        "total_shares": total_shares if total_shares > 0 else None,
        "columns": list(rows[0].keys()),
    }


def _classify_put_call_context(summary: dict[str, Any], *, max_age_days: int) -> dict[str, Any]:
    ratio = _to_float(summary.get("put_call_ratio"))
    age_days = summary.get("age_days")
    if ratio is None:
        return {
            "status": "UNKNOWN",
            "bias": "UNKNOWN_OPTIONS_CONTEXT",
            "contrarian_note": "Cboe aggregate put/call ratio unavailable",
            "usable": False,
        }
    if age_days is None or int(age_days) > int(max_age_days):
        return {
            "status": "STALE",
            "bias": "UNKNOWN_OPTIONS_CONTEXT",
            "contrarian_note": "historical Cboe put/call ratio is stale and must not be treated as current sentiment",
            "usable": False,
        }
    if ratio >= 1.2:
        bias = "CROWDED_BEARISH_AGGREGATE"
        note = "elevated aggregate put/call; contrarian bullish context only, not a ticker signal"
    elif ratio <= 0.65:
        bias = "CROWDED_BULLISH_AGGREGATE"
        note = "low aggregate put/call; contrarian caution only, not a ticker signal"
    else:
        bias = "NEUTRAL_AGGREGATE"
        note = "aggregate put/call is within a neutral range"
    return {"status": "CURRENT", "bias": bias, "contrarian_note": note, "usable": True}


def _fetch_and_parse(
    name: str,
    url: str,
    timeout_seconds: int,
    request_fn: RequestFn,
    parser: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        http_status, text = request_fn(url, timeout_seconds)
        if not (200 <= int(http_status) < 300):
            return {
                "name": name,
                "status": "WARN",
                "http_status": int(http_status),
                "checked_at": checked_at,
                "issue": "cboe_http_unavailable",
                "summary": {},
            }
        summary = parser(text)
        return {
            "name": name,
            "status": str(summary.get("status", "WARN")),
            "http_status": int(http_status),
            "checked_at": checked_at,
            "issue": "" if summary.get("status") == "PASS" else "cboe_schema_or_empty_data",
            "summary": summary,
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "WARN",
            "http_status": 0,
            "checked_at": checked_at,
            "issue": "cboe_request_or_parse_exception",
            "message": f"{type(exc).__name__}: {str(exc)[:500]}",
            "summary": {},
        }


def run_audit(
    *,
    market_share_url: str = DEFAULT_MARKET_SHARE_URL,
    total_put_call_url: str = DEFAULT_TOTAL_PUT_CALL_URL,
    equities_market_volume_url: str = DEFAULT_EQUITIES_MARKET_VOLUME_URL,
    timeout_seconds: int = 20,
    max_age_days: int = 5,
    request_fn: RequestFn = urllib_request_text,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    provider = ProviderResponse(
        provider_name="cboe",
        status="WARN",
        source="CBOE_MARKET_STATISTICS_CSV",
        timestamp=generated_at,
        data_freshness="EOD",
        confidence="MEDIUM",
        notes=["aggregate options/equities market statistics only"],
    ).to_dict()

    checks = [
        _fetch_and_parse("options_market_share", market_share_url, timeout_seconds, request_fn, parse_market_share_csv),
        _fetch_and_parse("total_put_call", total_put_call_url, timeout_seconds, request_fn, parse_put_call_csv),
        _fetch_and_parse(
            "equities_market_volume",
            equities_market_volume_url,
            timeout_seconds,
            request_fn,
            parse_equities_market_volume_csv,
        ),
    ]
    for check in checks:
        summary = check.get("summary", {}) or {}
        age_days = summary.get("age_days")
        if age_days is not None and int(age_days) > int(max_age_days):
            check["status"] = "WARN"
            check["issue"] = "cboe_dataset_stale"
            summary["stale"] = True
        else:
            summary["stale"] = False

    put_call_check = next(
        (check for check in checks if check.get("name") == "total_put_call"),
        {},
    )
    put_call_context = _classify_put_call_context(
        put_call_check.get("summary", {}) or {},
        max_age_days=max_age_days,
    )
    issues = sorted({check.get("issue") for check in checks if check.get("issue")})
    pass_count = sum(1 for check in checks if check.get("status") == "PASS")
    status = "PASS" if pass_count == len(checks) else "WARN"
    provider["status"] = status
    provider["errors"] = issues
    provider["fields"] = {
        "aggregate_put_call_status": put_call_context["status"],
        "aggregate_options_bias": put_call_context["bias"],
        "aggregate_put_call_usable": put_call_context["usable"],
    }

    return {
        "status": status,
        "generated_at": generated_at,
        "mode": "READ_ONLY",
        "provider": provider,
        "read_only": True,
        "execution_enabled": False,
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        "datasets_checked": len(checks),
        "datasets_available": pass_count,
        "endpoint_checks": checks,
        "aggregate_options_context": put_call_context,
        "issues": issues,
    }


def build_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Analista - Cboe market statistics audit",
        "",
        f"- status: {result.get('status', 'UNKNOWN')}",
        f"- mode: {result.get('mode', 'READ_ONLY')}",
        f"- generated_at: {result.get('generated_at', '')}",
        f"- datasets_checked: {result.get('datasets_checked', 0)}",
        f"- datasets_available: {result.get('datasets_available', 0)}",
        f"- read_only: {result.get('read_only', True)}",
        f"- execution_enabled: {result.get('execution_enabled', False)}",
        f"- notice: {result.get('no_real_order_notice', NO_REAL_ORDER_NOTICE)}",
        "",
        "## Datasets",
        "",
    ]
    for check in result.get("endpoint_checks", []) or []:
        summary = check.get("summary", {}) or {}
        lines.append(
            f"- {check.get('name', '')}: {check.get('status', 'MISSING')} "
            f"rows={summary.get('rows', 0)} latest_date={summary.get('latest_date', '')} "
            f"age_days={summary.get('age_days', '')} stale={summary.get('stale', False)} "
            f"issue={check.get('issue', '')}"
        )

    context = result.get("aggregate_options_context", {}) or {}
    lines.extend(
        [
            "",
            "## Aggregate options context",
            "",
            f"- status: {context.get('status', 'UNKNOWN')}",
            f"- bias: {context.get('bias', 'UNKNOWN_OPTIONS_CONTEXT')}",
            f"- usable: {context.get('usable', False)}",
            f"- contrarian_note: {context.get('contrarian_note', '')}",
        ]
    )
    lines.extend(["", "## Issues", ""])
    issues = result.get("issues", []) or []
    lines.extend([f"- {issue}" for issue in issues] or ["- none"])
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Aggregate market statistics only.",
            "- No scanner, scoring, threshold, signal, journal, or outcome writes.",
            "- No real order.",
        ]
    )
    return "\n".join(lines)


def save_reports(result: dict[str, Any], *, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(result), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita estadisticas Cboe read-only por CSV publico.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--market-share-url", default=DEFAULT_MARKET_SHARE_URL)
    parser.add_argument("--total-put-call-url", default=DEFAULT_TOTAL_PUT_CALL_URL)
    parser.add_argument("--equities-market-volume-url", default=DEFAULT_EQUITIES_MARKET_VOLUME_URL)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--max-age-days", type=int, default=5)
    args = parser.parse_args()

    result = run_audit(
        market_share_url=args.market_share_url,
        total_put_call_url=args.total_put_call_url,
        equities_market_volume_url=args.equities_market_volume_url,
        timeout_seconds=args.timeout_seconds,
        max_age_days=args.max_age_days,
    )
    save_reports(result, json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))

    print("=== ANALISTA CBOE MARKET STATISTICS AUDIT ===")
    print(f"Status: {result.get('status')}")
    print(f"Datasets available: {result.get('datasets_available')}/{result.get('datasets_checked')}")
    print(f"Issues: {', '.join(result.get('issues', []) or ['none'])}")
    print(f"Notice: {NO_REAL_ORDER_NOTICE}")
    print(f"JSON: {Path(args.json_out)}")
    print(f"Markdown: {Path(args.markdown_out)}")
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
