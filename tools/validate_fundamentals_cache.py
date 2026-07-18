from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import fundamentals_client as client


def main() -> int:
    context = client._extract_quote_context(
        {"marketState": "REGULAR", "regularMarketTime": 1_750_000_000},
        fetched_at=datetime(2026, 7, 18, 22, 0, tzinfo=timezone.utc),
    )
    assert context["market_session"] == "REGULAR"
    assert context["quote_timestamp"] == 1_750_000_000.0

    with tempfile.TemporaryDirectory() as directory:
        original = client.CACHE_DIR
        client.CACHE_DIR = Path(directory)
        try:
            legacy = client.CACHE_DIR / "OLD.json"
            legacy.write_text(json.dumps({"ticker": "OLD"}), encoding="utf-8")
            assert client._load_cache("OLD", 60) is None

            client._save_cache("NEW", {"ticker": "NEW"})
            loaded = client._load_cache("NEW", 60)
            assert loaded and loaded["cache_schema_version"] == client.CACHE_SCHEMA_VERSION
        finally:
            client.CACHE_DIR = original

    print("OK: fundamentals cache and Yahoo quote context validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
