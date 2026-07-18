from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from engine.backtest_registry import register_scan_for_backtest


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        result = register_scan_for_backtest(
            pd.DataFrame([{"ticker": "AAPL", "signal": "WATCHLIST"}]),
            telemetry_snapshot={"telemetry_schema_version": "1.1"},
            run_trust={"run_trust_status": "TRUSTED", "run_trust_reasons": []},
            config={"backtesting": {"registry_dir": temp}},
            now_utc=datetime(2026, 7, 20, 13, 20, tzinfo=timezone.utc),
        )
        run_dir = Path(result["run_dir"])
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["market_date_et"] == "2026-07-20"
        assert manifest["scheduled_time_et"] == "09:20"
        assert manifest["rows"] == 1
        assert len(manifest["files"]["scan_json"]["sha256"]) == 64
        assert len((Path(temp) / "index.jsonl").read_text().splitlines()) == 1
        records = json.loads((run_dir / "scan.json").read_text())
        assert records[0]["exchange_timezone"] == "America/New_York"

        empty = register_scan_for_backtest(
            pd.DataFrame(),
            telemetry_snapshot={"health": {"overall_status": "HEALTHY"}},
            run_trust={"run_trust_status": "TRUSTED", "run_trust_reasons": []},
            config={"backtesting": {"registry_dir": temp}},
            now_utc=datetime(2026, 7, 20, 13, 20, 1, tzinfo=timezone.utc),
        )
        empty_dir = Path(empty["run_dir"])
        assert empty["manifest"]["rows"] == 0
        assert json.loads((empty_dir / "scan.json").read_text()) == []
        assert len((Path(temp) / "index.jsonl").read_text().splitlines()) == 2
    print("OK: immutable backtest snapshot, hashes and registry index validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
