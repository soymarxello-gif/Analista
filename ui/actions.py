from __future__ import annotations

import csv
import inspect
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.single_ticker_deep_dive import clean_ticker, save_single_ticker_deep_dive_reports
from tools.daily_validation import run_daily_validation
from config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]
NO_REAL_ORDER_NOTICE = "manual review only; no real order"
ACTION_LOG_COLUMNS = [
    "action_id",
    "timestamp",
    "action_type",
    "user_visible_label",
    "ticker",
    "context_id",
    "status",
    "message",
    "no_real_order_notice",
]


@dataclass(frozen=True)
class ActionResult:
    status: str
    message: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "payload": self.payload,
            "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any, *, max_length: int = 240) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    allowed = []
    for char in text[:max_length]:
        if char.isalnum() or char in " .,_:-/@#()[]":
            allowed.append(char)
    return "".join(allowed).strip()


def _clean_symbol(value: Any) -> str:
    text = _clean_text(value, max_length=32).upper()
    return "".join(char for char in text if char.isalnum() or char in ".-_")


def _clean_identifier(value: Any) -> str:
    text = _clean_text(value, max_length=80)
    return "".join(char for char in text if char.isalnum() or char in ".-_")


def _result(status: str, message: str, payload: dict[str, Any] | None = None) -> ActionResult:
    return ActionResult(
        status=str(status or "UNKNOWN").upper(),
        message=_clean_text(message, max_length=500),
        payload=payload or {},
    )


def _log_action(
    *,
    root: Path,
    action_type: str,
    label: str,
    ticker: str = "",
    context_id: str = "",
    status: str,
    message: str,
) -> None:
    path = root / "data" / "ui_action_log.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    row = {
        "action_id": uuid.uuid4().hex,
        "timestamp": _utc_now(),
        "action_type": _clean_identifier(action_type),
        "user_visible_label": _clean_text(label, max_length=120),
        "ticker": _clean_symbol(ticker),
        "context_id": _clean_identifier(context_id),
        "status": _clean_text(status, max_length=40).upper(),
        "message": _clean_text(message, max_length=500),
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
    }
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ACTION_LOG_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _with_log(
    result: ActionResult,
    *,
    root: Path,
    action_type: str,
    label: str,
    ticker: str = "",
    context_id: str = "",
) -> dict[str, Any]:
    _log_action(
        root=root,
        action_type=action_type,
        label=label,
        ticker=ticker,
        context_id=context_id,
        status=result.status,
        message=result.message,
    )
    return result.to_dict()


def _parse_summary_status(summary_out: Path) -> str:
    if not summary_out.exists():
        return "UNKNOWN"
    try:
        text = summary_out.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return "UNKNOWN"
    for line in text.splitlines()[:20]:
        clean = line.strip()
        if clean.lower().startswith("status:"):
            return _clean_identifier(clean.split(":", 1)[1]).upper() or "UNKNOWN"
    return "UNKNOWN"


def run_single_ticker_deep_dive(
    *,
    root: Path = ROOT,
    ticker: str,
    confirmed: bool = True,
) -> dict[str, Any]:
    clean = clean_ticker(ticker)
    if not confirmed:
        result = _result("FAIL", "confirmation_required")
    elif not clean:
        result = _result("FAIL", "ticker_required")
    else:
        try:
            payload = save_single_ticker_deep_dive_reports(
                clean,
                config=load_config(str(root / "config.yaml")),
                json_out=root / "reports" / "single_ticker_deep_dive_latest.json",
                markdown_out=root / "reports" / "single_ticker_deep_dive_latest.md",
            )
            result = _result(
                payload.get("status", "UNKNOWN"),
                "single_ticker_deep_dive_completed",
                {
                    "ticker": payload.get("ticker", clean),
                    "decision": payload.get("row", {}).get("manual_deep_dive_decision", ""),
                    "scenario_status": payload.get("row", {}).get("scenario_status", ""),
                    "final_trade_score": payload.get("row", {}).get("final_trade_score", ""),
                    "quote_status": payload.get("row", {}).get("quote_status", ""),
                    "execution_quote_quality": payload.get("row", {}).get("execution_quote_quality", ""),
                    "json_out": payload.get("json_out", ""),
                    "markdown_out": payload.get("markdown_out", ""),
                    "manual_review_only": True,
                    "creates_trading_signal": False,
                    "row": payload.get("row", {}),
                },
            )
        except Exception as exc:
            result = _result("FAIL", f"single_ticker_deep_dive_failed:{exc}")
    return _with_log(
        result,
        root=root,
        action_type="single_ticker_deep_dive",
        label="Single ticker deep dive",
        ticker=clean,
    )


def refresh_all_data(*, root: Path = ROOT, confirmed: bool = True) -> dict[str, Any]:
    if not confirmed:
        result = _result("FAIL", "confirmation_required")
        return _with_log(
            result,
            root=root,
            action_type="refresh_all_data",
            label="Refresh all data",
        )

    started = time.perf_counter()
    summary_out = root / "reports" / "daily_validation_summary.txt"
    try:
        validation_kwargs = {}
        if "scanner_timeout_seconds" in inspect.signature(run_daily_validation).parameters:
            validation_kwargs["scanner_timeout_seconds"] = 420
        exit_code = run_daily_validation(summary_out, **validation_kwargs)
        duration = round(time.perf_counter() - started, 2)
        summary_status = _parse_summary_status(summary_out)
        status = summary_status if exit_code == 0 and summary_status in {"PASS", "WARN"} else "FAIL"
        payload = {
            "exit_code": exit_code,
            "summary_status": summary_status,
            "duration_seconds": duration,
            "scanner_timeout_seconds": 420,
            "summary_out": str(summary_out),
            "reports_refreshed": True,
            "manual_review_only": True,
            "creates_trading_signal": False,
        }
        result = _result(status, "daily_validation_completed", payload)
    except Exception as exc:
        duration = round(time.perf_counter() - started, 2)
        result = _result(
            "FAIL",
            f"daily_validation_failed:{exc}",
            {
                "duration_seconds": duration,
                "scanner_timeout_seconds": 420,
                "summary_out": str(summary_out),
                "reports_refreshed": False,
                "manual_review_only": True,
                "creates_trading_signal": False,
            },
        )

    return _with_log(
        result,
        root=root,
        action_type="refresh_all_data",
        label="Refresh all data",
    )
