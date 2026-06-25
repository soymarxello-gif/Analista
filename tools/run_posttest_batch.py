from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.posttest_batch_engine import print_batch_report, run_posttest_batch


def main() -> int:
    parser = argparse.ArgumentParser(description="Analista - ejecuta post-tests batch sobre scans elegibles.")
    parser.add_argument("--patterns", nargs="+", default=None, help="Patrones de scans CSV. Ej: reports/*.csv reports/history/*.csv")
    parser.add_argument("--horizons", nargs="+", type=int, default=[4])
    parser.add_argument("--top-n-candidates", type=int, default=5)
    parser.add_argument("--min-age-days", type=int, default=None)
    parser.add_argument("--output-dir", default="reports/posttests")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    report = run_posttest_batch(
        patterns=args.patterns,
        horizons=args.horizons,
        min_age_days=args.min_age_days,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        top_n_candidates=args.top_n_candidates,
    )
    print_batch_report(report)

    return 0 if report.get("posttests_error", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
