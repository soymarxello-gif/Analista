from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from loguru import logger

from config_loader import load_config
from engine.report_engine import save_reports
from engine.scan_audit_engine import audit_scan_file, print_audit_report
from engine.scanner_engine import run_scan
from tools.manual_review_export import save_manual_review_reports


def _print_scan_preview(df: pd.DataFrame, rows: int = 20) -> None:
    if df.empty:
        print("Scanner completado sin candidatos.")
        return

    cols = [
        "rank",
        "ticker",
        "pre_veto_signal",
        "signal",
        "recommendation",
        "setup_type",
        "final_trade_score",
        "asset_quality_score",
        "setup_quality_score",
        "final_score",
        "actionable_entry",
        "actionable_stop",
        "actionable_target",
        "rr",
        "stop_atr_multiple",
        "stop_atr_status",
        "quote_status",
        "execution_quote_quality",
        "options_bias",
        "options_confidence",
        "penalty_reasons",
        "veto_reasons",
        "reason_summary",
    ]
    
    cols = [c for c in cols if c in df.columns]

    print(df[cols].head(rows).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analista - scanner auditado para flujo operativo diario."
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--json-out", default="reports/latest_scan_audited.json")
    parser.add_argument("--csv-out", default="reports/latest_scan_audited.csv")
    parser.add_argument("--markdown-out", default="reports/latest_scan_audited.md")
    parser.add_argument("--html-out", default="reports/latest_scan_audited.html")
    parser.add_argument("--audit-json-out", default=None)
    parser.add_argument("--fail-on-audit-fail", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--preview-rows", type=int, default=20)
    args = parser.parse_args()

    config = load_config(args.config)

    if args.verbose:
        logger.info("Ejecutando scanner auditado.")
        logger.info(f"Config: {args.config}")
        logger.info(f"CSV out: {args.csv_out}")
        logger.info(f"JSON out: {args.json_out}")

    df = run_scan(config, max_candidates=args.max_candidates)
    save_reports(
        df,
        config,
        json_out=args.json_out,
        csv_out=args.csv_out,
        markdown_out=args.markdown_out,
        html_out=args.html_out,
    )    
    save_manual_review_reports(
        df,
        csv_out=Path("reports/manual_review_latest.csv"),
        markdown_out=Path("reports/manual_review_latest.md"),
    )

    logger.info(f"Scanner completado. Candidatos: {len(df)}")
    _print_scan_preview(df, rows=args.preview_rows)

    csv_path = Path(args.csv_out)
    audit_json_out = args.audit_json_out
    if audit_json_out is None:
        audit_json_out = str(Path("reports/audits") / f"audit_{csv_path.stem}.json")

    report = audit_scan_file(csv_path, output_json=audit_json_out)
    print_audit_report(report)

    status = report.get("status")
    if args.fail_on_audit_fail and status == "FAIL":
        logger.error("Audit status FAIL. Retornando exit code 1.")
        return 1

    if status == "FAIL":
        logger.warning("Audit status FAIL. No usar resultados operativamente hasta corregir.")
    elif status == "WARN":
        logger.warning("Audit status WARN. Resultados utilizables solo con revisión manual.")
    else:
        logger.info("Audit status PASS.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
