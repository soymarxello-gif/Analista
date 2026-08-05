from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config_loader import load_config
from data.historical_data_service import configured_local_database
from engine.data_sources.market_data_engine import inspect_market_database
from tools.sync_market_data_engine import sync_market_database


def build_audit(*, sync: bool = True, config: dict | None = None) -> dict:
    config = config or load_config()
    sync_result = sync_market_database(config) if sync else {"status": "SKIPPED"}
    local_db = configured_local_database(config)
    if not local_db.is_absolute():
        local_db = ROOT / local_db
    health = inspect_market_database(local_db)
    status = health.get("status", "FAIL")
    if sync_result.get("status") == "FAIL" and status == "PASS":
        status = "WARN"
    return {
        "status": status,
        "source": "MARKET_DATA_ENGINE_SQLITE",
        "sync": sync_result,
        "health": health,
        "read_only": True,
        "data_freshness": "EOD",
        "changes_trading_signal": False,
        "changes_quote_status": False,
        "changes_execution_quote_quality": False,
    }


def render_markdown(report: dict) -> str:
    health = report.get("health", {}) or {}
    sync = report.get("sync", {}) or {}
    return "\n".join(
        [
            "# Market Data Engine source audit",
            "",
            f"- status: {report.get('status')}",
            f"- source: {report.get('source')}",
            f"- latest_bar_date: {health.get('latest_bar_date')}",
            f"- latest_coverage: {health.get('latest_coverage')}",
            f"- active_assets: {health.get('active_assets')}",
            f"- sectors: {health.get('sectors')}",
            f"- sync_updated: {sync.get('updated', False)}",
            f"- local_db: {health.get('db_path')}",
            "- usage: historical analysis and backtesting only; never execution quality",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-sync", action="store_true")
    parser.add_argument("--json-out", default=str(ROOT / "reports" / "market_data_engine_source_latest.json"))
    parser.add_argument("--markdown-out", default=str(ROOT / "reports" / "market_data_engine_source_latest.md"))
    args = parser.parse_args()
    report = build_audit(sync=not args.no_sync)
    json_path = Path(args.json_out)
    md_path = Path(args.markdown_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
