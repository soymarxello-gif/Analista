from __future__ import annotations

import math
from pathlib import Path
from typing import Any

NO_REAL_ORDER_NOTICE = "paper trading only; no real order"

ALLOWED_MANUAL_DECISIONS = {
    "PAPER_WATCH",
    "PAPER_ENTER",
    "SKIP",
    "BLOCKED",
    "NEEDS_LIVE_QUOTE_RECHECK",
}

ALLOWED_CLOSE_REASONS = {
    "TARGET_REACHED_MANUAL",
    "STOP_REACHED_MANUAL",
    "TECHNICAL_INVALIDATION",
    "TIME_EXIT",
    "MANUAL_RISK_REDUCTION",
    "DATA_QUALITY_EXIT",
    "OTHER",
}

FORBIDDEN_TERMS = {
    "send_order",
    "place_order",
    "buy_order",
    "sell_order",
    "broker",
    "ibapi",
    "alpaca",
    "interactivebrokers",
    "robinhood",
    "real_order",
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "none", "nan", "null"} else text


def _positive_number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
    except Exception:
        return None
    if math.isnan(number) or number <= 0:
        return None
    return number


def _result(ok: bool, errors: list[str]) -> dict:
    return {
        "ok": bool(ok),
        "errors": errors,
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
    }


def validate_paper_action_confirmation(confirmed: bool) -> dict:
    errors = [] if confirmed else ["confirmation_required"]
    return _result(not errors, errors)


def validate_paper_enter_payload(
    *,
    manual_decision: Any,
    entry: Any = None,
    stop: Any = None,
    target: Any = None,
    confirmed: bool = False,
) -> dict:
    errors: list[str] = []
    decision = _clean_text(manual_decision).upper()
    if not confirmed:
        errors.append("confirmation_required")
    if decision not in ALLOWED_MANUAL_DECISIONS:
        errors.append("invalid_manual_decision")
    if decision == "PAPER_ENTER":
        if _positive_number(entry) is None:
            errors.append("entry_required")
        if _positive_number(stop) is None:
            errors.append("stop_required")
        if _positive_number(target) is None:
            errors.append("target_required")
    return _result(not errors, errors)


def validate_close_payload(
    *,
    journal_id: Any,
    exit_price: Any,
    reason: Any,
    confirmed: bool = False,
) -> dict:
    errors: list[str] = []
    clean_reason = _clean_text(reason).upper()
    if not confirmed:
        errors.append("confirmation_required")
    if not _clean_text(journal_id):
        errors.append("journal_id_required")
    if _positive_number(exit_price) is None:
        errors.append("exit_price_required")
    if not clean_reason:
        errors.append("reason_required")
    elif clean_reason not in ALLOWED_CLOSE_REASONS:
        errors.append("invalid_close_reason")
    return _result(not errors, errors)


def validate_export_confirmation(confirmed: bool) -> dict:
    errors = [] if confirmed else ["confirmation_required"]
    return _result(not errors, errors)


def scan_file_for_forbidden_terms(path: Path | str) -> dict:
    target = Path(path)
    if not target.exists():
        return {"ok": False, "path": str(target), "hits": [], "error": "file_missing"}
    try:
        text = target.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception as exc:
        return {"ok": False, "path": str(target), "hits": [], "error": str(exc)}
    hits = sorted(term for term in FORBIDDEN_TERMS if term.lower() in text)
    return {"ok": not hits, "path": str(target), "hits": hits, "error": ""}
