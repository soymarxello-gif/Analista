from __future__ import annotations

import argparse
from engine.posttest_engine import run_posttest


def main():
    parser = argparse.ArgumentParser(description="Analista - post-test de señales históricas")
    parser.add_argument("--scan", required=True, help="Ruta al CSV de scan, ej: reports/latest_scan.csv")
    parser.add_argument("--horizons", nargs="+", type=int, default=[4, 7, 10, 15, 21])
    parser.add_argument("--csv-out", default=None)
    args = parser.parse_args()

    df = run_posttest(args.scan, horizons=args.horizons, output_csv=args.csv_out)

    if df.empty:
        print("Post-test sin resultados. Puede que aún no existan suficientes días futuros.")
        return

    summary = (
        df.groupby(["horizon_days", "signal"], dropna=False)
        .agg(
            trades=("ticker", "count"),
            avg_return=("return_close_pct", "mean"),
            median_return=("return_close_pct", "median"),
            avg_mfe=("mfe_pct", "mean"),
            avg_mae=("mae_pct", "mean"),
            target_hit_rate=("hit_target", "mean"),
            stop_hit_rate=("hit_stop", "mean"),
        )
        .reset_index()
    )

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
