from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PREFERENCES_VERSION = 1
DEFAULT_PREFERENCES = {"version": PREFERENCES_VERSION, "tables": {}}


def preferences_path(root: Path) -> Path:
    return root / "cache" / "ui_preferences.json"


def load_preferences(root: Path) -> dict[str, Any]:
    path = preferences_path(root)
    if not path.exists():
        return dict(DEFAULT_PREFERENCES)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_PREFERENCES)
    if not isinstance(data, dict):
        return dict(DEFAULT_PREFERENCES)
    data.setdefault("version", PREFERENCES_VERSION)
    data.setdefault("tables", {})
    if not isinstance(data["tables"], dict):
        data["tables"] = {}
    return data


def save_preferences(root: Path, preferences: dict[str, Any]) -> Path:
    path = preferences_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(preferences or {})
    payload["version"] = PREFERENCES_VERSION
    payload.setdefault("tables", {})
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


def get_table_preferences(
    root: Path,
    table_key: str,
    *,
    default_columns: list[str],
    default_sort_column: str = "",
    default_sort_desc: bool = True,
) -> dict[str, Any]:
    preferences = load_preferences(root)
    table = preferences.get("tables", {}).get(table_key, {})
    if not isinstance(table, dict):
        table = {}
    columns = table.get("columns", default_columns)
    if not isinstance(columns, list):
        columns = default_columns
    return {
        "columns": [str(column) for column in columns],
        "sort_column": str(table.get("sort_column") or default_sort_column or ""),
        "sort_desc": bool(table.get("sort_desc", default_sort_desc)),
    }


def set_table_preferences(
    root: Path,
    table_key: str,
    *,
    columns: list[str],
    sort_column: str = "",
    sort_desc: bool = True,
) -> dict[str, Any]:
    preferences = load_preferences(root)
    tables = preferences.setdefault("tables", {})
    tables[table_key] = {
        "columns": [str(column) for column in columns],
        "sort_column": str(sort_column or ""),
        "sort_desc": bool(sort_desc),
    }
    save_preferences(root, preferences)
    return tables[table_key]


def reset_table_preferences(root: Path, table_key: str) -> None:
    preferences = load_preferences(root)
    preferences.setdefault("tables", {}).pop(table_key, None)
    save_preferences(root, preferences)


def sanitize_columns(
    available_columns: list[str],
    requested_columns: list[str],
    default_columns: list[str],
) -> list[str]:
    available = [str(column) for column in available_columns]
    available_set = set(available)
    requested = [str(column) for column in requested_columns if str(column) in available_set]
    if requested:
        return requested
    fallback = [str(column) for column in default_columns if str(column) in available_set]
    return fallback or available[: min(8, len(available))]


def sanitize_sort_column(
    available_columns: list[str],
    requested_column: str,
    default_column: str = "",
) -> str:
    available_set = {str(column) for column in available_columns}
    if requested_column in available_set:
        return requested_column
    if default_column in available_set:
        return default_column
    return ""
