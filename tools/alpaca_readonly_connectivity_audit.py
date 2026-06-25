from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_JSON_OUT = ROOT / "reports" / "alpaca_readonly_connectivity_latest.json"
DEFAULT_MARKDOWN_OUT = ROOT / "reports" / "alpaca_readonly_connectivity_latest.md"
DEFAULT_TRADING_BASE_URL = "https://paper-api.alpaca.markets"
DEFAULT_DATA_BASE_URL = "https://data.alpaca.markets"
DEFAULT_SYMBOL = "AAPL"
NO_REAL_ORDER_NOTICE = "read-only connectivity audit; no real order"

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


def load_credentials() -> dict[str, str]:
    key, key_env = _env_first(["APCA_API_KEY_ID", "ALPACA_API_KEY_ID"])
    secret, secret_env = _env_first(["APCA_API_SECRET_KEY", "ALPACA_API_SECRET_KEY"])
    return {
        "key": key,
        "secret": secret,
        "key_env": key_env,
        "secret_env": secret_env,
        "key_masked": _mask(key),
        "secret_present": bool(secret),
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


def _endpoint_result(name: str, url: str, headers: dict[str, str], timeout_seconds: int, request_fn: RequestFn) -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        http_status, data = request_fn(url, headers, timeout_seconds)
    except Exception as exc:
        return {
            "name": name,
            "status": "WARN",
            "http_status": 0,
            "ok": False,
            "url": _sanitize_url(url),
            "checked_at": started_at,
            "error": type(exc).__name__,
            "message": str(exc)[:500],
            "data": {},
        }

    ok = 200 <= int(http_status) < 300
    return {
        "name": name,
        "status": "PASS" if ok else "WARN",
        "http_status": int(http_status),
        "ok": ok,
        "url": _sanitize_url(url),
        "checked_at": started_at,
        "error": "" if ok else str(data.get("code", "")),
        "message": "" if ok else str(data.get("message", data))[:500],
        "data": data if isinstance(data, dict) else {},
    }


def _sanitize_url(url: str) -> str:
    return url.replace("APCA-API-KEY-ID", "REDACTED").replace("APCA-API-SECRET-KEY", "REDACTED")


def _headers(credentials: dict[str, str]) -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": credentials["key"],
        "APCA-API-SECRET-KEY": credentials["secret"],
        "Accept": "application/json",
        "User-Agent": "Analista-readonly-connectivity-audit/1.0",
    }


def _summarize_account(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_present": bool(_safe_text(data.get("id"))),
        "account_number_masked": _mask(str(data.get("account_number", "")), keep=4),
        "status": _safe_text(data.get("status")),
        "currency": _safe_text(data.get("currency")),
        "trading_blocked": bool(data.get("trading_blocked", False)),
        "account_blocked": bool(data.get("account_blocked", False)),
        "transfers_blocked": bool(data.get("transfers_blocked", False)),
        "pattern_day_trader": bool(data.get("pattern_day_trader", False)),
        "portfolio_value_present": bool(_safe_text(data.get("portfolio_value"))),
    }


def _summarize_clock(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": _safe_text(data.get("timestamp")),
        "is_open": bool(data.get("is_open", False)),
        "next_open": _safe_text(data.get("next_open")),
        "next_close": _safe_text(data.get("next_close")),
    }


def _summarize_quote(data: dict[str, Any], symbol: str = DEFAULT_SYMBOL) -> dict[str, Any]:
    quote = data.get("quote", {}) if isinstance(data, dict) else {}
    return {
        "symbol": _safe_text(data.get("symbol") or quote.get("S") or symbol or DEFAULT_SYMBOL),
        "feed": "iex",
        "bid_price_present": bool(_safe_text(quote.get("bp") or quote.get("bid_price"))),
        "ask_price_present": bool(_safe_text(quote.get("ap") or quote.get("ask_price"))),
        "timestamp": _safe_text(quote.get("t") or quote.get("timestamp")),
    }


