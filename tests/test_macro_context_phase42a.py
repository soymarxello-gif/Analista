from __future__ import annotations

import inspect

import pandas as pd

from engine import scanner_engine
from market import market_regime
from universe.equity_validator import validate_universe


def _prices(start: float = 100.0, step: float = 0.1, rows: int = 260) -> pd.DataFrame:
    close = [start + (i * step) for i in range(rows)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [value * 1.01 for value in close],
            "low": [value * 0.99 for value in close],
            "close": close,
            "volume": [1_000_000] * rows,
        },
        index=pd.date_range("2025-01-01", periods=rows, freq="B"),
    )


def _config() -> dict:
    return {
        "benchmarks": {
            "broad_market": "SPY",
            "growth_market": "QQQ",
            "small_caps": "IWM",
            "volatility": "^VIX",
            "us10y": "^TNX",
            "us30y": "^TYX",
            "dollar": "DX-Y.NYB",
            "crude_oil": "CL=F",
            "bitcoin": "BTC-USD",
        },
        "market_regime": {
            "risk_on": {"min_score": 6, "min_candidate_score": 75},
            "neutral": {"min_score": 4, "min_candidate_score": 82},
            "risk_off": {"min_candidate_score": 90, "block_new_longs": True},
            "vix": {"low_risk_below": 16, "high_risk_above": 25},
        },
        "indicators": {
            "moving_averages": [20, 50, 200],
            "rsi": {"period": 14},
            "macd": {"fast": 12, "slow": 26, "signal": 9},
            "atr": {"period": 14},
            "volume": {"avg_period": 20},
            "obv": {"slope_period": 20},
        },
    }


def test_market_regime_downloads_yahoo_macro_symbols_with_freshness(monkeypatch):
    calls: list[dict] = []

    def fake_download(symbols, period="1y", interval="1d"):
        calls.append({"symbols": list(symbols), "period": period, "interval": interval})
        return {
            "SPY": _prices(100, 0.2),
            "QQQ": _prices(120, 0.2),
            "IWM": _prices(80, 0.1),
            "^VIX": _prices(14, 0.0),
            "^TNX": _prices(42, -0.01),
            "^TYX": _prices(45, -0.01),
            "DX-Y.NYB": _prices(105, -0.01),
            "CL=F": _prices(75, 0.01),
            "BTC-USD": _prices(65000, 20),
        }

    monkeypatch.setattr(market_regime, "download_daily_prices", fake_download)

    result = market_regime.classify_market_regime(_config())

    assert calls
    requested = set(calls[0]["symbols"])
    assert {"^TNX", "^TYX", "^VIX", "DX-Y.NYB", "CL=F", "BTC-USD"}.issubset(requested)
    assert result["macro_source"] == "yfinance"
    assert result["macro_data_freshness"] == "DELAYED_OR_EOD"
    assert result["macro_context_status"] == "AVAILABLE"
    assert result["macro_risk_flag"] in {"RISK_ON_SUPPORTIVE", "MIXED_MACRO", "RISK_OFF_PRESSURE"}
    assert "VIX" in result["macro_notes"]
    assert "rates_dollar_placeholder" not in result["diagnostics"]
    assert result["diagnostics"]["macro"]["us30y"]["symbol"] == "^TYX"


def test_macro_download_path_does_not_require_usd_currency_column(monkeypatch):
    def fake_download(symbols, period="1y", interval="1d"):
        assert "currency" not in symbols
        return {
            "SPY": _prices(),
            "QQQ": _prices(),
            "IWM": _prices(),
            "^VIX": _prices(18, 0.0),
            "^TNX": _prices(42, 0.0),
            "^TYX": _prices(45, 0.0),
            "DX-Y.NYB": _prices(104, 0.0),
            "CL=F": _prices(74, 0.0),
            "BTC-USD": _prices(64000, 0.0),
        }

    monkeypatch.setattr(market_regime, "download_daily_prices", fake_download)

    result = market_regime.classify_market_regime(_config())

    assert result["macro_source"] == "yfinance"
    assert result["macro_context_status"] == "AVAILABLE"


def test_validate_universe_rejects_macro_symbols_as_tradables():
    df = pd.DataFrame(
        [
            {"ticker": "^TNX", "quote_type": "EQUITY", "price": 40.0, "market_cap": 2_000_000_000},
            {"ticker": "CL=F", "quote_type": "EQUITY", "price": 80.0, "market_cap": 2_000_000_000},
            {"ticker": "BTC-USD", "quote_type": "EQUITY", "price": 65000.0, "market_cap": 2_000_000_000},
        ]
    )

    out = validate_universe(df, {"filters": {"min_market_cap_usd": 1_000_000_000}})

    assert out.empty


def test_scanner_exposes_macro_context_without_touching_execution_guardrails():
    source = inspect.getsource(scanner_engine.run_scan)

    for field in [
        "macro_context_status",
        "macro_risk_flag",
        "macro_notes",
        "macro_source",
        "macro_timestamp",
        "macro_data_freshness",
    ]:
        assert field in source

    assert '"quote_status": regime.get' not in source
    assert '"execution_quote_quality": regime.get' not in source
    assert '"signal": "TRIGGER_CONFIRMED"' not in source
