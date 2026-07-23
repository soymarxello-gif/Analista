from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from institutional.decision import DecisionEngine, DecisionInput
from institutional.features import DiscoveryEngine
from institutional.models import AssetType, DataStatus, PriceBar, SecurityRecord
from institutional.providers import ProviderPolicy
from institutional.runtime import InstitutionalRuntime
from institutional.store import InstitutionalStore
from institutional.universe import UniverseBuilder


def main() -> None:
    ProviderPolicy.validate()
    with tempfile.TemporaryDirectory() as directory:
        store = InstitutionalStore(Path(directory) / "validation.db")
        now = datetime(2026, 7, 21, 20, tzinfo=timezone.utc)
        store.put_security_records(
            [
                SecurityRecord(
                    symbol="VALID",
                    asset_type=AssetType.COMMON_STOCK,
                    exchange="NASDAQ",
                    currency="USD",
                    active=True,
                    valid_from=now - timedelta(days=500),
                    valid_to=None,
                    available_at=now - timedelta(days=500),
                    market_cap_usd=5_000_000_000,
                    source="VALIDATION",
                )
            ]
        )
        bars = []
        for index in range(240):
            session = now - timedelta(days=239 - index)
            close = 100 + index * 0.035 + (index % 12 - 6) * 0.35
            bars.append(
                PriceBar(
                    symbol="VALID",
                    session=session,
                    open=close - 0.2,
                    high=close + 1,
                    low=close - 1,
                    close=close,
                    volume=1_000_000,
                    available_at=session + timedelta(hours=8),
                    source="VALIDATION",
                    feed="SIP",
                    adjusted=True,
                )
            )
        store.put_price_bars(bars)
        snapshot = UniverseBuilder(store).build(now)
        assert [row.security.symbol for row in snapshot.members] == ["VALID"]
        features = DiscoveryEngine().evaluate("VALID", store.bars_as_of("VALID", now), now)
        assert features.feature_hash
        decision = DecisionEngine().decide(
            DecisionInput(
                setup_valid=True,
                setup_quality=80,
                required_data_statuses=(DataStatus.COMPLETE, DataStatus.COMPLETE),
                market_session_open=False,
                quote_fresh=False,
                risk_plan_valid=True,
            )
        )
        assert decision.state.value == "READY_FOR_NEXT_SESSION"
        runtime = InstitutionalRuntime(store, configuration={"validation": True}).run(now)
        assert runtime.status == "COMPLETED"
        assert runtime.discovery_count == 1
        assert runtime.signal_count == 1
        assert store.table_counts()["signals"] == 1
        assert store.table_counts()["shadow_runs"] == 1
        store.close()
    entrypoint = (ROOT / "run_scanner.py").read_text(encoding="utf-8")
    assert 'default="institutional"' in entrypoint
    assert "runLegacyResearchScan" not in entrypoint
    print("OK institutional production path: ingestion/store -> discovery -> lifecycle -> signal -> shadow")


if __name__ == "__main__":
    main()
