from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from config_loader import load_config
from contracts.scan_schema import SCHEMA_VERSION, assert_scan_schema
from data.quote_context import normalize_scan_with_quote_context
from engine.data_telemetry import save_telemetry
from engine.data_telemetry_runtime import install_data_telemetry
from engine.backtest_registry import register_scan_for_backtest
from engine.circuit_breaker_runtime import install_circuit_breakers
from engine.early_filter_runtime import append_early_veto_rows, install_early_filters
from engine.options_priority_runtime import install_options_priority
from engine.report_engine import format_numeric_columns, save_reports
from engine.retry_runtime import install_retries
from engine.source_health import format_health_log
from engine.run_trust import assess_run_trust, attach_run_trust
import engine.scanner_engine as scanner_engine


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
    telemetry = install_data_telemetry(scanner_engine)
    install_retries(scanner_engine, config, telemetry)
    install_circuit_breakers(scanner_engine, config, telemetry)
    early_state = install_early_filters(scanner_engine, config)
    install_options_priority(scanner_engine, config)

    try:
        raw_df = scanner_engine.run_scan(config, max_candidates=args.max_candidates)
        raw_df = append_early_veto_rows(raw_df, early_state)
    finally:
        telemetry_snapshot = telemetry.snapshot(config)
        telemetry_path = save_telemetry(telemetry, config)
        logger.info(f"Telemetría de datos: {telemetry_path}")
        for health_line in format_health_log(telemetry_snapshot["health"]):
            logger.info(health_line)
        run_trust = assess_run_trust(telemetry_snapshot["health"], config)
        logger.info(
            f"Confianza de ejecución: {run_trust['run_trust_status']} | "
            f"reasons={','.join(run_trust['run_trust_reasons']) or 'none'}"
        )

    if raw_df.empty:
        registry = register_scan_for_backtest(
            raw_df, telemetry_snapshot=telemetry_snapshot, run_trust=run_trust, config=config
        )
        logger.info(f"Registro backtesting vacío: {registry['run_dir']}")
        logger.warning("Scanner terminó sin candidatos ni vetos auditables.")
        return

    df = normalize_scan_with_quote_context(raw_df, config)
    df = attach_run_trust(df, run_trust)
    df["schema_version"] = SCHEMA_VERSION
    assert_scan_schema(df)
    registry = register_scan_for_backtest(
        df, telemetry_snapshot=telemetry_snapshot, run_trust=run_trust, config=config
    )
    logger.info(f"Registro backtesting: {registry['run_dir']}")
    save_reports(df, config, json_out=args.json_out, csv_out=args.csv_out)
    logger.info(f"Scanner completado. Candidatos: {len(df)} | schema={SCHEMA_VERSION}")

    display_cols = [
        "rank", "ticker", "signal", "scanner_stage", "setup_type", "final_score",
        "final_trade_score", "quote_status", "execution_quote_quality", "quote_age_seconds",
        "market_session", "actionable_entry", "actionable_stop", "actionable_target", "rr",
        "reason_summary",
    ]
    available = [column for column in display_cols if column in df.columns]
    print(format_numeric_columns(df[available].head(30), decimals=2).to_string(index=False))


if __name__ == "__main__":
    main()
