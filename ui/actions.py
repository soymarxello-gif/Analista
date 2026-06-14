from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ui import guards
from tools.paper_trade_close import CLOSE_REASONS, save_paper_trade_close_reports
from tools.paper_trade_followup import save_paper_trade_followup_reports
from tools.paper_trading_journal import (
    MANUAL_DECISIONS,
    load_import_candidates,
    save_paper_trading_journal,
)


ROOT = Path(__file__).resolve().parents[1]
NO_REAL_ORDER_NOTICE = guards.NO_REAL_ORDER_NOTICE
ACTION_LOG_COLUMNS = [
    "action_id",
    "timestamp",
    "action_type",
    "user_visible_label",
    "ticker",
    "journal_id",
    "status",
    "message",
    "no_real_order_notice",
]
ALLOWED_MANUAL_DECISIONS = guards.ALLOWED_MANUAL_DECISIONS
ALLOWED_FOLLOWUP_STATUSES = {
    "OPEN_MONITORING",
    "NOT_ENTERED",
    "ENTERED_PAPER",
    "CLOSED_PAPER",
    "INVALIDATED",
    "EXPIRED",
}


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


def _clean_float(value: Any):
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except Exception:
        return None
    return out if out > 0 else None


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
    journal_id: str = "",
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
        "journal_id": _clean_identifier(journal_id),
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
    journal_id: str = "",
) -> dict[str, Any]:
    _log_action(
        root=root,
        action_type=action_type,
        label=label,
        ticker=ticker,
        journal_id=journal_id,
        status=result.status,
        message=result.message,
    )
    return result.to_dict()


def _load_journal(root: Path) -> pd.DataFrame:
    path = root / "data" / "paper_trading_journal.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def _resolve_ticker_run_date(
    root: Path,
    *,
    ticker: str = "",
    journal_id: str = "",
) -> tuple[str, str | None, str]:
    clean_ticker = _clean_symbol(ticker)
    clean_journal_id = _clean_identifier(journal_id)
    if clean_ticker:
        return clean_ticker, None, clean_journal_id
    if not clean_journal_id:
        return "", None, ""

    journal = _load_journal(root)
    if journal.empty or "journal_id" not in journal.columns:
        return "", None, clean_journal_id
    match = journal[journal["journal_id"].astype(str).eq(clean_journal_id)]
    if match.empty:
        return "", None, clean_journal_id
    row = match.iloc[-1].to_dict()
    return _clean_symbol(row.get("ticker")), _clean_text(row.get("run_date"), max_length=20) or None, clean_journal_id


def import_today_candidates(*, root: Path = ROOT, confirmed: bool = False) -> dict[str, Any]:
    if not confirmed:
        result = _result("FAIL", "confirmation_required")
        return _with_log(
            result,
            root=root,
            action_type="import_today_candidates",
            label="Import today candidates",
        )

    before = _load_journal(root)
    candidates, _source_report, _warning = load_import_candidates(
        cards_json=root / "reports" / "trade_candidate_cards_latest.json",
        checklist_csv=root / "reports" / "trade_decision_checklist_latest.csv",
        manual_top_csv=root / "reports" / "manual_review_top.csv",
        live_quote_csv=root / "reports" / "live_quote_recheck_latest.csv",
    )
    candidate_count = int(len(candidates)) if isinstance(candidates, pd.DataFrame) else 0
    try:
        payload = save_paper_trading_journal(root=root, import_today=True)
    except Exception as exc:
        result = _result("FAIL", f"import_failed:{exc}")
        return _with_log(
            result,
            root=root,
            action_type="import_today_candidates",
            label="Import today candidates",
        )

    inserted = int(payload.get("imported_rows", 0) or 0)
    after_rows = int(payload.get("rows", 0) or 0)
    before_rows = int(len(before))
    duplicate_rows = max(0, candidate_count - inserted)
    if candidate_count == 0 and after_rows >= before_rows:
        duplicate_rows = max(0, after_rows - before_rows - inserted)
    payload = dict(payload)
    payload["inserted_rows"] = inserted
    payload["duplicate_rows"] = duplicate_rows
    result = _result(payload.get("status", "PASS"), "import_completed", payload)
    return _with_log(
        result,
        root=root,
        action_type="import_today_candidates",
        label="Import today candidates",
    )


