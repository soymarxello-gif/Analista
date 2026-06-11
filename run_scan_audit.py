from __future__ import annotations

import argparse

from engine.scan_audit_engine import audit_scan_file, print_audit_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita un CSV generado por Analista.")
    parser.add_argument("--scan", required=True, help="Ruta al CSV de scan, ej: reports/latest_scan_phase1_2.csv")
    parser.add_argument("--json-out", default=None, help="Ruta opcional de salida JSON")
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="Retorna código 1 si el audit status es FAIL",
    )
    args = parser.parse_args()

    report = audit_scan_file(args.scan, output_json=args.json_out)
    print_audit_report(report)

    if args.fail_on_issues and report.get("status") == "FAIL":
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
