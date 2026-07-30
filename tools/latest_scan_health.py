from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.scan_audit_engine import audit_scan_file, print_audit_report


def _discover_latest_csv(reports_dir: Path) -> Path:
    canonical_scan = reports_dir / "latest_scan_audited.csv"
    if canonical_scan.exists():
        return canonical_scan

    files = list(reports_dir.glob("*.csv"))

    history = reports_dir / "history"
    if history.exists():
        files.extend(history.glob("*.csv"))

    if not files:
        raise FileNotFoundError(f"No encontré CSVs en {reports_dir} ni {history}")

    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita automáticamente el CSV más reciente de reports/.")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()

    latest = _discover_latest_csv(Path(args.reports_dir))
    print(f"CSV más reciente: {latest}")

    report = audit_scan_file(latest, output_json=args.json_out)
    print_audit_report(report)

    if args.fail_on_issues and report.get("status") == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
