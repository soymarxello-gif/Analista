from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from institutional.baseline import create_baseline_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a reproducible Analista baseline bundle")
    parser.add_argument("--database", required=True)
    parser.add_argument("--configuration", default="config.yaml")
    parser.add_argument("--output", default="reports/institutional-baseline.zip")
    args = parser.parse_args()
    print(create_baseline_bundle(args.database, args.configuration, args.output))


if __name__ == "__main__":
    main()
