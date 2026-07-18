from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.early_filter_runtime import (
    append_early_veto_rows,
    hard_filter_reasons,
    install_early_filters,
)


def main() -> int:
    config = {"filters": {"min_price": 10, "min_market_cap_usd": 1_500_000_000}}

    assert hard_filter_reasons(
        {"ticker": "LOW", "price": 8, "market_cap": 5_000_000_000}, config
    ) == ["price_below_min"]
    assert hard_filter_reasons(
        {"ticker": "SMALL", "price": 20, "market_cap": 500_000_000}, config
    ) == ["market_cap_below_min"]
    assert hard_filter_reasons(
        {
            "ticker": "ETF",
            "price": 50,
            "market_cap": 9_000_000_000,
            "universe_veto_reasons": "non_tradable_instrument",
        },
        config,
    ) == ["non_tradable_instrument"]

    calls: list[list[str]] = []

    def enrich(df, _config):
        return pd.DataFrame(
            [
                {"ticker": "PASS", "price": 50, "market_cap": 5_000_000_000, "quote_type": "EQUITY"},
                {"ticker": "LOW", "price": 5, "market_cap": 5_000_000_000, "quote_type": "EQUITY"},
            ]
        )

    def download(tickers, *args, **kwargs):
        calls.append(list(tickers))
        return {"PASS": pd.DataFrame()}

    scanner = types.SimpleNamespace(enrich_metadata=enrich, download_daily_prices=download)
    state = install_early_filters(scanner, config)
    eligible = scanner.enrich_metadata(pd.DataFrame([{"ticker": "X"}]), config)
    assert eligible["ticker"].tolist() == ["PASS"]
    assert state.hard_rejected[0]["ticker"] == "LOW"

    scanner.download_daily_prices(["PASS"])
    assert calls == [["PASS"]]
    assert state.no_history[0]["ticker"] == "PASS"

    out = append_early_veto_rows(pd.DataFrame(), state)
    assert set(out["scanner_stage"]) == {"HARD_FILTER_VETO", "NO_HISTORY_VETO"}
    assert set(out["signal"]) == {"VETO"}
    assert out["entry"].isna().all()

    print("OK: hard filters precede history downloads and missing history stays auditable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
