from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.data_sources.provider_contract import ProviderResponse
from engine.data_sources.google_sheets_manual import (
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    parse_google_sheets_csv,
)
from config_loader import load_config

DEFAULT_JSON_OUT = ROOT / "reports" / "google_sheets_data_source_latest.json"
DEFAULT_MARKDOWN_OUT = ROOT / "reports" / "google_sheets_data_source_latest.md"
NO_REAL_ORDER_NOTICE = "read-only Google Sheets manual data source audit; no real order"
RequestFn = Callable[[str, int], tuple[int, str]]


def urllib_request_text(url: str, timeout_seconds: int) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Analista-google-sheets-source-audit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return int(response.status), payload
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), payload


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def parse_published_csv(text: str, *, max_stale_minutes: int = 1440) -> dict[str, Any]:
    parsed = parse_google_sheets_csv(text, max_stale_minutes=max_stale_minutes)
    return {key: value for key, value in parsed.items() if key != "records"}


def run_audit(
    *,
    csv_url: str = "",
    timeout_seconds: int = 20,
    max_stale_minutes: int = 1440,
    request_fn: RequestFn = urllib_request_text,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    csv_url = _safe_text(csv_url)
    provider = ProviderResponse(
        provider_name="google_sheets_manual",
        status="WARN",
        source="GOOGLE_SHEETS_MANUAL_CSV",
        timestamp=generated_at,
        data_freshness="DELAYED_20_MIN",
        confidence="LOW",
        notes=["published CSV/manual source only; not execution quality"],
    ).to_dict()

    result: dict[str, Any] = {
        "status": "WARN",
        "generated_at": generated_at,
        "mode": "READ_ONLY",
        "provider": provider,
        "csv_url_present": bool(csv_url),
        "read_only": True,
        "execution_enabled": False,
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        "rows": 0,
        "valid_rows": 0,
        "header_row": None,
        "ignored_preamble_rows": 0,
        "stale_rows": 0,
        "schema": {},
        "issues": [],
    }

    if not csv_url:
        result["issues"].append("missing_google_sheets_csv_url")
        provider["errors"] = result["issues"]
        result["provider"] = provider
        return result

    try:
        http_status, text = request_fn(csv_url, timeout_seconds)
        result["http_status"] = int(http_status)
        if not (200 <= int(http_status) < 300):
            result["issues"].append("google_sheets_csv_unavailable")
            provider["errors"] = result["issues"]
            result["provider"] = provider
            return result
        parsed = parse_published_csv(text, max_stale_minutes=max_stale_minutes)
        result["status"] = str(parsed.get("status", "WARN"))
        result["rows"] = int(parsed.get("rows", 0) or 0)
        result["valid_rows"] = int(parsed.get("valid_rows", 0) or 0)
        result["header_row"] = parsed.get("header_row")
        result["ignored_preamble_rows"] = int(parsed.get("ignored_preamble_rows", 0) or 0)
        result["stale_rows"] = int(parsed.get("stale_rows", 0) or 0)
        result["schema"] = {
            "columns": parsed.get("columns", []),
            "detected_schema": parsed.get("detected_schema", []),
            "header_detected": bool(parsed.get("header_detected", False)),
            "missing_columns": parsed.get("missing_columns", []),
            "optional_columns_present": parsed.get("optional_columns_present", []),
        }
        result["sample_rows"] = parsed.get("sample_rows", [])
        result["issues"] = parsed.get("issues", [])
    except Exception as exc:
        result["issues"].append("google_sheets_request_or_parse_exception")
        result["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"

    provider["status"] = result["status"]
    provider["fields"] = {
        "rows": result.get("rows", 0),
        "valid_rows": result.get("valid_rows", 0),
        "header_row": result.get("header_row"),
        "ignored_preamble_rows": result.get("ignored_preamble_rows", 0),
        "stale_rows": result.get("stale_rows", 0),
    }
    provider["errors"] = result["issues"]
    result["provider"] = provider
    return result


def build_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Analista - Google Sheets data source audit",
        "",
        f"- status: {result.get('status', 'UNKNOWN')}",
        f"- mode: {result.get('mode', 'READ_ONLY')}",
        f"- generated_at: {result.get('generated_at', '')}",
        f"- csv_url_present: {result.get('csv_url_present', False)}",
        f"- rows: {result.get('rows', 0)}",
        f"- valid_rows: {result.get('valid_rows', 0)}",
        f"- header_row: {result.get('header_row', '')}",
        f"- ignored_preamble_rows: {result.get('ignored_preamble_rows', 0)}",
        f"- stale_rows: {result.get('stale_rows', 0)}",
        f"- read_only: {result.get('read_only', True)}",
        f"- execution_enabled: {result.get('execution_enabled', False)}",
        f"- notice: {result.get('no_real_order_notice', NO_REAL_ORDER_NOTICE)}",
        "",
        "## Schema",
        "",
    ]
    schema = result.get("schema", {}) or {}
    lines.append(f"- header_detected: {schema.get('header_detected', False)}")
    lines.append(f"- missing_columns: {', '.join(schema.get('missing_columns', []) or ['none'])}")
    lines.append(f"- optional_columns_present: {', '.join(schema.get('optional_columns_present', []) or ['none'])}")
    lines.extend(["", "## Issues", ""])
    issues = result.get("issues", []) or []
    lines.extend([f"- {issue}" for issue in issues] or ["- none"])
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Manual/published CSV source only.",
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
    config = load_config()
    sheets_cfg = (
        config.get("data_sources", {})
        .get("providers", {})
        .get("google_sheets_manual", {})
        or {}
    )
    configured_url = str(sheets_cfg.get("published_csv_url") or "")
    configured_max_stale = int(sheets_cfg.get("max_stale_minutes", 1440) or 1440)
    configured_timeout = int(sheets_cfg.get("timeout_seconds", 20) or 20)

    parser = argparse.ArgumentParser(description="Audita Google Sheets publicado como CSV manual read-only.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument(
        "--csv-url",
        default=os.environ.get("GOOGLE_SHEETS_ANALISTA_CSV_URL") or configured_url,
    )
    parser.add_argument("--timeout-seconds", type=int, default=configured_timeout)
    parser.add_argument(
        "--max-stale-minutes",
        type=int,
        default=int(os.environ.get("GOOGLE_SHEETS_MAX_STALE_MINUTES", configured_max_stale)),
    )
    args = parser.parse_args()

    result = run_audit(
        csv_url=args.csv_url,
        timeout_seconds=args.timeout_seconds,
        max_stale_minutes=args.max_stale_minutes,
    )
    save_reports(result, json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))

    print("=== ANALISTA GOOGLE SHEETS DATA SOURCE AUDIT ===")
    print(f"Status: {result.get('status')}")
    print(f"CSV URL present: {result.get('csv_url_present')}")
    print(f"Rows: {result.get('rows')}")
    print(f"Issues: {', '.join(result.get('issues', []) or ['none'])}")
    print(f"Notice: {NO_REAL_ORDER_NOTICE}")
    print(f"JSON: {Path(args.json_out)}")
    print(f"Markdown: {Path(args.markdown_out)}")
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
