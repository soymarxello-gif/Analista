from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from config_loader import load_config
from institutional.context_advisory import ContextAdvisory
from institutional.ingestion import IngestionError, InstitutionalIngestor
from institutional.runtime import InstitutionalRuntime, serialize_signal
from institutional.store import InstitutionalStore


def _write_json(payload: dict[str, object], path: str | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def _legacy(args: argparse.Namespace) -> None:
    """Explicit research-only compatibility path; never selected automatically."""
    from loguru import logger

    import engine.scanner_engine as scanner_engine
    from contracts.scan_schema import SCHEMA_VERSION, assert_scan_schema
    from data.quote_context import normalize_scan_with_quote_context
    from engine.audit_postprocessor import normalize_scan as postprocess_scan
    from engine.report_engine import save_reports

    config = load_config(args.config)
    logger.warning("LEGACY_RESEARCH_ONLY: Yahoo scanner is not the institutional production engine")
    raw = scanner_engine.run_scan(config, max_candidates=args.max_candidates)
    if raw.empty:
        _write_json({"status": "LEGACY_EMPTY", "engine": "legacy_research_only"}, args.json_out)
        return
    frame = normalize_scan_with_quote_context(raw, config)
    frame = postprocess_scan(frame, config)
    frame["schema_version"] = SCHEMA_VERSION
    assert_scan_schema(frame)
    save_reports(frame, config, json_out=args.json_out, csv_out=args.csv_out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analista institutional swing scanner")
    parser.add_argument("--config", default=None)
    parser.add_argument("--db", default="cache/institutional.db")
    parser.add_argument("--as-of", default=None, help="ISO-8601 point-in-time boundary")
    parser.add_argument("--ingest-live", action="store_true", help="Ingest Nasdaq Trader + Alpaca before scanning")
    parser.add_argument("--import-bundle", default=None, help="Import a deterministic institutional JSON bundle")
    parser.add_argument("--symbols", default=None, help="Comma-separated live-ingestion scope; default is full universe")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--engine", choices=("institutional", "legacy"), default="institutional")
    parser.add_argument("--max-candidates", type=int, default=None, help="Legacy compatibility only")
    parser.add_argument("--csv-out", default=None, help="Legacy compatibility only")
    parser.add_argument("--verbose", action="store_true", help="Legacy compatibility only")
    parser.add_argument("--no-intraday", action="store_true", help="Legacy compatibility only")
    args = parser.parse_args()

    if args.engine == "legacy":
        _legacy(args)
        return 0

    as_of = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc)
    config = load_config(args.config)
    store = InstitutionalStore(args.db)
    try:
        ingestion: dict[str, object] | None = None
        ingestor = InstitutionalIngestor(store)
        if args.import_bundle:
            ingestion = ingestor.import_bundle(args.import_bundle).__dict__
        if args.ingest_live:
            symbols = [value.strip().upper() for value in args.symbols.split(",")] if args.symbols else None
            ingestion = ingestor.ingest_live(as_of=as_of, symbols=symbols).__dict__
        result = InstitutionalRuntime(store, configuration=config).run(as_of)
        context_ingestion = None
        if args.ingest_live:
            context_ingestion = ingestor.ingest_context(
                [signal.symbol for signal in result.signals], as_of=as_of
            ).__dict__
        annotated = ContextAdvisory(store).annotate(result.signals, as_of)
        payload = {
            **result.to_dict(),
            "signals": [serialize_signal(signal) for signal in annotated],
            "ingestion": ingestion,
            "context_ingestion": context_ingestion,
            "selection_policy": "TECHNICAL_SETUP_ONLY_CONTEXT_ADVISORY",
            "store_counts": store.table_counts(),
        }
        _write_json(payload, args.json_out)
        return 0 if result.status.startswith("COMPLETED") else 2
    except IngestionError as exc:
        _write_json(
            {"status": "DATA_BLOCKED_INGESTION", "error": str(exc), "store_counts": store.table_counts()},
            args.json_out,
        )
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