def run_audit(
    *,
    trading_base_url: str = DEFAULT_TRADING_BASE_URL,
    data_base_url: str = DEFAULT_DATA_BASE_URL,
    symbol: str = DEFAULT_SYMBOL,
    timeout_seconds: int = 15,
    request_fn: RequestFn = urllib_request_json,
) -> dict:
    credentials = load_credentials()
    generated_at = datetime.now(timezone.utc).isoformat()
    symbol = _safe_text(symbol).upper() or DEFAULT_SYMBOL

    result: dict[str, Any] = {
        "status": "WARN",
        "generated_at": generated_at,
        "mode": "READ_ONLY",
        "trading_base_url": trading_base_url.rstrip("/"),
        "data_base_url": data_base_url.rstrip("/"),
        "symbol": symbol,
        "credentials_present": bool(credentials["key"] and credentials["secret"]),
        "key_env": credentials["key_env"],
        "secret_env": credentials["secret_env"],
        "key_masked": credentials["key_masked"],
        "secret_present": credentials["secret_present"],
        "account_check": {},
        "clock_check": {},
        "iex_quote_check": {},
        "account_summary": {},
        "clock_summary": {},
        "iex_quote_summary": {},
        "orders_endpoint_called": False,
        "execution_enabled": False,
        "read_only": True,
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        "issues": [],
    }

    if not result["credentials_present"]:
        result["issues"].append("missing_alpaca_credentials")
        return result

    headers = _headers(credentials)
    trading_base = trading_base_url.rstrip("/")
    data_base = data_base_url.rstrip("/")
    quote_symbol = urllib.parse.quote(symbol, safe="")

    account = _endpoint_result("account", f"{trading_base}/v2/account", headers, timeout_seconds, request_fn)
    clock = _endpoint_result("clock", f"{trading_base}/v2/clock", headers, timeout_seconds, request_fn)
    quote = _endpoint_result(
        "iex_latest_quote",
        f"{data_base}/v2/stocks/{quote_symbol}/quotes/latest?feed=iex",
        headers,
        timeout_seconds,
        request_fn,
    )

    result["account_check"] = {k: v for k, v in account.items() if k != "data"}
    result["clock_check"] = {k: v for k, v in clock.items() if k != "data"}
    result["iex_quote_check"] = {k: v for k, v in quote.items() if k != "data"}
    result["account_summary"] = _summarize_account(account.get("data", {}))
    result["clock_summary"] = _summarize_clock(clock.get("data", {}))
    result["iex_quote_summary"] = _summarize_quote(quote.get("data", {}), symbol=symbol)

    if not account["ok"]:
        result["issues"].append("account_check_failed")
    if not clock["ok"]:
        result["issues"].append("clock_check_failed")
    if not quote["ok"]:
        result["issues"].append("iex_quote_check_failed")

    result["status"] = "PASS" if not result["issues"] else "WARN"
    return result


def build_markdown(result: dict) -> str:
    lines = [
        "# Analista - Alpaca read-only connectivity audit",
        "",
        f"- status: {result.get('status', 'UNKNOWN')}",
        f"- mode: {result.get('mode', 'READ_ONLY')}",
        f"- generated_at: {result.get('generated_at', '')}",
        f"- credentials_present: {result.get('credentials_present', False)}",
        f"- key_env: {result.get('key_env', '')}",
        f"- secret_env: {result.get('secret_env', '')}",
        f"- key_masked: {result.get('key_masked', '')}",
        f"- symbol: {result.get('symbol', '')}",
        f"- read_only: {result.get('read_only', True)}",
        f"- execution_enabled: {result.get('execution_enabled', False)}",
        f"- orders_endpoint_called: {result.get('orders_endpoint_called', False)}",
        f"- notice: {result.get('no_real_order_notice', NO_REAL_ORDER_NOTICE)}",
        "",
        "## Endpoint checks",
        "",
    ]
    for key in ["account_check", "clock_check", "iex_quote_check"]:
        check = result.get(key, {}) or {}
        lines.append(f"- {key}: {check.get('status', 'MISSING')} http={check.get('http_status', 0)}")

    lines.extend(["", "## Account summary", ""])
    for key, value in (result.get("account_summary", {}) or {}).items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Clock summary", ""])
    for key, value in (result.get("clock_summary", {}) or {}).items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## IEX quote summary", ""])
    for key, value in (result.get("iex_quote_summary", {}) or {}).items():
        lines.append(f"- {key}: {value}")

    issues = result.get("issues", []) or []
    lines.extend(["", "## Issues", ""])
    if issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Read-only account, clock, and IEX market data checks only.",
            "- No scanner, scoring, threshold, signal, journal, outcome, or config changes.",
            "- No real order.",
        ]
    )
    return "\n".join(lines)


def save_reports(result: dict, *, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(result), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita conectividad Alpaca read-only sin ejecución.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--trading-base-url", default=DEFAULT_TRADING_BASE_URL)
    parser.add_argument("--data-base-url", default=DEFAULT_DATA_BASE_URL)
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--timeout-seconds", type=int, default=15)
    args = parser.parse_args()

    result = run_audit(
        trading_base_url=args.trading_base_url,
        data_base_url=args.data_base_url,
        symbol=args.symbol,
        timeout_seconds=args.timeout_seconds,
    )
    save_reports(result, json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))

    print("=== ANALISTA ALPACA READ-ONLY CONNECTIVITY AUDIT ===")
    print(f"Status: {result.get('status')}")
    print(f"Credentials present: {result.get('credentials_present')}")
    print(f"Account: {(result.get('account_check') or {}).get('status', 'MISSING')}")
    print(f"Clock: {(result.get('clock_check') or {}).get('status', 'MISSING')}")
    print(f"IEX quote: {(result.get('iex_quote_check') or {}).get('status', 'MISSING')}")
    print(f"Notice: {NO_REAL_ORDER_NOTICE}")
    print(f"JSON: {Path(args.json_out)}")
    print(f"Markdown: {Path(args.markdown_out)}")
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
