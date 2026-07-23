from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from institutional.ingestion import InstitutionalIngestor
from institutional.store import InstitutionalStore

NOW = datetime(2026, 7, 21, 20, tzinfo=timezone.utc)


class FakeClient:
    def request(self, url, **_kwargs):
        if "nasdaqlisted.txt" in url:
            return "Symbol|Security Name|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\nAAA|AAA Corp|N|N|100|N|N\nETF1|ETF One|N|N|100|Y|N\nFile Creation Time: x"
        if "otherlisted.txt" in url:
            return "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\nBADW|Bad Warrants|N|BADW|N|100|N|BADW\n"
        if "/v2/assets" in url:
            return [
                {"symbol": "AAA", "name": "AAA Corp", "exchange": "NASDAQ", "tradable": True},
                {"symbol": "ETF1", "name": "ETF One", "exchange": "NASDAQ", "tradable": True},
            ]
        if "api/screener/stocks" in url:
            return {"data": {"table": {"rows": [{"symbol": "AAA", "marketCap": "$5,000,000,000"}]}}}
        if "/v2/stocks/bars" in url:
            symbols = parse_qs(urlparse(url).query)["symbols"][0].split(",")
            rows = {}
            for symbol in symbols:
                rows[symbol] = []
                for index in range(240):
                    session = NOW - timedelta(days=239 - index)
                    close = 100 + index * 0.03 + ((index % 10) - 5) * 0.4
                    rows[symbol].append(
                        {"t": session.isoformat(), "o": close - 0.2, "h": close + 1, "l": close - 1, "c": close, "v": 1_000_000}
                    )
            return {"bars": rows, "next_page_token": None}
        if "api.stlouisfed.org" in url:
            return {"observations": [{"date": "2026-07-20", "value": "4.25", "realtime_start": "2026-07-21", "realtime_end": "2026-07-21"}]}
        if "company_tickers.json" in url:
            return {"0": {"ticker": "AAA", "cik_str": 1234, "title": "AAA Corp"}}
        if "companyfacts/CIK" in url:
            return {
                "facts": {
                    "us-gaap": {
                        "Revenues": {"units": {"USD": [{"end": "2026-03-31", "filed": "2026-05-01", "val": 100, "accn": "x", "form": "10-Q"}]}},
                        "NetIncomeLoss": {"units": {"USD": [{"end": "2026-03-31", "filed": "2026-05-01", "val": 20, "accn": "x", "form": "10-Q"}]}},
                    }
                }
            }
        if "/v1beta1/options/snapshots/" in url:
            return {
                "snapshots": {
                    "AAA260821C00100000": {"latestQuote": {"bp": 2.0, "ap": 2.2}},
                    "AAA260821P00100000": {"latestQuote": {"bp": 1.8, "ap": 2.0}},
                }
            }
        raise AssertionError(url)


def test_live_ingestion_populates_store_and_excludes_non_common(monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", "key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "secret")
    monkeypatch.setenv("APCA_DATA_FEED", "sip")
    store = InstitutionalStore()
    result = InstitutionalIngestor(store, FakeClient()).ingest_live(as_of=NOW)

    assert result.status == "COMPLETE"
    assert result.securities_stored == 2
    assert result.bars_stored == 480
    assert store.table_counts()["securities"] == 2
    assert len(store.bars_as_of("AAA", NOW)) == 240
    assert store.securities_as_of(NOW)[0].market_cap_usd == 5_000_000_000


def test_late_context_ingestion_is_vintaged_and_does_not_claim_missing_oi(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "fred")
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "analista@example.com")
    monkeypatch.setenv("APCA_API_KEY_ID", "key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "secret")
    monkeypatch.setenv("APCA_OPTIONS_FEED", "opra")
    store = InstitutionalStore()

    result = InstitutionalIngestor(store, FakeClient()).ingest_context(["AAA"], as_of=NOW)

    assert result.fred_series == 7
    assert result.sec_companies == 1
    assert result.option_underlyings == 1
    rows = store.context_as_of(NOW)
    assert len(rows) == 9
    option = next(row for row in rows if row["source"] == "ALPACA_OPTIONS")
    assert option["payload"]["execution_grade"] is True
    assert option["payload"]["open_interest_available"] is False
    assert option["payload"]["dealer_gamma_claimed"] is False
