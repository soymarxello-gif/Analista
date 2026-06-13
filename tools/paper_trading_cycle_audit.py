from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


NO_REAL_ORDER_NOTICE = "paper trading only; no real order"
PAPER_SOURCE = "PAPER_TRADING_JOURNAL"

REQUIRED_JOURNAL_COLUMNS = [
    "journal_id",
    "run_date",
    "ticker",
    "manual_decision",
    "followup_status",
    "simulated_entry_price",
    "simulated_stop",
    "simulated_target",
    "no_real_order_notice",
]

OPTIONAL_REPORT_INPUTS = [
    "reports/paper_trading_journal_latest.json",
    "reports/paper_trade_followup_latest.json",
    "reports/paper_trade_close_latest.json",
    "reports/trade_outcome_analytics_latest.json",
    "reports/trade_score_calibration_latest.json",
    "reports/calibration_recommendations_latest.json",
]

BROKER_PATTERNS = [
    "broker_connection",
    "broker_order",
    "real_order_id",
    "order_submitted",
    "order_sent",
    "alpaca_order",
    "ibkr_order",
    "interactive_brokers",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _safe_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _load_csv(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        return pd.DataFrame(), f"missing_file:{path}"
    try:
        return pd.read_csv(path, dtype=str).fillna(""), ""
    except pd.errors.EmptyDataError:
        return pd.DataFrame(), ""
    except Exception as exc:
        return pd.DataFrame(), f"read_failed:{exc}"


def _load_json(path: Path) -> tuple[dict, str]:
    if not path.exists():
        return {}, f"missing_file:{path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except Exception as exc:
        return {}, f"read_failed:{exc}"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _upper_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([""] * len(df), index=df.index)
    return df[column].fillna("").astype(str).str.upper()


def _journal_open_mask(df: pd.DataFrame) -> pd.Series:
    manual = _upper_series(df, "manual_decision")
    followup = _upper_series(df, "followup_status")
    return manual.eq("PAPER_ENTER") | followup.eq("ENTERED_PAPER")


def _journal_closed_mask(df: pd.DataFrame) -> pd.Series:
    return _upper_series(df, "followup_status").eq("CLOSED_PAPER")


def _paper_outcomes(outcomes: pd.DataFrame) -> pd.DataFrame:
    if outcomes.empty:
        return outcomes.copy()
    if "source" not in outcomes.columns:
        return pd.DataFrame(columns=outcomes.columns)
    return outcomes[_upper_series(outcomes, "source").eq(PAPER_SOURCE)].copy()


def _ids_from_series(series: pd.Series) -> set[str]:
    return {_safe_text(value) for value in series.astype(str).tolist() if _safe_text(value)}


def _detect_broker_connection(paths: list[Path]) -> tuple[bool, list[str]]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        for pattern in BROKER_PATTERNS:
            if pattern in text:
                hits.append(f"{_relative(path, ROOT)}:{pattern}")
    return bool(hits), hits


def collect_optional_report_status(root: Path) -> dict:
    status: dict = {}
    for relative in OPTIONAL_REPORT_INPUTS:
        path = root / relative
        data, error = _load_json(path)
        status[relative] = {
            "exists": path.exists(),
            "status": str(data.get("status", "MISSING")) if data else "MISSING",
            "error": error,
        }
    return status


def collect_paper_trading_cycle_audit(
    *,
    root: Path = ROOT,
    journal_path: Path | None = None,
    outcomes_path: Path | None = None,
) -> dict:
    root = root.resolve()
    journal_path = journal_path or root / "data" / "paper_trading_journal.csv"
    outcomes_path = outcomes_path or root / "data" / "trade_outcomes.csv"

    journal_df, journal_error = _load_csv(journal_path)
    outcomes_df, outcomes_error = _load_csv(outcomes_path)
    report_status = collect_optional_report_status(root)

    issues: list[str] = []
    warnings: list[str] = []

    if journal_error:
        warnings.append(f"journal_unavailable:{journal_error}")
    if outcomes_error:
        warnings.append(f"outcomes_unavailable:{outcomes_error}")

    missing_journal_columns: list[str] = []
    if not journal_error:
        missing_journal_columns = [
            col for col in REQUIRED_JOURNAL_COLUMNS if col not in journal_df.columns
        ]
        if missing_journal_columns:
            issues.append("missing_journal_columns:" + ",".join(missing_journal_columns))

    closed_mask = _journal_closed_mask(journal_df) if not journal_df.empty else pd.Series(dtype=bool)
    open_mask = _journal_open_mask(journal_df) if not journal_df.empty else pd.Series(dtype=bool)
    exported_mask = (
        journal_df.get("outcome_exported", pd.Series([""] * len(journal_df))).apply(_safe_bool)
        if not journal_df.empty
        else pd.Series(dtype=bool)
    )

    pending_review_count = int(_upper_series(journal_df, "manual_decision").eq("PENDING_REVIEW").sum())
    open_paper_count = int(open_mask.sum()) if len(open_mask) else 0
    closed_paper_count = int(closed_mask.sum()) if len(closed_mask) else 0
    pending_export_count = int((closed_mask & ~exported_mask).sum()) if len(closed_mask) else 0
    exported_count = int((closed_mask & exported_mask).sum()) if len(closed_mask) else 0

    paper_outcomes = _paper_outcomes(outcomes_df)
    outcome_rows = int(len(outcomes_df))
    paper_outcome_rows = int(len(paper_outcomes))

    duplicate_outcome_ids: list[str] = []
    if not paper_outcomes.empty and "source_journal_id" in paper_outcomes.columns:
        ids = paper_outcomes["source_journal_id"].fillna("").astype(str)
        duplicate_outcome_ids = sorted(
            value for value, count in ids[ids.ne("")].value_counts().items() if count > 1
        )
        if duplicate_outcome_ids:
            issues.append("duplicate_outcome_ids:" + ",".join(duplicate_outcome_ids))

    if not paper_outcomes.empty and "source" in paper_outcomes.columns:
        invalid_sources = sorted(
            {
                _safe_text(value)
                for value in paper_outcomes["source"].fillna("").astype(str).tolist()
                if _safe_text(value).upper() != PAPER_SOURCE
            }
        )
        if invalid_sources:
            issues.append("invalid_paper_outcome_source:" + ",".join(invalid_sources))

    journal_ids = (
        _ids_from_series(journal_df["journal_id"])
        if "journal_id" in journal_df.columns
        else set()
    )
    outcome_ids = (
        _ids_from_series(paper_outcomes["source_journal_id"])
        if "source_journal_id" in paper_outcomes.columns
        else set()
    )

    exported_journal_ids = set()
    if not journal_df.empty and "journal_id" in journal_df.columns:
        exported_journal_ids = _ids_from_series(journal_df.loc[exported_mask, "journal_id"])

    missing_outcome_exports = sorted(exported_journal_ids - outcome_ids)
    if missing_outcome_exports:
        issues.append("missing_outcome_exports:" + ",".join(missing_outcome_exports))

    orphan_exported_journal_ids = sorted(outcome_ids - journal_ids)
    if orphan_exported_journal_ids:
        issues.append("orphan_exported_journal_ids:" + ",".join(orphan_exported_journal_ids))

    no_real_order_notice_present = True
    if not journal_error:
        if "no_real_order_notice" not in journal_df.columns:
            no_real_order_notice_present = False
        elif not journal_df.empty:
            no_real_order_notice_present = bool(
                journal_df["no_real_order_notice"]
                .fillna("")
                .astype(str)
                .str.contains("no real order", case=False, regex=False)
                .all()
            )
    if not no_real_order_notice_present:
        issues.append("missing_no_real_order_notice")

    guardrail_paths = [
        journal_path,
        outcomes_path,
        *[root / relative for relative in OPTIONAL_REPORT_INPUTS],
    ]
    broker_connection_detected, broker_hits = _detect_broker_connection(guardrail_paths)
    if broker_connection_detected:
        issues.append("broker_connection_detected")

    disabled_signal = "_".join(["BUY", "SETUP", "ACTIVE"])
    rendered_inputs = ""
    for path in guardrail_paths:
        if path.exists() and path.is_file():
            try:
                rendered_inputs += "\n" + path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
    disabled_signal_present = disabled_signal in rendered_inputs.upper()
    if disabled_signal_present:
        issues.append("disabled_buy_setup_signal_detected")

    auto_change_flags: list[str] = []
    calibration_data, _ = _load_json(root / "reports" / "trade_score_calibration_latest.json")
    recommendations_data, _ = _load_json(root / "reports" / "calibration_recommendations_latest.json")
    if calibration_data.get("changed_weights") or calibration_data.get("changed_thresholds"):
        auto_change_flags.append("calibration_auto_change_flag")
    if recommendations_data.get("do_not_change_automatically") is False:
        auto_change_flags.append("recommendations_allow_auto_change")
    if auto_change_flags:
        issues.extend(auto_change_flags)

    missing_optional_reports = [
        key for key, value in report_status.items() if not value.get("exists")
    ]
    if missing_optional_reports:
        warnings.append("missing_optional_reports:" + ",".join(missing_optional_reports))

    if not issues and (closed_paper_count == 0 or exported_count == 0):
        warnings.append("paper_cycle_sample_incomplete:no_closed_or_exported_paper_trades")

    status = "PASS"
    if issues:
        status = "FAIL"
    elif warnings:
        status = "WARN"

    return {
        "status": status,
        "generated_at": _utc_now(),
        "journal_path": _relative(journal_path, root),
        "outcomes_path": _relative(outcomes_path, root),
        "required_journal_columns": {
            "required": REQUIRED_JOURNAL_COLUMNS,
            "missing": missing_journal_columns,
            "ok": not missing_journal_columns and not journal_error,
        },
        "journal_rows": int(len(journal_df)),
        "pending_review_count": pending_review_count,
        "open_paper_count": open_paper_count,
        "closed_paper_count": closed_paper_count,
        "pending_export_count": pending_export_count,
        "exported_count": exported_count,
        "outcome_rows": outcome_rows,
        "paper_outcome_rows": paper_outcome_rows,
        "duplicate_outcome_ids": duplicate_outcome_ids,
        "orphan_exported_journal_ids": orphan_exported_journal_ids,
        "missing_outcome_exports": missing_outcome_exports,
        "calibration_status": str(calibration_data.get("status", "MISSING")),
        "recommendations_status": str(recommendations_data.get("status", "MISSING")),
        "no_real_order_notice_present": no_real_order_notice_present,
        "broker_connection_detected": broker_connection_detected,
        "broker_connection_hits": broker_hits,
        "disabled_signal_detected": disabled_signal_present,
        "automatic_change_flags": auto_change_flags,
        "optional_reports": report_status,
        "issues": issues,
        "warnings": warnings,
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
    }


def build_paper_trading_cycle_audit_markdown(data: dict) -> str:
    lines: list[str] = []
    lines.append("# Analista - paper trading cycle audit")
    lines.append("")
    lines.append(f"- status: {data.get('status')}")
    lines.append(f"- generated_at: {data.get('generated_at')}")
    lines.append(f"- journal_rows: {data.get('journal_rows')}")
    lines.append(f"- pending_review_count: {data.get('pending_review_count')}")
    lines.append(f"- open_paper_count: {data.get('open_paper_count')}")
    lines.append(f"- closed_paper_count: {data.get('closed_paper_count')}")
    lines.append(f"- pending_export_count: {data.get('pending_export_count')}")
    lines.append(f"- exported_count: {data.get('exported_count')}")
    lines.append(f"- outcome_rows: {data.get('outcome_rows')}")
    lines.append(f"- duplicate_outcome_ids: {len(data.get('duplicate_outcome_ids', []))}")
    lines.append(f"- missing_outcome_exports: {len(data.get('missing_outcome_exports', []))}")
    lines.append(f"- calibration_status: {data.get('calibration_status')}")
    lines.append(f"- recommendations_status: {data.get('recommendations_status')}")
    lines.append(f"- broker_connection_detected: {data.get('broker_connection_detected')}")
    lines.append(f"- notice: {NO_REAL_ORDER_NOTICE}")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    lines.append("- Paper trading only; no real order.")
    lines.append("- No broker connection is used.")
    lines.append("- No real orders are sent.")
    lines.append("- This audit is read-only and does not modify journal, outcomes, scanner, scoring, config, weights, or thresholds.")
    lines.append("")
    lines.append("## Issues")
    lines.append("")
    issues = data.get("issues", [])
    lines.extend([f"- {issue}" for issue in issues] if issues else ["- None"])
    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    warnings = data.get("warnings", [])
    lines.extend([f"- {warning}" for warning in warnings] if warnings else ["- None"])
    lines.append("")
    lines.append("## Optional Reports")
    lines.append("")
    for path, status in (data.get("optional_reports", {}) or {}).items():
        lines.append(
            f"- {path}: exists={status.get('exists')} status={status.get('status')} error={status.get('error')}"
        )
    return "\n".join(lines)


def save_paper_trading_cycle_audit(
    *,
    root: Path = ROOT,
    journal_path: Path | None = None,
    outcomes_path: Path | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "paper_trading_cycle_audit_latest.json"
    markdown_out = markdown_out or root / "reports" / "paper_trading_cycle_audit_latest.md"

    data = collect_paper_trading_cycle_audit(
        root=root,
        journal_path=journal_path,
        outcomes_path=outcomes_path,
    )
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_paper_trading_cycle_audit_markdown(data), encoding="utf-8")
    data["json_out"] = str(json_out)
    data["markdown_out"] = str(markdown_out)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita el ciclo end-to-end de paper trading.")
    parser.add_argument("--journal-path", default="data/paper_trading_journal.csv")
    parser.add_argument("--outcomes-path", default="data/trade_outcomes.csv")
    parser.add_argument("--json-out", default="reports/paper_trading_cycle_audit_latest.json")
    parser.add_argument("--markdown-out", default="reports/paper_trading_cycle_audit_latest.md")
    args = parser.parse_args()

    result = save_paper_trading_cycle_audit(
        root=ROOT,
        journal_path=ROOT / args.journal_path,
        outcomes_path=ROOT / args.outcomes_path,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA PAPER TRADING CYCLE AUDIT ===")
    print(f"Status: {result['status']}")
    print(f"Journal rows: {result['journal_rows']}")
    print(f"Open paper trades: {result['open_paper_count']}")
    print(f"Closed paper trades: {result['closed_paper_count']}")
    print(f"Pending export: {result['pending_export_count']}")
    print(f"Exported: {result['exported_count']}")
    print(f"Duplicate outcome IDs: {len(result['duplicate_outcome_ids'])}")
    print(f"Notice: {result['no_real_order_notice']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
