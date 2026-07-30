from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _is_missing_series(series: pd.Series) -> pd.Series:
    return (
        series.isna()
        | series.astype(str).str.strip().str.lower().isin({"", "none", "nan", "null", "na", "n/a"})
    )


def _safe_counts(df: pd.DataFrame, col: str) -> dict:
    if col not in df.columns:
        return {}

    return (
        df[col]
        .fillna("MISSING")
        .astype(str)
        .replace({"": "MISSING"})
        .value_counts(dropna=False)
        .to_dict()
    )


def _pct(value: float) -> float:
    return round(float(value) * 100.0, 2)


def build_source_coverage_report(df: pd.DataFrame, top_n: int = 30) -> dict:
    total_rows = len(df)

    report: dict = {
        "rows": total_rows,
        "coverage_scopes": {},
        "counts": {},
        "missing_rates": {},
        "cross_tabs": {},
        "options_flow": {},
        "analysis_quotes": {},
        "top_missing_metadata": [],
        "top_quote_low": [],
        "operable_missing_metadata": [],
    }

    if total_rows == 0:
        return report

    metadata_requested_mask = pd.Series(True, index=df.index)
    if "metadata_source" in df.columns:
        metadata_requested_mask = ~(
            df["metadata_source"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.startswith("NOT_REQUESTED")
        )
    metadata_df = df.loc[metadata_requested_mask].copy()

    execution_scope_mask = metadata_requested_mask.copy()
    if "technical_analysis_lane" in df.columns:
        execution_scope_mask |= (
            df["technical_analysis_lane"]
            .fillna("")
            .astype(str)
            .str.upper()
            .eq("ADVANCE_DEEP_ANALYSIS")
        )
    execution_df = df.loc[execution_scope_mask].copy()
    report["coverage_scopes"] = {
        "all_rows": int(total_rows),
        "metadata_requested_rows": int(len(metadata_df)),
        "metadata_not_requested_rows": int(total_rows - len(metadata_df)),
        "execution_review_rows": int(len(execution_df)),
    }

    for col in [
        "signal",
        "recommendation",
        "technical_analysis_lane",
        "decision_lane",
        "primary_setup_hypothesis",
        "primary_setup_hypothesis_state",
        "trend_transition_state",
        "momentum_gate_status",
        "timing_gate_status",
        "core_liquidity_status",
        "technical_prefilter_status",
        "technical_prefilter_triage",
        "daily_macd_prefilter_status",
        "weekly_macd_prefilter_status",
        "daily_macd_trajectory_state",
        "weekly_macd_trajectory_state",
        "momentum_alignment",
        "momentum_operability_status",
        "ema20_extension_prefilter_status",
        "sector_benchmark_symbol",
        "sector_weekly_macd_state",
        "sector_weekly_macd_acceleration_state",
        "sector_context_status",
        "sector_context_reason",
        "quote_status",
        "execution_quote_quality",
        "execution_spread_status",
        "options_source",
        "options_available",
        "options_data_available",
        "options_error",
        "options_coverage_status",
        "options_bias",
        "options_confidence",
        "options_priority_selected",
        "options_priority_reason",
        "options_preliminary_signal",
        "data_quality_confidence",
        "analysis_quote_source",
        "analysis_quote_freshness",
        "analysis_quote_confidence",
        "secondary_data_sources_used",
        "metadata_source",
        "sector_source",
        "industry_source",
        "market_cap_source",
        "earnings_source",
    ]:
        report["counts"][col] = _safe_counts(df, col)

    missing_fields = [
        "sector",
        "industry",
        "quote_status",
        "execution_quote_quality",
        "market_cap",
        "avg_volume_20d",
        "dollar_volume_20d",
        "dollar_volume_60d",
        "rr",
        "atr",
        "setup_type",
        "analysis_price",
        "analysis_bid",
        "analysis_ask",
    ]

    metadata_fields = {"sector", "industry", "market_cap"}
    execution_fields = {
        "quote_status",
        "execution_quote_quality",
        "analysis_bid",
        "analysis_ask",
    }
    for col in missing_fields:
        scope = (
            metadata_df
            if col in metadata_fields
            else execution_df
            if col in execution_fields
            else df
        )
        if col in scope.columns:
            report["missing_rates"][col] = (
                _pct(_is_missing_series(scope[col]).mean()) if len(scope) else 0.0
            )

    if {"sector", "industry"}.issubset(metadata_df.columns):
        missing_sector = _is_missing_series(metadata_df["sector"])
        missing_industry = _is_missing_series(metadata_df["industry"])
        df_tmp = metadata_df.copy()
        df_tmp["_metadata_missing"] = missing_sector | missing_industry

        report["counts"]["metadata_missing"] = (
            df_tmp["_metadata_missing"]
            .map({True: "MISSING_SECTOR_OR_INDUSTRY", False: "OK"})
            .value_counts()
            .to_dict()
        )

        if "signal" in df_tmp.columns:
            report["cross_tabs"]["metadata_missing_by_signal"] = (
                pd.crosstab(df_tmp["_metadata_missing"], df_tmp["signal"])
                .to_dict()
            )

        if "quote_status" in df_tmp.columns:
            report["cross_tabs"]["metadata_missing_by_quote_status"] = (
                pd.crosstab(df_tmp["_metadata_missing"], df_tmp["quote_status"].fillna("MISSING"))
                .to_dict()
            )

        cols = [
            "rank",
            "ticker",
            "signal",
            "recommendation",
            "sector",
            "industry",
            "quote_status",
            "execution_quote_quality",
            "data_quality_score",
            "core_data_quality_score",
            "fundamental_data_quality_score",
            "options_bias",
        ]
        cols = [c for c in cols if c in df_tmp.columns]

        report["top_missing_metadata"] = (
            df_tmp[df_tmp["_metadata_missing"]]
            .head(top_n)[cols]
            .to_dict(orient="records")
        )

        if "signal" in df_tmp.columns:
            operable_signals = {"TRIGGER_CONFIRMED", "READY_WAIT_TRIGGER", "WATCHLIST"}
            report["operable_missing_metadata"] = (
                df_tmp[
                    df_tmp["_metadata_missing"]
                    & df_tmp["signal"].astype(str).isin(operable_signals)
                ]
                .head(top_n)[cols]
                .to_dict(orient="records")
            )

    if "execution_quote_quality" in execution_df.columns:
        low_quote = execution_df[
            execution_df["execution_quote_quality"].astype(str).str.upper() == "LOW"
        ].copy()
        cols = [
            "rank",
            "ticker",
            "signal",
            "recommendation",
            "quote_status",
            "execution_quote_quality",
            "sector",
            "industry",
            "final_trade_score",
            "setup_quality_score",
            "penalty_reasons",
        ]
        cols = [c for c in cols if c in low_quote.columns]

        report["top_quote_low"] = low_quote.head(top_n)[cols].to_dict(orient="records")

    option_summary_cols = [
        "options_bias",
        "options_confidence",
        "options_source",
        "options_available",
        "options_data_available",
        "options_error",
        "options_coverage_status",
        "options_priority_selected",
        "options_priority_reason",
        "options_preliminary_signal",
    ]
    report["options_flow"] = {
        col: _safe_counts(df, col)
        for col in option_summary_cols
        if col in df.columns
    }

    analysis_quote_cols = [
        "analysis_quote_source",
        "analysis_quote_freshness",
        "analysis_quote_confidence",
        "secondary_data_sources_used",
    ]
    report["analysis_quotes"] = {
        col: _safe_counts(df, col)
        for col in analysis_quote_cols
        if col in df.columns
    }

    return report


def print_report(report: dict) -> None:
    print("\n=== SOURCE COVERAGE AUDIT ===")
    print(f"Rows: {report.get('rows', 0)}")
    scopes = report.get("coverage_scopes", {})
    if scopes:
        print(
            "Coverage scope: "
            f"metadata requested={scopes.get('metadata_requested_rows', 0)}, "
            f"not requested={scopes.get('metadata_not_requested_rows', 0)}, "
            f"execution review={scopes.get('execution_review_rows', 0)}"
        )

    print("\n[Counts]")
    for col, counts in report.get("counts", {}).items():
        if counts:
            print(f"\n{col}:")
            for key, value in counts.items():
                print(f"  {key}: {value}")

    print("\n[Missing rates]")
    for col, rate in report.get("missing_rates", {}).items():
        print(f"  {col}: {rate}%")

    print("\n[Options / institutional flow]")
    for col, counts in report.get("options_flow", {}).items():
        if counts:
            print(f"\n{col}:")
            for key, value in counts.items():
                print(f"  {key}: {value}")

    print("\n[Analysis quotes / delayed sources]")
    for col, counts in report.get("analysis_quotes", {}).items():
        if counts:
            print(f"\n{col}:")
            for key, value in counts.items():
                print(f"  {key}: {value}")

    print("\n[Cross tabs]")
    for name, table in report.get("cross_tabs", {}).items():
        print(f"\n{name}:")
        print(json.dumps(table, indent=2, ensure_ascii=False))

    print("\n[Top missing metadata]")
    for row in report.get("top_missing_metadata", [])[:10]:
        print(row)

    print("\n[Operable missing metadata]")
    for row in report.get("operable_missing_metadata", [])[:10]:
        print(row)

    print("\n[Top LOW execution quote]")
    for row in report.get("top_quote_low", [])[:10]:
        print(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita cobertura de fuentes y metadata del último scan.")
    parser.add_argument("--csv", default="reports/latest_scan_audited.csv")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--top-n", type=int, default=30)
    args = parser.parse_args()

    csv_path = ROOT / args.csv
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe CSV: {csv_path}")

    df = pd.read_csv(csv_path)
    report = build_source_coverage_report(df, top_n=args.top_n)

    print_report(report)

    if args.json_out:
        out_path = ROOT / args.json_out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON escrito en: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
