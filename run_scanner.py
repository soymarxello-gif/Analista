from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from config_loader import load_config
from contracts.scan_schema import SCHEMA_VERSION, assert_scan_schema
from data.quote_context import normalize_scan_with_quote_context
from engine.report_engine import format_numeric_columns, save_reports
from engine.scanner_engine import run_scan


def setup_logger(config: dict, verbose: bool = False):
    logger.remove()
    level = "DEBUG" if verbose else config.get("logging", {}).get("level", "INFO")

    if config.get("logging", {}).get("log_to_console", True):
        logger.add(lambda msg: print(msg, end=""), level=level)

    log_file = config.get("logging", {}).get("file", "logs/scanner.log")
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logger.add(log_file, level=level, rotation="2 MB")


def main():
    parser = argparse.ArgumentParser(description="Analista - Scanner swing long-only USA")
    parser.add_argument("--config", default=None)
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--csv-out", default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-intraday", action="store_true", help="Reservado para compatibilidad futura.")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logger(config, args.verbose)

    raw_df = run_scan(config, max_candidates=args.max_candidates)

    if raw_df.empty:
        logger.warning("Scanner terminó sin candidatos.")
        return

    df = normalize_scan_with_quote_context(raw_df, config)
    df["schema_version"] = SCHEMA_VERSION
    assert_scan_schema(df)
    save_reports(df, config, json_out=args.json_out, csv_out=args.csv_out)
    logger.info(f"Scanner completado. Candidatos: {len(df)} | schema={SCHEMA_VERSION}")

    display_cols = [
        "rank",
        "ticker",
        "signal",
        "setup_type",
        "final_score",
        "final_trade_score",
        "quote_status",
        "execution_quote_quality",
        "quote_age_seconds",
        "market_session",
        "actionable_entry",
        "actionable_stop",
        "actionable_target",
        "rr",
        "reason_summary",
    ]

    available_cols = [c for c in display_cols if c in df.columns]
    display_df = format_numeric_columns(df[available_cols].head(30), decimals=2)
    print(display_df.to_string(index=False))


if __name__ == "__main__":
    main()
