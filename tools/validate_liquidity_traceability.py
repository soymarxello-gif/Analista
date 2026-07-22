from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _stub(module_name: str, **attrs) -> None:
    module = types.ModuleType(module_name)
    for name, value in attrs.items():
        setattr(module, name, value)
    sys.modules[module_name] = module


def _load_scanner_module():
    def noop(*args, **kwargs):
        return None

    _stub("data.screener_client", run_screeners=noop)
    _stub("data.price_client", download_daily_prices=noop)
    _stub("data.fundamentals_client", enrich_metadata=noop)
    _stub("data.options_client", fetch_options_metrics=noop)
    _stub("universe.equity_validator", validate_universe=noop)
    _stub("universe.liquidity_filter", compute_liquidity=noop)
    _stub("indicators.pipeline", add_all_indicators=noop)
    _stub("market.market_regime", classify_market_regime=noop)
    _stub("market.sector_rotation", calculate_sector_rotation=noop)
    _stub("scoring.relative_strength", add_relative_strength_scores=noop)
    _stub("scoring.trend_score", score_trend=noop)
    _stub("scoring.volume_score", score_volume=noop)
    _stub("scoring.structure_score", score_structure=noop)
    _stub("scoring.risk_reward_score", score_risk_reward=noop)
    _stub("scoring.momentum_score", score_momentum=noop)
    _stub("scoring.fundamental_score", score_fundamentals=noop)
    _stub("scoring.options_score", score_options_flow=noop)
    _stub("scoring.final_score", calculate_final_score=noop)
    _stub("scoring.signal_classifier", classify_signal=noop)

    path = ROOT / "engine" / "scanner_engine.py"
    spec = importlib.util.spec_from_file_location("scanner_engine_validation", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = _load_scanner_module()
    metadata = pd.Series(
        {
            "ticker": "TEST",
            "company": "Test Co",
            "quote_type": "EQUITY",
            "market_cap": 5_000_000_000,
            "price": 42.0,
            "liquidity_pass": False,
            "liquidity_score": 0.2,
            "liquidity_warning": "dollar_volume_below_min",
            "quote_timestamp": "2026-07-18T20:00:00Z",
            "market_session": "REGULAR",
            "quote_timestamp_source": "regularMarketTime",
        }
    )
    row = module._liquidity_veto_row(metadata, {"regime": "NEUTRAL"})
    assert row["signal"] == "VETO"
    assert row["veto_reasons"] == "liquidity_fail"
    assert row["scanner_stage"] == "LIQUIDITY_VETO"
    assert row["quote_timestamp"] == "2026-07-18T20:00:00Z"
    assert row["market_session"] == "REGULAR"
    assert row["entry"] is None and row["stop"] is None and row["target"] is None

    source = (ROOT / "engine" / "scanner_engine.py").read_text(encoding="utf-8")
    assert 'meta = meta[meta["liquidity_pass"] == True]' not in source
    assert "rows + veto_rows" in source
    print("OK: liquidity failures remain auditable VETO rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