def set_paper_decision(
    *,
    root: Path = ROOT,
    ticker: str = "",
    journal_id: str = "",
    manual_decision: str,
    reason: str,
    entry=None,
    stop=None,
    target=None,
    confirmed: bool = False,
    confirm_live_quote: bool = True,
) -> dict[str, Any]:
    clean_decision = _clean_identifier(manual_decision).upper()
    clean_reason = _clean_text(reason, max_length=500)
    clean_ticker, run_date, clean_journal_id = _resolve_ticker_run_date(
        root,
        ticker=ticker,
        journal_id=journal_id,
    )

    if not confirmed:
        result = _result("FAIL", "confirmation_required")
    elif clean_decision not in ALLOWED_MANUAL_DECISIONS or clean_decision not in MANUAL_DECISIONS:
        result = _result("FAIL", "invalid_manual_decision")
    elif not clean_reason:
        result = _result("FAIL", "reason_required")
    elif not clean_ticker:
        result = _result("FAIL", "ticker_or_journal_id_required")
    elif clean_decision == "PAPER_ENTER" and (
        _clean_float(entry) is None or _clean_float(stop) is None or _clean_float(target) is None
    ):
        result = _result("FAIL", "paper_enter_requires_entry_stop_target")
    else:
        try:
            payload = save_paper_trading_journal(
                root=root,
                set_decision=(clean_ticker, clean_decision),
                run_date=run_date,
                reason=clean_reason,
                entry=_clean_float(entry),
                stop=_clean_float(stop),
                target=_clean_float(target),
                confirm_live_quote=confirm_live_quote,
            )
            result = _result(payload.get("status", "PASS"), payload.get("error") or "decision_updated", payload)
        except Exception as exc:
            result = _result("FAIL", f"decision_update_failed:{exc}")

    return _with_log(
        result,
        root=root,
        action_type="set_paper_decision",
        label="Set paper decision",
        ticker=clean_ticker,
        journal_id=clean_journal_id,
    )


def set_paper_followup(
    *,
    root: Path = ROOT,
    ticker: str = "",
    journal_id: str = "",
    followup_status: str,
    notes: str = "",
    confirmed: bool = False,
) -> dict[str, Any]:
    clean_status = _clean_identifier(followup_status).upper()
    clean_ticker, run_date, clean_journal_id = _resolve_ticker_run_date(
        root,
        ticker=ticker,
        journal_id=journal_id,
    )
    if not confirmed:
        result = _result("FAIL", "confirmation_required")
    elif clean_status not in ALLOWED_FOLLOWUP_STATUSES:
        result = _result("FAIL", "invalid_followup_status")
    elif not clean_ticker:
        result = _result("FAIL", "ticker_or_journal_id_required")
    else:
        try:
            payload = save_paper_trading_journal(
                root=root,
                set_followup=(clean_ticker, clean_status),
                run_date=run_date,
                notes=_clean_text(notes, max_length=500),
            )
            result = _result(payload.get("status", "PASS"), payload.get("error") or "followup_updated", payload)
        except Exception as exc:
            result = _result("FAIL", f"followup_update_failed:{exc}")

    return _with_log(
        result,
        root=root,
        action_type="set_paper_followup",
        label="Set paper follow-up",
        ticker=clean_ticker,
        journal_id=clean_journal_id,
    )


def refresh_paper_followup(*, root: Path = ROOT) -> dict[str, Any]:
    try:
        payload = save_paper_trade_followup_reports(root=root)
        result = _result(payload.get("status", "PASS"), payload.get("error") or "followup_report_refreshed", payload)
    except Exception as exc:
        result = _result("FAIL", f"followup_refresh_failed:{exc}")
    return _with_log(
        result,
        root=root,
        action_type="refresh_paper_followup",
        label="Refresh paper follow-up",
    )


def close_paper_trade(
    *,
    root: Path = ROOT,
    journal_id: str,
    exit_price,
    reason: str,
    exit_date: str | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    clean_journal_id = _clean_identifier(journal_id)
    clean_reason = _clean_identifier(reason).upper()
    price = _clean_float(exit_price)
    if not confirmed:
        result = _result("FAIL", "confirmation_required")
    elif not clean_journal_id:
        result = _result("FAIL", "journal_id_required")
    elif price is None:
        result = _result("FAIL", "exit_price_required")
    elif not clean_reason:
        result = _result("FAIL", "reason_required")
    elif clean_reason not in CLOSE_REASONS:
        result = _result("FAIL", "invalid_close_reason")
    else:
        try:
            payload = save_paper_trade_close_reports(
                root=root,
                close_identifier=clean_journal_id,
                exit_price=price,
                exit_date=_clean_text(exit_date, max_length=20) or None,
                reason=clean_reason,
            )
            result = _result(payload.get("status", "PASS"), payload.get("error") or "paper_trade_close_recorded", payload)
        except Exception as exc:
            result = _result("FAIL", f"paper_trade_close_failed:{exc}")

    return _with_log(
        result,
        root=root,
        action_type="close_paper_trade",
        label="Close paper trade",
        journal_id=clean_journal_id,
    )


def export_closed_paper_outcomes(*, root: Path = ROOT, confirmed: bool = False) -> dict[str, Any]:
    if not confirmed:
        result = _result("FAIL", "confirmation_required")
    else:
        try:
            payload = save_paper_trade_close_reports(root=root, export_outcomes=True)
            export_result = payload.get("export_result", {}) or {}
            payload = dict(payload)
            payload["exported_count"] = int(export_result.get("exported_outcomes", 0) or 0)
            payload["skipped_already_exported"] = int(export_result.get("skipped_already_exported", 0) or 0)
            result = _result(payload.get("status", "PASS"), payload.get("error") or "closed_paper_outcomes_exported", payload)
        except Exception as exc:
            result = _result("FAIL", f"outcome_export_failed:{exc}")
    return _with_log(
        result,
        root=root,
        action_type="export_closed_paper_outcomes",
        label="Export closed paper outcomes",
    )
