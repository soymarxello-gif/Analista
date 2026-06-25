from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.data_sources.provider_contract import ProviderResponse

DEFAULT_JSON_OUT = ROOT / "reports" / "webull_readonly_market_data_latest.json"
DEFAULT_MARKDOWN_OUT = ROOT / "reports" / "webull_readonly_market_data_latest.md"
DEFAULT_BASE_URL = "https://api.webull.com"
DEFAULT_SYMBOL = "AAPL"
NO_REAL_ORDER_NOTICE = "read-only market data audit; no real order"

RequestFn = Callable[[str, dict[str, str], int], tuple[int, dict[str, Any]]]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def _mask(value: str, keep: int = 4) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    if len(text) <= keep:
        return "*" * len(text)
    return f"{'*' * max(len(text) - keep, 4)}{text[-keep:]}"


def _env_first(names: list[str]) -> tuple[str, str]:
    for name in names:
        value = _safe_text(os.environ.get(name))
        if value:
            return value, name
    return "", ""


def load_credentials() -> dict[str, Any]:
    app_key, app_key_env = _env_first(["WEBULL_APP_KEY", "WEBULL_API_KEY"])
    app_secret, app_secret_env = _env_first(["WEBULL_APP_SECRET", "WEBULL_API_SECRET"])
    return {
        "app_key": app_key,
        "app_secret": app_secret,
        "app_key_env": app_key_env,
        "app_secret_env": app_secret_env,
        "app_key_masked": _mask(app_key),
        "app_secret_present": bool(app_secret),
    }


def _signature(secret: str, method: str, path_query: str, timestamp: str, nonce: str) -> str:
    message = "\n".join([method.upper(), path_query, timestamp, nonce])
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha1).hexdigest()


def _headers(credentials: dict[str, Any], *, method: str, path_query: str) -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    nonce = hashlib.sha256(f"{timestamp}:{path_query}".encode("utf-8")).hexdigest()[:24]
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Analista-webull-readonly-market-data-audit/1.0",
        "x-app-key": str(credentials.get("app_key", "")),
        "x-timestamp": timestamp,
        "x-signature-version": "1.0",
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce": nonce,
        "x-signature": _signature(str(credentials.get("app_secret", "")), method, path_query, timestamp, nonce),
    }


def urllib_request_json(url: str, headers: dict[str, str], timeout_seconds: int) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return int(response.status), json.loads(payload or "{}")
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(payload or "{}")
        except Exception:
            data = {"message": payload[:500]}
        return int(exc.code), data


def _classify_http_status(http_status: int) -> tuple[str, str]:
    if 200 <= int(http_status) < 300:
        return "PASS", ""
    if int(http_status) == 401:
        return "WARN", "webull_credentials_invalid_or_signature_rejected"
    if int(http_status) == 403:
        return "WARN", "webull_market_data_entitlement_missing"
    if int(http_status) in {408, 429, 500, 502, 503, 504}:
        return "WARN", "webull_transient_or_rate_limited"
    return "FAIL", "webull_endpoint_unavailable"


