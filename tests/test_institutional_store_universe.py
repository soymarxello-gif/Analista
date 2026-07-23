from __future__ import annotations

from datetime import datetime, timedelta, timezone

from institutional.models import AssetType, PriceBar, SecurityRecord
from institutional.store import InstitutionalStore
from institutional.universe import UniverseBuilder, UniversePolicy

NOW = datetime(2026, 7, 21, 20, tzinfo=timezone.utc)


def security(symbol: str, *, asset_type: AssetType = AssetType.COMMON_STOCK, cap: float | None = 5e9, available_days: int = 400):
    return SecurityRecord(
        symbol=symbol,
        asset_type=asset_type,
        exchange="NASDAQ",
        currency="USD",
        active=True,
        valid_from=NOW - timedelta(days=500),
        valid_to=None,
        available_at=NOW - timedelta(days=available_days),
        market_cap_usd=cap,
        source="TEST",
    )


def bars(symbol: str, count: int = 240, price: float = 100, volume: int = 1_000_000):
    output = []
    for index in range(count):
        session = NOW - timedelta(days=count - index)
        close = price + index * 0.01
        output.append(
            PriceBar(
                symbol=symbol,
                session=session,
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=volume,
                available_at=session + timedelta(hours=8),
                source="TEST",
                feed="SIP",
                adjusted=True,
            )
        )
    return output


def test_point_in_time_store_hides_future_security_revision_and_future_bar_revision():
    store = InstitutionalStore()
    store.put_security_records(
        [
            security("AAA", cap=2e9),
            SecurityRecord(
                **{
                    **security("AAA", cap=9e9).__dict__,
                    "available_at": NOW + timedelta(days=1),
                }
            ),
        ]
    )
    base = bars("AAA", 1)[0]
    revised = PriceBar(**{**base.__dict__, "close": base.close + 10, "high": base.high + 10, "available_at": NOW + timedelta(days=1)})
    store.put_price_bars([base, revised])
    assert store.securities_as_of(NOW)[0].market_cap_usd == 2e9
    assert store.bars_as_of("AAA", NOW)[0].close == base.close


def test_universe_includes_all_eligible_symbols_without_top_n_and_etf_without_market_cap():
    store = InstitutionalStore()
    records = [security(f"S{index:03}") for index in range(125)]
    records.append(security("ETF1", asset_type=AssetType.ETF, cap=None))
    store.put_security_records(records)
    for record in records:
        store.put_price_bars(bars(record.symbol))
    snapshot = UniverseBuilder(store).build(NOW)
    assert len(snapshot.members) == 126
    assert "ETF1" in {row.security.symbol for row in snapshot.members}
    assert snapshot.funnel["eligible"] == 126


def test_universe_reports_every_exclusion_reason_instead_of_silent_fallback():
    store = InstitutionalStore()
    store.put_security_records([security("SMALL", cap=200e6), security("ILLIQUID")])
    store.put_price_bars(bars("SMALL"))
    store.put_price_bars(bars("ILLIQUID", volume=100))
    snapshot = UniverseBuilder(store, UniversePolicy()).build(NOW)
    assert not snapshot.members
    assert snapshot.funnel["stock_market_cap_below_minimum"] == 1
    assert snapshot.funnel["dollar_volume_below_minimum"] == 1


def test_missing_stock_market_cap_warns_but_does_not_remove_technical_candidate():
    store = InstitutionalStore()
    record = security("UNKNOWNCAP", cap=None)
    store.put_security_records([record])
    store.put_price_bars(bars(record.symbol))

    snapshot = UniverseBuilder(store).build(NOW)

    assert [member.security.symbol for member in snapshot.members] == ["UNKNOWNCAP"]
    assert snapshot.members[0].warnings == ("stock_market_cap_unavailable",)
