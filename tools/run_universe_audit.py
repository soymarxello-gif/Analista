from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config_loader import load_config
from engine.universe_source_audit import audit_universe_file, print_universe_audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Analista - audita sesgo del universo inicial/screener.")
    parser.add_argument("--csv", required=True, help="CSV del scan o universo.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    report = audit_universe_file(args.csv, output_json=args.json_out, config=config)
    print_universe_audit(report)

    if args.fail_on_issues and report.get("status") == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
