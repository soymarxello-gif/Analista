from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import json

NEW_YORK_TZ = ZoneInfo("America/New_York")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def register_scan_for_backtest(
    df,
    *,
    telemetry_snapshot: dict[str, Any],
    run_trust: dict[str, Any],
    config: dict,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now_et = now.astimezone(NEW_YORK_TZ)
    run_id = now.strftime("%Y%m%dT%H%M%S%fZ")
    root = Path(config.get("backtesting", {}).get("registry_dir", "backtesting"))
    run_dir = root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    enriched = df.copy()
    enriched["backtest_run_id"] = run_id
    enriched["generated_at_utc"] = now.isoformat()
    enriched["market_date_et"] = now_et.date().isoformat()
    enriched["exchange_timezone"] = "America/New_York"

    json_path = run_dir / "scan.json"
    csv_path = run_dir / "scan.csv"
    telemetry_path = run_dir / "telemetry.json"
    _atomic_write(json_path, enriched.to_json(orient="records", indent=2, date_format="iso"))
    enriched.to_csv(csv_path, index=False)
    _atomic_write(telemetry_path, json.dumps(telemetry_snapshot, ensure_ascii=False, indent=2))

    manifest = {
        "registry_schema_version": "1.0",
        "run_id": run_id,
        "generated_at_utc": now.isoformat(),
        "market_date_et": now_et.date().isoformat(),
        "exchange_timezone": "America/New_York",
        "scheduled_time_et": "09:20",
        "rows": int(len(enriched)),
        "run_trust_status": run_trust.get("run_trust_status"),
        "run_trust_reasons": run_trust.get("run_trust_reasons", []),
        "files": {
            "scan_json": {"path": str(json_path), "sha256": _digest(json_path)},
            "scan_csv": {"path": str(csv_path), "sha256": _digest(csv_path)},
            "telemetry_json": {"path": str(telemetry_path), "sha256": _digest(telemetry_path)},
        },
    }
    manifest_path = run_dir / "manifest.json"
    _atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    index_path = root / "index.jsonl"
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {"run_id": run_id, "run_dir": str(run_dir), "manifest": manifest}
