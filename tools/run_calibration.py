from __future__ import annotations

import argparse
from pathlib import Path
import json

import pandas as pd

from config_loader import load_config
from engine.calibration_engine import (
    calibrate_weights_from_posttest,
    save_calibration_report,
    summarize_posttest,
)


def _print_summary(report: dict) -> None:
    print("\n=== POST-TEST SUMMARY ===")
    print(f"Status: {report.get('status')}")
    summary = report.get("summary", {})
    for k, v in summary.items():
        print(f"{k}: {v}")

    group_summaries = report.get("group_summaries", {})
    if not group_summaries:
        print("\nSin group summaries suficientes.")
        return

    preferred = [
        "signal_ALL",
        "pre_veto_signal_ALL",
        "setup_type_ALL",
        "options_bias_ALL",
        "data_quality_confidence_ALL",
    ]

    for key in preferred:
        rows = group_summaries.get(key)
        if not rows:
            continue
        print(f"\n--- {key} ---")
        cols = [
            "group",
            "value",
            "horizon_days",
            "samples",
            "hit_rate",
            "avg_return_close",
            "median_return_close",
            "avg_mfe",
            "avg_mae",
            "expectancy_proxy",
        ]
        print(pd.DataFrame(rows)[cols].head(12).to_string(index=False))


def _print_calibration(report: dict) -> None:
    print("\n=== WEIGHT CALIBRATION ===")
    print(f"Status: {report.get('status')}")
    print(f"Horizon: {report.get('horizon_days')}")
    print(f"Samples: {report.get('samples')}")
    print(f"Method: {report.get('method')}")
    if report.get("message"):
        print(report["message"])
    if report.get("warning"):
        print(f"Warning: {report['warning']}")

    details = report.get("details") or []
    if details:
        cols = [
            "score_col",
            "weight_key",
            "samples",
            "spearman_corr",
            "old_weight",
            "proposed_weight",
            "delta_weight",
        ]
        print(pd.DataFrame(details)[cols].to_string(index=False))

    proposed = report.get("proposed_weights") or {}
    if proposed:
        print("\nProposed scoring_weights:")
        print(json.dumps(proposed, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Analista - resumen y calibración con post-tests.")
    parser.add_argument("--posttests", nargs="+", required=True, help="CSV(s) o patrón glob, ej: reports/posttests/*.csv")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--max-delta-pct", type=float, default=0.20)
    parser.add_argument("--summary-json-out", default="reports/calibration/posttest_summary.json")
    parser.add_argument("--calibration-json-out", default="reports/calibration/weight_calibration.json")
    parser.add_argument("--calibration-csv-out", default="reports/calibration/weight_calibration.csv")
    args = parser.parse_args()

    config = load_config(args.config)

    summary = summarize_posttest(args.posttests, min_samples=max(3, min(args.min_samples, 10)))
    Path(args.summary_json_out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.summary_json_out).open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    _print_summary(summary)

    calibration = calibrate_weights_from_posttest(
        args.posttests,
        config=config,
        horizon=args.horizon,
        min_samples=args.min_samples,
        max_delta_pct=args.max_delta_pct,
    )

    save_calibration_report(
        calibration,
        output_json=args.calibration_json_out,
        output_csv=args.calibration_csv_out,
    )

    _print_calibration(calibration)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
