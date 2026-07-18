from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from engine.options_priority import calculate_options_priority, select_options_tickers


@dataclass
class OptionsPriorityState:
    selected: set[str] = field(default_factory=set)
    priority_by_ticker: dict[str, float] = field(default_factory=dict)
    indicator_cache: dict[int, Any] = field(default_factory=dict)
    score_cache: dict[tuple[str, int], Any] = field(default_factory=dict)


def install_options_priority(scanner_module, config: dict) -> OptionsPriorityState:
    """Install one-run wrappers that rank options requests before full scoring."""
    state = OptionsPriorityState()
    original_download = scanner_module.download_daily_prices
    original_add_indicators = scanner_module.add_all_indicators
    original_score_trend = scanner_module.score_trend
    original_score_volume = scanner_module.score_volume
    original_score_structure = scanner_module.score_structure
    original_score_rr = scanner_module.score_risk_reward
    original_score_momentum = scanner_module.score_momentum
    original_fetch_options = scanner_module.fetch_options_metrics

    def cached_score(name: str, frame, fn, *args):
        key = (name, id(frame))
        if key not in state.score_cache:
            state.score_cache[key] = fn(frame, *args)
        return state.score_cache[key]

    def add_indicators(frame, runtime_config):
        key = id(frame)
        if key not in state.indicator_cache:
            state.indicator_cache[key] = original_add_indicators(frame, runtime_config)
        return state.indicator_cache[key]

    def score_trend(frame, runtime_config):
        return cached_score("trend", frame, original_score_trend, runtime_config)

    def score_volume(frame):
        return cached_score("volume", frame, original_score_volume)

    def score_structure(frame, runtime_config):
        return cached_score("structure", frame, original_score_structure, runtime_config)

    def score_rr(frame, structure, runtime_config):
        key = ("rr", id(frame))
        if key not in state.score_cache:
            state.score_cache[key] = original_score_rr(frame, structure, runtime_config)
        return state.score_cache[key]

    def score_momentum(frame, runtime_config):
        return cached_score("momentum", frame, original_score_momentum, runtime_config)

    def download(tickers, *args, **kwargs):
        raw = original_download(tickers, *args, **kwargs)
        candidates: list[dict] = []
        for ticker in tickers:
            frame = raw.get(ticker)
            if frame is None or frame.empty:
                continue
            indicators = add_indicators(frame, config)
            trend, _ = score_trend(indicators, config)
            volume = score_volume(indicators)
            structure = score_structure(indicators, config)
            rr_data = score_rr(indicators, structure, config)
            momentum = score_momentum(indicators, config)
            candidate = {
                "ticker": ticker,
                "trend_score": trend,
                "volume_score": volume,
                "structure_score": structure.get("structure_score", 0.5),
                "setup_type": structure.get("setup_type"),
                "trigger_confirmed": structure.get("trigger_confirmed", False),
                "rr_score": rr_data.get("rr_score", 0.0),
                "rr": rr_data.get("rr"),
                "momentum_score": momentum,
                "rs_score": 0.5,
                "liquidity_score": 0.5,
            }
            priority = calculate_options_priority(candidate)
            state.priority_by_ticker[str(ticker).upper()] = priority
            candidates.append(candidate)
        options_cfg = config.get("options_flow", {})
        limit = int(options_cfg.get("max_tickers_per_run", 50))
        state.selected = set(select_options_tickers(candidates, limit))
        logger.info(f"Opciones priorizadas: {len(state.selected)}/{len(candidates)} candidatos.")
        return raw

    def fetch_options(ticker: str, spot: float, runtime_config: dict):
        symbol = str(ticker).upper()
        if symbol not in state.selected:
            return {
                "options_data_available": False,
                "options_source": "not_prioritized",
                "options_warning": "candidato fuera del cupo priorizado de opciones",
                "options_priority_selected": False,
                "options_priority_score": state.priority_by_ticker.get(symbol),
            }
        result = original_fetch_options(ticker, spot, runtime_config)
        result["options_priority_selected"] = True
        result["options_priority_score"] = state.priority_by_ticker.get(symbol)
        return result

    scanner_module.download_daily_prices = download
    scanner_module.add_all_indicators = add_indicators
    scanner_module.score_trend = score_trend
    scanner_module.score_volume = score_volume
    scanner_module.score_structure = score_structure
    scanner_module.score_risk_reward = score_rr
    scanner_module.score_momentum = score_momentum
    scanner_module.fetch_options_metrics = fetch_options
    return state
