from __future__ import annotations

from datetime import datetime, timedelta, timezone

from institutional.context_advisory import ContextAdvisory
from institutional.features import DiscoveryFeatures
from institutional.models import AssetType, PriceBar, SecurityRecord
from institutional.runtime import InstitutionalRuntime
from institutional.store import InstitutionalStore

NOW = datetime(2026, 7, 21, 20, tzinfo=timezone.utc)


def _bars(symbol: str, offset: float = 0.0) -> list[PriceBar]:
    rows = []
    for index in range(240):
        session = NOW - timedelta(days=239 - index)
        close = 100 + offset + index * 0.035 + ((index % 12) - 6) * 0.35
        rows.append(
            PriceBar(
                symbol,
                session,
                close - 0.3,
                close + 0.8,
                close - 0.8,
                close,
                1_000_000 + index * 1000,
                session + timedelta(hours=4),
                "TEST",
                "SIP",
                True,
            )
        )
    return rows


def _security(symbol: str, asset_type: AssetType = AssetType.COMMON_STOCK) -> SecurityRecord:
    return SecurityRecord(
        symbol,
        asset_type,
        "NASDAQ",
        "USD",
        True,
        NOW - timedelta(days=500),
        None,
        NOW - timedelta(days=500),
        5_000_000_000 if asset_type == AssetType.COMMON_STOCK else None,
        "Technology",
        "Software",
        symbol,
        "TEST",
    )


def test_runtime_is_the_complete_store_to_signal_path_and_is_idempotent():
    store = InstitutionalStore()
    store.put_security_records([_security("AAA"), _security("ETF1", AssetType.ETF), _security("SPY", AssetType.ETF)])
    for symbol, offset in (("AAA", 0.0), ("ETF1", 4.0), ("SPY", -2.0)):
        store.put_price_bars(_bars(symbol, offset))

    first = InstitutionalRuntime(store, configuration={"test": True}).run(NOW)
    second = InstitutionalRuntime(store, configuration={"test": True}).run(NOW)

    assert first.status == "COMPLETED"
    assert first.universe_count == 3
    assert first.discovery_count == 3
    assert first.funnel["discovery_evaluated"] == 3
    assert first.signal_count == len(first.signals)
    assert store.table_counts()["signals"] == first.signal_count
    assert store.table_counts()["outcomes"] == first.signal_count
    assert store.table_counts()["shadow_runs"] == 1
    assert not first.promotion_eligible
    assert "insufficient_oos_closed" in first.promotion_reasons
    assert second.run_id == first.run_id


def test_empty_store_is_explicitly_data_blocked_not_legacy_fallback():
    result = InstitutionalRuntime(InstitutionalStore()).run(NOW)
    assert result.status == "DATA_BLOCKED_EMPTY_UNIVERSE"
    assert result.universe_count == 0
    assert result.signal_count == 0


def test_missing_context_is_an_explicit_warning_and_never_removes_signals():
    store = InstitutionalStore()
    store.put_security_records([_security("AAA"), _security("SPY", AssetType.ETF)])
    store.put_price_bars(_bars("AAA") + _bars("SPY", -2.0))
    result = InstitutionalRuntime(store).run(NOW)

    annotated = ContextAdvisory(store).annotate(result.signals, NOW)

    assert len(annotated) == result.signal_count
    for signal in annotated:
        assert signal.setup_quality > 0
        assert signal.metadata["selection_basis"] == "TECHNICAL_SETUP_ONLY"
        assert signal.metadata["context_warnings"] == [
            "Sin datos macro", "Sin datos fundamentales", "Sin datos de opciones"
        ]
        assert signal.metadata["context_support"]["options"]["status"] == "NO_DATA"


def test_missing_optional_market_relative_strength_does_not_reduce_setup_quality():
    features = DiscoveryFeatures(
        symbol="AAA",
        as_of=NOW,
        close=110.0,
        rsi6=60.0,
        rsi14=55.0,
        ema20=105.0,
        ema50=100.0,
        ema200=90.0,
        relative_volume20=1.6,
        weekly_trend="UP",
        market_rs20_pct=None,
        sector_rs20_pct=None,
        eligible=True,
        reasons=(),
        feature_hash="test",
    )
    assert InstitutionalRuntime._setup_quality(features, breakout=True, pullback=False) == 100.0
