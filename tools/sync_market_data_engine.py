from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config_loader import load_config
from engine.data_sources.market_data_engine import inspect_market_database


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sync_market_database(config: dict | None = None, *, force: bool = False) -> dict:
    config = config or load_config()
    cfg = config.get("data_sources", {}).get("providers", {}).get("market_data_engine", {}) or {}
    report = {
        "status": "WARN",
        "source": "MARKET_DATA_ENGINE_SQLITE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "updated": False,
        "errors": [],
        "warnings": [],
    }
    if not cfg.get("enabled", True):
        report.update(status="DISABLED", warnings=["provider_disabled"])
        return report

    source_db = Path(os.environ.get("MARKET_DATA_ENGINE_DRIVE_DB", cfg.get("drive_db_path", "")))
    source_manifest = Path(cfg.get("drive_manifest_path", ""))
    local_db = ROOT / Path(cfg.get("local_cache_path", "cache/market_data_engine/us_market_5y.db"))
    local_manifest = ROOT / Path(
        cfg.get("local_manifest_path", "cache/market_data_engine/master_manifest.json")
    )
    report.update(
        {
            "source_db_path": str(source_db),
            "source_manifest_path": str(source_manifest),
            "local_db_path": str(local_db),
            "local_manifest_path": str(local_manifest),
        }
    )
    if not source_db.is_file():
        report["errors"].append("drive_database_missing")
        if local_db.is_file():
            health = inspect_market_database(local_db, max_stale_days=int(cfg.get("max_stale_days", 7)))
            report.update(status="WARN", local_health=health)
            report["warnings"].append("using_existing_local_cache")
        else:
            report["status"] = "FAIL"
        return report

    manifest: dict = {}
    if source_manifest.is_file():
        try:
            manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
        except Exception as exc:
            report["warnings"].append(f"manifest_read_failed:{type(exc).__name__}")
    else:
        report["warnings"].append("drive_manifest_missing")

    local_manifest_data: dict = {}
    if local_manifest.is_file():
        try:
            local_manifest_data = json.loads(local_manifest.read_text(encoding="utf-8"))
        except Exception:
            local_manifest_data = {}
    source_signature = manifest.get("database_sha256") or f"{source_db.stat().st_size}:{source_db.stat().st_mtime_ns}"
    local_signature = local_manifest_data.get("database_sha256") or local_manifest_data.get("source_signature")
    needs_copy = force or not local_db.is_file() or source_signature != local_signature
    if needs_copy:
        local_db.parent.mkdir(parents=True, exist_ok=True)
        partial = local_db.with_suffix(local_db.suffix + ".partial")
        partial.unlink(missing_ok=True)
        try:
            shutil.copy2(source_db, partial)
            health = inspect_market_database(partial, max_stale_days=int(cfg.get("max_stale_days", 7)))
            if health.get("status") not in {"PASS", "WARN"}:
                raise RuntimeError("copied_database_validation_failed:" + ";".join(health.get("errors", [])))
            expected = manifest.get("database_sha256")
            actual = _sha256(partial) if expected else None
            if expected and actual != expected:
                raise RuntimeError("database_checksum_mismatch")
            os.replace(partial, local_db)
            report["updated"] = True
        except Exception as exc:
            partial.unlink(missing_ok=True)
            report["errors"].append(f"database_sync_failed:{type(exc).__name__}:{exc}")
            report["status"] = "FAIL"
            return report

    health = inspect_market_database(local_db, max_stale_days=int(cfg.get("max_stale_days", 7)))
    stored_manifest = dict(manifest)
    stored_manifest["source_signature"] = source_signature
    stored_manifest["synced_at"] = datetime.now(timezone.utc).isoformat()
    local_manifest.parent.mkdir(parents=True, exist_ok=True)
    local_manifest.write_text(json.dumps(stored_manifest, indent=2), encoding="utf-8")
    report.update(local_health=health, manifest=manifest)
    report["status"] = "PASS" if health.get("status") == "PASS" and not report["warnings"] else "WARN"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync the validated Market Data Engine snapshot locally.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json-out", default=str(ROOT / "reports" / "market_data_engine_sync_latest.json"))
    args = parser.parse_args()
    result = sync_market_database(force=args.force)
    output = Path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in {"PASS", "WARN", "DISABLED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
