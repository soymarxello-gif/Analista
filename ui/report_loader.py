from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


SOURCE_SPECS = {
    "daily_operator_index": ("markdown", "reports/daily_operator_index.md"),
    "daily_run_manifest": ("json", "reports/daily_run_manifest_latest.json"),
    "daily_quality_gate": ("json", "reports/daily_quality_gate_latest.json"),
    "release_readiness": ("json", "reports/release_readiness_latest.json"),
    "ui_data_contract": ("json", "reports/ui_data_contract_audit_latest.json"),
    "streamlit_smoke_test": ("json", "reports/streamlit_smoke_test_latest.json"),
    "gui_actions_audit": ("json", "reports/gui_actions_audit_latest.json"),
    "gui_visuals_audit": ("json", "reports/gui_visuals_audit_latest.json"),
    "manual_review_top": ("csv", "reports/manual_review_top.csv"),
    "manual_review_latest": ("csv", "reports/manual_review_latest.csv"),
    "trade_candidate_cards": ("json", "reports/trade_candidate_cards_latest.json"),
    "trade_decision_checklist": ("csv", "reports/trade_decision_checklist_latest.csv"),
    "live_quote_recheck": ("csv", "reports/live_quote_recheck_latest.csv"),
    "paper_trading_journal": ("csv", "reports/paper_trading_journal_latest.csv"),
    "paper_trade_followup": ("csv", "reports/paper_trade_followup_latest.csv"),
    "paper_trade_close": ("csv", "reports/paper_trade_close_latest.csv"),
    "paper_trading_cycle_audit": ("json", "reports/paper_trading_cycle_audit_latest.json"),
    "trade_outcome_analytics": ("csv", "reports/trade_outcome_analytics_latest.csv"),
    "trade_score_calibration": ("json", "reports/trade_score_calibration_latest.json"),
    "calibration_recommendations": ("json", "reports/calibration_recommendations_latest.json"),
}

VALID_SOURCE_STATUSES = {"AVAILABLE", "MISSING", "INVALID", "EMPTY"}


def _relative(path: Path, root: Path | None = None) -> str:
    if root is None:
        return str(path)
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _empty_dataframe(status: str, path: Path, error: str = "") -> pd.DataFrame:
    df = pd.DataFrame()
    df.attrs["status"] = status
    df.attrs["path"] = str(path)
    df.attrs["error"] = error
    return df


def file_status(path: Path) -> dict:
    try:
        exists = path.exists()
        return {
            "path": str(path),
            "exists": exists,
            "status": "AVAILABLE" if exists else "MISSING",
            "size_bytes": path.stat().st_size if exists else 0,
            "modified": path.stat().st_mtime if exists else None,
            "error": "",
        }
    except Exception as exc:
        return {
            "path": str(path),
            "exists": False,
            "status": "INVALID",
            "size_bytes": 0,
            "modified": None,
            "error": str(exc),
        }


def load_json_report(path: Path) -> dict:
    status = file_status(path)
    if not status["exists"]:
        return {**status, "status": "MISSING", "data": {}}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return {**status, "status": "EMPTY", "data": {}}
        data = json.loads(text)
        if not isinstance(data, dict):
            data = {"value": data}
        return {**status, "status": "AVAILABLE", "data": data}
    except Exception as exc:
        return {**status, "status": "INVALID", "data": {}, "error": str(exc)}


def load_csv_report(path: Path) -> pd.DataFrame:
    status = file_status(path)
    if not status["exists"]:
        return _empty_dataframe("MISSING", path)
    try:
        df = pd.read_csv(path, dtype=str, encoding="utf-8", encoding_errors="replace")
    except pd.errors.EmptyDataError:
        return _empty_dataframe("EMPTY", path)
    except Exception as exc:
        return _empty_dataframe("INVALID", path, str(exc))

    df = df.fillna("")
    df.attrs["status"] = "EMPTY" if df.empty else "AVAILABLE"
    df.attrs["path"] = str(path)
    df.attrs["error"] = ""
    return df


def load_markdown_report(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _source_from_json(name: str, path: Path, root: Path) -> dict:
    loaded = load_json_report(path)
    data = loaded.get("data", {})
    return {
        "name": name,
        "kind": "json",
        "path": _relative(path, root),
        "exists": bool(loaded.get("exists", False)),
        "status": loaded.get("status", "UNKNOWN"),
        "size_bytes": int(loaded.get("size_bytes", 0) or 0),
        "modified": loaded.get("modified"),
        "error": loaded.get("error", ""),
        "data": data,
        "rows_count": int(data.get("rows", 0) or data.get("journal_rows", 0) or 0)
        if isinstance(data, dict)
        else 0,
    }


def _source_from_csv(name: str, path: Path, root: Path) -> dict:
    status = file_status(path)
    df = load_csv_report(path)
    return {
        "name": name,
        "kind": "csv",
        "path": _relative(path, root),
        "exists": bool(status.get("exists", False)),
        "status": df.attrs.get("status", "UNKNOWN"),
        "size_bytes": int(status.get("size_bytes", 0) or 0),
        "modified": status.get("modified"),
        "error": df.attrs.get("error", ""),
        "dataframe": df,
        "rows_count": int(len(df)),
        "columns": list(df.columns),
    }


def _source_from_markdown(name: str, path: Path, root: Path) -> dict:
    status = file_status(path)
    text = load_markdown_report(path)
    source_status = "MISSING"
    if status.get("exists") and text.strip():
        source_status = "AVAILABLE"
    elif status.get("exists"):
        source_status = "EMPTY"
    return {
        "name": name,
        "kind": "markdown",
        "path": _relative(path, root),
        "exists": bool(status.get("exists", False)),
        "status": source_status,
        "size_bytes": int(status.get("size_bytes", 0) or 0),
        "modified": status.get("modified"),
        "error": status.get("error", ""),
        "text": text,
        "rows_count": 0,
    }


def load_all_ui_sources(root: Path) -> dict:
    root = root.resolve()
    sources: dict = {}
    for name, (kind, relative_path) in SOURCE_SPECS.items():
        path = root / relative_path
        try:
            if kind == "json":
                sources[name] = _source_from_json(name, path, root)
            elif kind == "csv":
                sources[name] = _source_from_csv(name, path, root)
            elif kind == "markdown":
                sources[name] = _source_from_markdown(name, path, root)
            else:
                sources[name] = {
                    "name": name,
                    "kind": kind,
                    "path": _relative(path, root),
                    "status": "INVALID",
                    "error": f"unsupported_kind:{kind}",
                    "rows_count": 0,
                }
        except Exception as exc:
            sources[name] = {
                "name": name,
                "kind": kind,
                "path": _relative(path, root),
                "status": "INVALID",
                "error": str(exc),
                "rows_count": 0,
            }

    available = sum(1 for source in sources.values() if source.get("status") == "AVAILABLE")
    missing = sum(1 for source in sources.values() if source.get("status") == "MISSING")
    invalid = sum(1 for source in sources.values() if source.get("status") == "INVALID")
    empty = sum(1 for source in sources.values() if source.get("status") == "EMPTY")
    return {
        "root": str(root),
        "sources": sources,
        "summary": {
            "available_sources": available,
            "missing_sources": missing,
            "invalid_sources": invalid,
            "empty_sources": empty,
            "total_sources": len(sources),
        },
    }
