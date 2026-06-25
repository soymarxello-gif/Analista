from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config_loader import load_config
from engine.calibration_engine import (
    calibrate_weights_from_posttest,
    save_calibration_report,
    summarize_posttest,
)
from engine.posttest_batch_engine import print_batch_report, run_posttest_batch


def main() -> int:
    parser = argparse.ArgumentParser(description="Analista - pipeline evidencia: posttest batch + resumen + calibración.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--patterns", nargs="+", default=None)
    parser.add_argument("--horizons", nargs="+", type=int, default=[4])
    parser.add_argument("--min-age-days", type=int, default=None)
    parser.add_argument("--posttest-dir", default="reports/posttests")
    parser.add_argument("--overwrite-posttests", action="store_true")
    parser.add_argument("--calibration-horizon", type=int, default=4)
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--max-delta-pct", type=float, default=0.20)
    args = parser.parse_args()

    config = load_config(args.config)

    batch_report = run_posttest_batch(
        patterns=args.patterns,
        horizons=args.horizons,
        min_age_days=args.min_age_days,
        output_dir=args.posttest_dir,
        overwrite=args.overwrite_posttests,
    )
    print_batch_report(batch_report)

    posttest_pattern = str(Path(args.posttest_dir) / "*.csv")

    summary = summarize_posttest([posttest_pattern], min_samples=max(3, min(args.min_samples, 10)))
    summary_path = Path("reports/calibration/posttest_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    calibration = calibrate_weights_from_posttest(
        [posttest_pattern],
        config=config,
        horizon=args.calibration_horizon,
        min_samples=args.min_samples,
        max_delta_pct=args.max_delta_pct,
    )

    save_calibration_report(
        calibration,
        output_json="reports/calibration/weight_calibration.json",
        output_csv="reports/calibration/weight_calibration.csv",
    )

    print("\n=== EVIDENCE PIPELINE ===")
    print(f"Posttest summary: {summary_path}")
    print("Calibration JSON: reports/calibration/weight_calibration.json")
    print("Calibration CSV: reports/calibration/weight_calibration.csv")
    print(f"Calibration status: {calibration.get('status')}")
    if calibration.get("message"):
        print(calibration["message"])
    if calibration.get("warning"):
        print(calibration["warning"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