def _endpoint_result(
    name: str,
    base_url: str,
    path_query: str,
    credentials: dict[str, Any],
    timeout_seconds: int,
    request_fn: RequestFn,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    url = f"{base_url.rstrip('/')}{path_query}"
    headers = _headers(credentials, method="GET", path_query=path_query)
    try:
        http_status, data = request_fn(url, headers, timeout_seconds)
        status, issue = _classify_http_status(int(http_status))
        return {
            "name": name,
            "status": status,
            "http_status": int(http_status),
            "ok": status == "PASS",
            "checked_at": started_at,
            "issue": issue,
            "message": "" if status == "PASS" else str(data.get("message", data))[:500],
            "data_keys": sorted(list(data.keys()))[:25] if isinstance(data, dict) else [],
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "WARN",
            "http_status": 0,
            "ok": False,
            "checked_at": started_at,
            "issue": "webull_request_exception",
            "message": f"{type(exc).__name__}: {str(exc)[:500]}",
            "data_keys": [],
        }


def run_audit(
    *,
    base_url: str = DEFAULT_BASE_URL,
    symbol: str = DEFAULT_SYMBOL,
    timeout_seconds: int = 15,
    request_fn: RequestFn = urllib_request_json,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    credentials = load_credentials()
    symbol = _safe_text(symbol).upper() or DEFAULT_SYMBOL
    quote_symbol = urllib.parse.quote(symbol, safe="")

    provider = ProviderResponse(
        provider_name="webull",
        status="WARN",
        source="WEBULL_OPENAPI",
        timestamp=generated_at,
        data_freshness="UNKNOWN",
        confidence="UNKNOWN",
        notes=["quotes/bars audit only; no execution endpoints"],
    ).to_dict()

    result: dict[str, Any] = {
        "status": "WARN",
        "generated_at": generated_at,
        "mode": "READ_ONLY",
        "provider": provider,
        "base_url": base_url.rstrip("/"),
        "symbol": symbol,
        "credentials_present": bool(credentials["app_key"] and credentials["app_secret"]),
        "app_key_env": credentials["app_key_env"],
        "app_secret_env": credentials["app_secret_env"],
        "app_key_masked": credentials["app_key_masked"],
        "app_secret_present": credentials["app_secret_present"],
        "read_only": True,
        "execution_enabled": False,
        "execution_endpoint_called": False,
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        "endpoint_checks": [],
        "issues": [],
    }

    if not result["credentials_present"]:
        result["issues"].append("missing_webull_credentials")
        provider["errors"] = result["issues"]
        result["provider"] = provider
        return result

    endpoints = [
        (
            "stock_snapshot",
            f"/openapi/market-data/stock/snapshot?symbols={quote_symbol}&category=US_STOCK&extend_hour_required=false&overnight_required=false",
        ),
        (
            "stock_quote",
            f"/openapi/market-data/stock/quotes?symbol={quote_symbol}&category=US_STOCK&depth=1&overnight_required=false",
        ),
        (
            "daily_bars",
            f"/openapi/market-data/stock/bars?symbol={quote_symbol}&category=US_STOCK&timespan=D&count=5",
        ),
    ]

    checks = [
        _endpoint_result(name, base_url, path_query, credentials, timeout_seconds, request_fn)
        for name, path_query in endpoints
    ]
    result["endpoint_checks"] = checks
    result["issues"] = sorted({check["issue"] for check in checks if check.get("issue")})

    if all(check.get("status") == "PASS" for check in checks):
        result["status"] = "PASS"
        provider["status"] = "PASS"
        provider["confidence"] = "MEDIUM"
    elif any(check.get("status") == "FAIL" for check in checks):
        result["status"] = "FAIL"
        provider["status"] = "FAIL"
        provider["confidence"] = "LOW"
    else:
        result["status"] = "WARN"
        provider["status"] = "WARN"
        provider["confidence"] = "LOW"
    provider["errors"] = result["issues"]
    result["provider"] = provider
    return result


def build_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Analista - Webull read-only market data audit",
        "",
        f"- status: {result.get('status', 'UNKNOWN')}",
        f"- mode: {result.get('mode', 'READ_ONLY')}",
        f"- generated_at: {result.get('generated_at', '')}",
        f"- symbol: {result.get('symbol', '')}",
        f"- credentials_present: {result.get('credentials_present', False)}",
        f"- app_key_env: {result.get('app_key_env', '')}",
        f"- app_secret_env: {result.get('app_secret_env', '')}",
        f"- app_key_masked: {result.get('app_key_masked', '')}",
        f"- read_only: {result.get('read_only', True)}",
        f"- execution_enabled: {result.get('execution_enabled', False)}",
        f"- execution_endpoint_called: {result.get('execution_endpoint_called', False)}",
        f"- notice: {result.get('no_real_order_notice', NO_REAL_ORDER_NOTICE)}",
        "",
        "## Endpoint checks",
        "",
    ]
    for check in result.get("endpoint_checks", []) or []:
        lines.append(
            f"- {check.get('name', '')}: {check.get('status', 'MISSING')} "
            f"http={check.get('http_status', 0)} issue={check.get('issue', '')}"
        )
    if not result.get("endpoint_checks"):
        lines.append("- none")

    lines.extend(["", "## Issues", ""])
    issues = result.get("issues", []) or []
    lines.extend([f"- {issue}" for issue in issues] or ["- none"])

    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Read-only market data checks only.",
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
    parser = argparse.ArgumentParser(description="Audita Webull OpenAPI read-only para datos de mercado.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--base-url", default=os.environ.get("WEBULL_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--symbol", default=os.environ.get("WEBULL_TEST_SYMBOL", DEFAULT_SYMBOL))
    parser.add_argument("--timeout-seconds", type=int, default=15)
    args = parser.parse_args()

    result = run_audit(
        base_url=args.base_url,
        symbol=args.symbol,
        timeout_seconds=args.timeout_seconds,
    )
    save_reports(result, json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))

    print("=== ANALISTA WEBULL READ-ONLY MARKET DATA AUDIT ===")
    print(f"Status: {result.get('status')}")
    print(f"Credentials present: {result.get('credentials_present')}")
    print(f"Issues: {', '.join(result.get('issues', []) or ['none'])}")
    print(f"Notice: {NO_REAL_ORDER_NOTICE}")
    print(f"JSON: {Path(args.json_out)}")
    print(f"Markdown: {Path(args.markdown_out)}")
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
