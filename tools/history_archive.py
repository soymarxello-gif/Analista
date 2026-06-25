from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


ARCHIVE_FILES = [
    {"path": "reports/latest_scan_audited.csv", "required": True},
    {"path": "reports/latest_scan_audited.json", "required": False},
    {"path": "reports/manual_review_latest.csv", "required": True},
    {"path": "reports/manual_review_latest.md", "required": True},
    {"path": "reports/daily_validation_summary.txt", "required": True},
    {"path": "reports/source_coverage_latest.json", "required": False},
]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def archive_current_reports(
    root: Path = ROOT,
    timestamp: str | None = None,
    archive_root: Path | None = None,
) -> dict:
    timestamp = timestamp or _timestamp()
    archive_root = archive_root or root / "reports" / "history"
    archive_dir = archive_root / timestamp
    archive_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    missing: list[str] = []
    missing_required: list[str] = []

    for item in ARCHIVE_FILES:
        rel_path = item["path"]
        required = bool(item.get("required", False))
        src = root / rel_path

        if not src.exists():
            missing.append(rel_path)
            if required:
                missing_required.append(rel_path)
            continue

        dst = archive_dir / Path(rel_path).name
        shutil.copy2(src, dst)
        copied.append(rel_path)

    manifest = {
        "timestamp": timestamp,
        "archive_dir": str(archive_dir.relative_to(root)),
        "copied": copied,
        "missing": missing,
        "missing_required": missing_required,
        "status": "FAIL" if missing_required else "PASS",
    }

    manifest_path = archive_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    latest_pointer = archive_root / "latest.txt"
    latest_pointer.write_text(str(archive_dir.relative_to(root)), encoding="utf-8")

    return manifest


def print_archive_report(manifest: dict) -> None:
    print("\n=== ANALISTA HISTORY ARCHIVE ===")
    print(f"Status: {manifest.get('status')}")
    print(f"Archive dir: {manifest.get('archive_dir')}")

    print("\n[Copied]")
    for item in manifest.get("copied", []):
        print(f"- {item}")

    print("\n[Missing]")
    missing = manifest.get("missing", [])
    if not missing:
        print("- None")
    else:
        for item in missing:
            print(f"- {item}")

    missing_required = manifest.get("missing_required", [])
    if missing_required:
        print("\n[Missing required]")
        for item in missing_required:
            print(f"- {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Archiva los reportes actuales de Analista.")
    parser.add_argument("--timestamp", default=None)
    args = parser.parse_args()

    manifest = archive_current_reports(timestamp=args.timestamp)
    print_archive_report(manifest)

    return 0 if manifest["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())