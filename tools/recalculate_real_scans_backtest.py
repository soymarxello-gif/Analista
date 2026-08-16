from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yfinance as yf

BACKTEST_VERSION = "backtest-fill-3"
WALK_FORWARD_VERSION = "walk-forward-statistics-1"
RANKING_PROMOTION_VERSION = "ranking-promotion-1"
PRICE_SOURCE = "Yahoo Finance / yfinance"
EXPIRATION_SESSIONS = 20
ENTRY_SLIPPAGE_BPS = 5.0
EXIT_SLIPPAGE_BPS = 5.0

# Stratified across the immutable registry: earliest, peak-universe period,
# first v1.1/config transition, August follow-up, and latest available scan.
DEFAULT_RUN_IDS = (
    "20260723T153344068192Z",
    "20260728T154332907566Z",
    "20260730T152954356054Z",
    "20260804T154628297689Z",
    "20260813T144009963304Z",
)


@dataclass(frozen=True)
class Bar:
    session: date
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Contract:
    observation_id: str
    run_id: str
    ticker: str
    decision_date: date
    decision_timestamp_utc: int
    setup_type: str
    macro_regime: str
    sector: str
    signal: str
    legacy_rank: int
    proposed_rank: int
    p0_valid: bool
    trigger_price: float
    maximum_entry: float
    stop_price: float
    target_price: float
    expiration_sessions: int = EXPIRATION_SESSIONS


@dataclass
class Outcome:
    observation_id: str
    run_id: str
    ticker: str
    decision_date: str
    setup_type: str
    macro_regime: str
    sector: str
    final_signal: str
    legacy_rank: int
    proposed_rank: int
    p0_valid: bool
    eligible_for_contract: bool
    engine_version: str = BACKTEST_VERSION
    activated: bool = False
    status: str = "NOT_TRIGGERED"
    entry_session: str | None = None
    entry_fill: float | None = None
    exit_session: str | None = None
    exit_fill: float | None = None
    exit_reason: str = "NONE"
    holding_sessions: int = 0
    trade_return_pct: float | None = None
    trade_return_r: float | None = None
    mfe_pct: float | None = None
    mae_pct: float | None = None
    ambiguous_same_bar: bool = False
    observed_sessions: int = 0


def _num(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _num(value)
    return int(number) if number is not None else None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y", "pass"}


def _text(value: Any, default: str = "UNKNOWN") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    text = str(value).strip()
    return text if text else default


def _first_number(row: pd.Series, names: Iterable[str]) -> float | None:
    for name in names:
        if name in row.index:
            value = _num(row.get(name))
            if value is not None:
                return value
    return None


def _round2(value: float | None) -> float | None:
    return None if value is None else round(value + 0.0, 2)


def _buy_fill(price: float) -> float:
    return price * (1.0 + ENTRY_SLIPPAGE_BPS / 10_000.0)


def _sell_fill(price: float) -> float:
    return price * (1.0 - EXIT_SLIPPAGE_BPS / 10_000.0)


def _valid_levels(entry: float | None, stop: float | None, target: float | None) -> bool:
    return (
        entry is not None
        and stop is not None
        and target is not None
        and entry > 0
        and stop > 0
        and target > 0
        and entry > stop
        and target > entry
    )


def row_to_contract(row: pd.Series, run_id: str, decision_date: date) -> Contract | None:
    signal = _text(row.get("signal"), "UNKNOWN").upper()
    if signal not in {"READY_WAIT_TRIGGER", "TRIGGER_CONFIRMED"}:
        return None

    # Immutable desktop scans predate SignalContractEntity.maximumEntry. Do not infer a
    # missing chase allowance. The stored entry becomes the raw trigger and the maximum
    # effective fill is only widened by the engine's mandatory 5 bps entry slippage.
    entry = _first_number(row, ("actionable_entry", "theoretical_entry", "entry"))
    stop = _first_number(row, ("actionable_stop", "theoretical_stop", "stop"))
    target = _first_number(row, ("actionable_target", "theoretical_target", "target"))
    if not _valid_levels(entry, stop, target):
        return None

    legacy_rank = _int(row.get("legacy_rank")) or _int(row.get("rank"))
    proposed_rank = _int(row.get("trade_rank")) or legacy_rank
    if legacy_rank is None or proposed_rank is None:
        return None

    generated = pd.to_datetime(row.get("generated_at_utc"), utc=True, errors="coerce")
    if pd.isna(generated):
        generated = pd.Timestamp(datetime.combine(decision_date, datetime.min.time(), tzinfo=timezone.utc))
    decision_timestamp_utc = int(generated.timestamp() * 1000)
    trust = _text(row.get("run_trust_status"), "UNKNOWN").upper()

    return Contract(
        observation_id=f"{run_id}-{_text(row.get('ticker'))}",
        run_id=run_id,
        ticker=_text(row.get("ticker")),
        decision_date=decision_date,
        decision_timestamp_utc=decision_timestamp_utc,
        setup_type=_text(row.get("setup_type")),
        macro_regime=_text(row.get("market_regime")),
        sector=_text(row.get("sector")),
        signal=signal,
        legacy_rank=legacy_rank,
        proposed_rank=proposed_rank,
        p0_valid=trust == "TRUSTED",
        trigger_price=float(entry),
        maximum_entry=float(entry) * (1.0 + ENTRY_SLIPPAGE_BPS / 10_000.0),
        stop_price=float(stop),
        target_price=float(target),
    )


def evaluate_backtest(contract: Contract, bars: list[Bar]) -> Outcome:
    future = [bar for bar in bars if bar.session > contract.decision_date][: contract.expiration_sessions]
    base = Outcome(
        observation_id=contract.observation_id,
        run_id=contract.run_id,
        ticker=contract.ticker,
        decision_date=contract.decision_date.isoformat(),
        setup_type=contract.setup_type,
        macro_regime=contract.macro_regime,
        sector=contract.sector,
        final_signal=contract.signal,
        legacy_rank=contract.legacy_rank,
        proposed_rank=contract.proposed_rank,
        p0_valid=contract.p0_valid,
        eligible_for_contract=True,
        observed_sessions=len(future),
    )

    entry_index: int | None = None
    entry_fill: float | None = None
    triggered_at_open = False
    for index, bar in enumerate(future):
        if bar.open > contract.maximum_entry:
            continue
        if bar.high < contract.trigger_price:
            continue
        raw_fill = max(bar.open, contract.trigger_price)
        effective_fill = _buy_fill(raw_fill)
        if effective_fill > contract.maximum_entry:
            continue
        entry_index = index
        entry_fill = effective_fill
        triggered_at_open = bar.open >= contract.trigger_price
        break

    if entry_index is None or entry_fill is None:
        base.holding_sessions = len(future)
        base.status = "EXPIRED_NOT_TRIGGERED" if len(future) >= contract.expiration_sessions else "NOT_TRIGGERED"
        return base

    active = future[entry_index:]
    exit_index: int | None = None
    exit_fill: float | None = None
    exit_reason = "NONE"
    stop_hit = False
    target_hit = False
    ambiguous = False

    for index, bar in enumerate(active):
        first_bar = index == 0
        touches_stop = bar.low <= contract.stop_price
        touches_target = bar.high >= contract.target_price
        if first_bar and not triggered_at_open and touches_stop:
            exit_index = index
            exit_reason = "AMBIGUOUS_SAME_BAR" if touches_target else "AMBIGUOUS_ENTRY_STOP_SAME_BAR"
            stop_hit = True
            target_hit = touches_target
            ambiguous = True
            break
        if bar.open <= contract.stop_price:
            exit_index, exit_fill, exit_reason, stop_hit = index, _sell_fill(bar.open), "GAP_STOP", True
            break
        if bar.open >= contract.target_price:
            exit_index, exit_fill, exit_reason, target_hit = index, _sell_fill(bar.open), "GAP_TARGET", True
            break
        if touches_stop and touches_target:
            exit_index, exit_reason, stop_hit, target_hit, ambiguous = index, "AMBIGUOUS_SAME_BAR", True, True, True
            break
        if touches_stop:
            exit_index, exit_fill, exit_reason, stop_hit = index, _sell_fill(contract.stop_price), "STOP", True
            break
        if touches_target:
            exit_index, exit_fill, exit_reason, target_hit = index, _sell_fill(contract.target_price), "TARGET", True
            break

    if exit_index is None and len(future) >= contract.expiration_sessions and active:
        exit_index = len(active) - 1
        exit_fill = _sell_fill(active[-1].close)
        exit_reason = "EXPIRED"

    observed = active[: (exit_index + 1) if exit_index is not None else len(active)]
    if not triggered_at_open and exit_index == 0 and ambiguous:
        mfe = None
        mae = None
    else:
        mfe = max(((bar.high / entry_fill - 1.0) * 100.0 for bar in observed), default=None)
        if triggered_at_open:
            mae = min(((bar.low / entry_fill - 1.0) * 100.0 for bar in observed), default=None)
        else:
            later = [((bar.low / entry_fill - 1.0) * 100.0) for bar in observed[1:]]
            mae = min(0.0, min(later) if later else 0.0)

    base.activated = True
    base.entry_session = active[0].session.isoformat()
    base.entry_fill = _round2(entry_fill)
    base.exit_reason = exit_reason
    base.holding_sessions = len(observed)
    base.mfe_pct = _round2(mfe)
    base.mae_pct = _round2(mae)
    base.ambiguous_same_bar = ambiguous

    if exit_index is not None:
        base.exit_session = active[exit_index].session.isoformat()
        base.exit_fill = _round2(exit_fill)
    if exit_fill is not None:
        base.trade_return_pct = _round2((exit_fill / entry_fill - 1.0) * 100.0)
        risk_per_share = entry_fill - contract.stop_price
        if risk_per_share > 0:
            base.trade_return_r = _round2((exit_fill - entry_fill) / risk_per_share)

    if ambiguous:
        base.status = "CLOSED_AMBIGUOUS"
    elif exit_reason in {"TARGET", "GAP_TARGET"}:
        base.status = "CLOSED_TARGET"
    elif exit_reason in {"STOP", "GAP_STOP"}:
        base.status = "CLOSED_STOP"
    elif exit_reason == "EXPIRED":
        base.status = "CLOSED_EXPIRED"
    else:
        base.status = "OPEN"
    return base


def _ticker_alias(ticker: str) -> str:
    # Yahoo uses '-' for US class shares that are often stored with '.' by screeners.
    return ticker.replace(".", "-")


def fetch_yahoo_history(tickers: list[str], start: date, end: date) -> tuple[dict[str, list[Bar]], dict[str, Any]]:
    histories: dict[str, list[Bar]] = {}
    aliases = {ticker: _ticker_alias(ticker) for ticker in tickers}
    reverse = {alias: original for original, alias in aliases.items()}
    failures: list[str] = []

    unique_aliases = sorted(set(aliases.values()))
    for offset in range(0, len(unique_aliases), 50):
        chunk = unique_aliases[offset : offset + 50]
        try:
            frame = yf.download(
                tickers=chunk,
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=False,
                actions=False,
                progress=False,
                threads=True,
                group_by="ticker",
            )
        except Exception:
            failures.extend(reverse.get(ticker, ticker) for ticker in chunk)
            continue

        for alias in chunk:
            original = reverse.get(alias, alias)
            try:
                if len(chunk) == 1 and not isinstance(frame.columns, pd.MultiIndex):
                    sub = frame
                elif isinstance(frame.columns, pd.MultiIndex) and alias in frame.columns.get_level_values(0):
                    sub = frame[alias]
                else:
                    failures.append(original)
                    continue
                bars: list[Bar] = []
                for index, row in sub.iterrows():
                    o, h, l, c = (_num(row.get(name)) for name in ("Open", "High", "Low", "Close"))
                    if None in {o, h, l, c}:
                        continue
                    session = pd.Timestamp(index).date()
                    bars.append(Bar(session=session, open=float(o), high=float(h), low=float(l), close=float(c)))
                if bars:
                    histories[original] = bars
                else:
                    failures.append(original)
            except Exception:
                failures.append(original)

    failures = sorted(set(ticker for ticker in failures if ticker not in histories))
    return histories, {
        "source": PRICE_SOURCE,
        "requested_tickers": len(tickers),
        "received_tickers": len(histories),
        "missing_tickers": failures,
        "coverage_pct": round((len(histories) / len(tickers) * 100.0), 2) if tickers else 100.0,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
    }


def _metrics(rows: list[Outcome]) -> dict[str, Any]:
    activated = [row for row in rows if row.activated]
    closed = [row for row in activated if row.trade_return_r is not None]
    returns = [row.trade_return_r for row in closed if row.trade_return_r is not None]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    cumulative = peak = max_drawdown = 0.0
    for value in returns:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)

    def avg(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    def median(values: list[float]) -> float | None:
        if not values:
            return None
        sorted_values = sorted(values)
        middle = len(sorted_values) // 2
        value = sorted_values[middle] if len(sorted_values) % 2 else (sorted_values[middle - 1] + sorted_values[middle]) / 2
        return round(value, 4)

    return {
        "total_observations": len(rows),
        "activated": len(activated),
        "closed_with_return": len(closed),
        "expectancy_r": avg(returns),
        "median_r": median(returns),
        "hit_rate_pct": round(sum(value > 0 for value in returns) * 100.0 / len(returns), 2) if returns else None,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 4) if losses else None,
        "maximum_drawdown_r": round(max_drawdown, 4) if returns else None,
        "average_mfe_pct": avg([row.mfe_pct for row in activated if row.mfe_pct is not None]),
        "average_mae_pct": avg([row.mae_pct for row in activated if row.mae_pct is not None]),
        "average_holding_sessions": avg([float(row.holding_sessions) for row in activated]),
    }


def walk_forward(outcomes: list[Outcome]) -> dict[str, Any]:
    ordered = sorted(outcomes, key=lambda row: (row.decision_date, row.observation_id))
    training_end = math.floor(len(ordered) * 0.60)
    validation_end = training_end + math.floor(len(ordered) * 0.20)
    partitions = {
        "training": ordered[:training_end],
        "validation": ordered[training_end:validation_end],
        "test": ordered[validation_end:],
    }
    test = partitions["test"]
    reasons: list[str] = []
    test_closed = sum(row.activated and row.trade_return_r is not None for row in test)
    if test_closed < 100:
        reasons.append("insufficient_out_of_sample_closed")
    if any(not row.p0_valid for row in test):
        reasons.append("p0_regression_present")

    closed_by_setup: dict[str, int] = {}
    for row in test:
        if row.activated and row.trade_return_r is not None:
            key = row.setup_type.strip().upper() or "UNKNOWN"
            closed_by_setup[key] = closed_by_setup.get(key, 0) + 1
    dominant_minimum = test_closed * 0.20
    dominant = {key: count for key, count in closed_by_setup.items() if count >= dominant_minimum}
    if not dominant:
        reasons.append("no_dominant_setup_in_test")
    for key, count in sorted(dominant.items()):
        if count < 30:
            reasons.append(f"insufficient_dominant_setup:{key}")

    regimes = {
        row.macro_regime.strip().upper()
        for row in test
        if row.activated and row.trade_return_r is not None and row.macro_regime.strip().upper() != "UNKNOWN"
    }
    if len(regimes) < 2:
        reasons.append("insufficient_market_regimes")

    def partition_payload(rows: list[Outcome]) -> dict[str, Any]:
        return {
            "first_decision_date": rows[0].decision_date if rows else None,
            "last_decision_date": rows[-1].decision_date if rows else None,
            "metrics": _metrics(rows),
        }

    def grouped(selector: str) -> list[dict[str, Any]]:
        groups: dict[str, list[Outcome]] = {}
        for row in test:
            key = str(getattr(row, selector)).strip().upper() or "UNKNOWN"
            groups.setdefault(key, []).append(row)
        return [
            {"key": key, "metrics": _metrics(values)}
            for key, values in sorted(groups.items(), key=lambda item: (-_metrics(item[1])["closed_with_return"], item[0]))
        ]

    return {
        "engine_version": WALK_FORWARD_VERSION,
        "partition_config": {"training_pct": 0.60, "validation_pct": 0.20, "test_pct": 0.20},
        "thresholds": {
            "minimum_out_of_sample_closed": 100,
            "minimum_dominant_setup_closed": 30,
            "dominant_setup_min_share_pct": 20.0,
            "minimum_distinct_regimes": 2,
        },
        "training": partition_payload(partitions["training"]),
        "validation": partition_payload(partitions["validation"]),
        "test": partition_payload(test),
        "test_by_setup": grouped("setup_type"),
        "test_by_regime": grouped("macro_regime"),
        "test_by_sector": grouped("sector"),
        "eligible_for_ranking_promotion": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
    }


def _ranking_metrics(rows: list[Outcome]) -> dict[str, Any]:
    closed = [row for row in rows if row.trade_return_r is not None]
    returns = [row.trade_return_r for row in closed if row.trade_return_r is not None]
    cumulative = peak = max_drawdown = 0.0
    for value in returns:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)

    def avg(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    return {
        "selected": len(rows),
        "closed": len(closed),
        "expectancy_r": _round2(avg(returns)),
        "hit_rate_pct": _round2(sum(value > 0 for value in returns) * 100.0 / len(returns)) if returns else None,
        "maximum_drawdown_r": _round2(max_drawdown) if returns else None,
        "average_mfe_pct": _round2(avg([row.mfe_pct for row in closed if row.mfe_pct is not None])),
        "average_mae_pct": _round2(avg([row.mae_pct for row in closed if row.mae_pct is not None])),
        "invalid_selections": sum((not row.eligible_for_contract) or (not row.p0_valid) or row.final_signal in {"VETO", "AVOID"} for row in rows),
    }


def ranking_promotion(outcomes: list[Outcome], walk_forward_passed: bool, top_k: int = 5) -> dict[str, Any]:
    by_run: dict[str, list[Outcome]] = {}
    for row in outcomes:
        by_run.setdefault(row.run_id, []).append(row)
    legacy_rows = [row for rows in by_run.values() for row in sorted(rows, key=lambda item: item.legacy_rank)[:top_k]]
    proposed_rows = [row for rows in by_run.values() for row in sorted(rows, key=lambda item: item.proposed_rank)[:top_k]]
    legacy = _ranking_metrics(sorted(legacy_rows, key=lambda row: (row.decision_date, row.run_id, row.legacy_rank)))
    proposed = _ranking_metrics(sorted(proposed_rows, key=lambda row: (row.decision_date, row.run_id, row.proposed_rank)))

    def diff(first: float | None, second: float | None) -> float | None:
        return None if first is None or second is None else round(first - second, 4)

    def deterioration(first: float | None, second: float | None) -> float | None:
        if first is None or second is None:
            return None
        if second == 0:
            return 0.0 if first == 0 else math.inf
        return round((first / second - 1.0) * 100.0, 4)

    expectancy_improvement = diff(proposed["expectancy_r"], legacy["expectancy_r"])
    drawdown_deterioration = deterioration(proposed["maximum_drawdown_r"], legacy["maximum_drawdown_r"])
    mfe_change = diff(proposed["average_mfe_pct"], legacy["average_mfe_pct"])
    legacy_mae = legacy["average_mae_pct"]
    proposed_mae = proposed["average_mae_pct"]
    if legacy_mae is None or proposed_mae is None:
        mae_deterioration = None
    elif abs(legacy_mae) == 0:
        mae_deterioration = 0.0 if abs(proposed_mae) == 0 else math.inf
    else:
        mae_deterioration = round((abs(proposed_mae) / abs(legacy_mae) - 1.0) * 100.0, 4)
    regimes = {
        row.macro_regime.strip().upper()
        for row in proposed_rows
        if row.trade_return_r is not None and row.macro_regime.strip().upper() != "UNKNOWN"
    }

    reasons: list[str] = []
    if not walk_forward_passed:
        reasons.append("walk_forward_gate_failed")
    if legacy["closed"] < 100:
        reasons.append("insufficient_legacy_closed_sample")
    if proposed["closed"] < 100:
        reasons.append("insufficient_proposed_closed_sample")
    if proposed["invalid_selections"] > 0:
        reasons.append("proposed_ranking_selects_invalid_candidates")
    if expectancy_improvement is None or expectancy_improvement < 0.10:
        reasons.append("expectancy_improvement_below_threshold")
    if drawdown_deterioration is None or drawdown_deterioration > 10.0:
        reasons.append("drawdown_deterioration_above_threshold")
    if mfe_change is None or mfe_change < -0.25:
        reasons.append("mfe_deterioration_above_threshold")
    if mae_deterioration is None or mae_deterioration > 10.0:
        reasons.append("mae_deterioration_above_threshold")
    if len(regimes) < 2:
        reasons.append("insufficient_proposed_regime_breadth")

    return {
        "engine_version": RANKING_PROMOTION_VERSION,
        "top_k": top_k,
        "legacy": legacy,
        "proposed": proposed,
        "expectancy_improvement_r": expectancy_improvement,
        "drawdown_deterioration_pct": drawdown_deterioration,
        "mfe_change_pct_points": mfe_change,
        "mae_deterioration_pct": mae_deterioration,
        "distinct_proposed_regimes": len(regimes),
        "status": "PROMOTE_PROPOSED_RANKING" if not reasons else "KEEP_LEGACY_ORDER",
        "reasons": list(dict.fromkeys(reasons)),
    }


def audit_run(df: pd.DataFrame, run_id: str, sampled: pd.DataFrame) -> dict[str, Any]:
    signal_counts = df.get("signal", pd.Series(dtype=str)).fillna("UNKNOWN").astype(str).value_counts().to_dict()
    quote_quality = df.get("execution_quote_quality", pd.Series(dtype=str)).fillna("UNKNOWN").astype(str).value_counts().to_dict()
    validation = df.get("validation_status", pd.Series(dtype=str)).fillna("UNKNOWN").astype(str).value_counts().to_dict()
    trust = df.get("run_trust_status", pd.Series(dtype=str)).fillna("UNKNOWN").astype(str).value_counts().to_dict()
    levels = pd.DataFrame(
        {
            "entry": pd.to_numeric(df.get("theoretical_entry", df.get("entry")), errors="coerce"),
            "stop": pd.to_numeric(df.get("theoretical_stop", df.get("stop")), errors="coerce"),
            "target": pd.to_numeric(df.get("theoretical_target", df.get("target")), errors="coerce"),
        }
    )
    complete_levels = levels.notna().all(axis=1).sum() if not levels.empty else 0
    return {
        "run_id": run_id,
        "market_date_et": _text(df.iloc[0].get("market_date_et"), "UNKNOWN") if not df.empty else "UNKNOWN",
        "rows": int(len(df)),
        "sampled_rows": int(len(sampled)),
        "signals": {str(key): int(value) for key, value in signal_counts.items()},
        "execution_quote_quality": {str(key): int(value) for key, value in quote_quality.items()},
        "validation_status": {str(key): int(value) for key, value in validation.items()},
        "run_trust_status": {str(key): int(value) for key, value in trust.items()},
        "complete_theoretical_levels": int(complete_levels),
        "manual_review_required": bool(df.get("run_manual_review_required", pd.Series([False])).map(_bool).any()),
        "critical_essential_sources": sorted(
            set(
                item.strip()
                for value in df.get("critical_essential_sources", pd.Series(dtype=str)).dropna().astype(str)
                for item in value.split(";")
                if item.strip()
            )
        ),
    }


def make_markdown(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    wf = payload["walk_forward"]
    rp = payload["ranking_promotion"]
    source = payload["price_data"]
    lines = [
        "# Real scan audit and backtest recalculation",
        "",
        f"- Backtest engine: `{BACKTEST_VERSION}`",
        f"- Price source: {PRICE_SOURCE}",
        f"- Runs sampled: {len(payload['runs'])}",
        f"- Rows audited: {agg['rows_audited']}",
        f"- Rows sampled for outcome recalculation: {agg['rows_sampled']}",
        f"- Diagnostic contracts: {agg['diagnostic_contracts']}",
        f"- Yahoo ticker coverage: {source['received_tickers']}/{source['requested_tickers']} ({source['coverage_pct']}%)",
        f"- Activated: {agg['activated']}",
        f"- Closed with return: {agg['closed_with_return']}",
        f"- Open/not triggered: {agg['unresolved']}",
        "",
        "## Run audit",
        "",
        "| Run | Date | Rows | Sample | TRIGGER | READY | Trust | Critical source |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for run in payload["runs"]:
        lines.append(
            f"| {run['run_id']} | {run['market_date_et']} | {run['rows']} | {run['sampled_rows']} | "
            f"{run['signals'].get('TRIGGER_CONFIRMED', 0)} | {run['signals'].get('READY_WAIT_TRIGGER', 0)} | "
            f"{','.join(run['run_trust_status'])} | {','.join(run['critical_essential_sources']) or '—'} |"
        )
    lines += [
        "",
        "## Walk-forward",
        "",
        f"- Gate: **{'PASS' if wf['eligible_for_ranking_promotion'] else 'FAIL'}**",
        f"- OOS closed: {wf['test']['metrics']['closed_with_return']}",
        f"- OOS expectancy: {wf['test']['metrics']['expectancy_r']} R",
        f"- Reasons: {', '.join(wf['reasons']) or 'none'}",
        "",
        "## Ranking promotion",
        "",
        f"- Status: **{rp['status']}**",
        f"- Legacy closed: {rp['legacy']['closed']} · expectancy {rp['legacy']['expectancy_r']} R",
        f"- Proposed closed: {rp['proposed']['closed']} · expectancy {rp['proposed']['expectancy_r']} R",
        f"- Expectancy improvement: {rp['expectancy_improvement_r']} R",
        f"- Reasons: {', '.join(rp['reasons']) or 'none'}",
        "",
        "## Interpretation constraints",
        "",
        "All sampled immutable runs retain their recorded run-trust/P0 state. UNUSABLE runs are not retroactively upgraded.",
        "The historical desktop CSV schema has no maximumEntry. The compatibility adapter uses stored entry as the raw trigger and permits only the mandatory 5 bps slippage as maximum effective fill; it does not invent a chase allowance.",
        "Daily OHLC bars strictly after the scan date are used, so the scan-day bar is excluded to avoid intraday look-ahead.",
        "Open or not-yet-expired contracts remain unresolved and do not contribute a realized R.",
    ]
    return "\n".join(lines) + "\n"


def run_audit(repo_root: Path, output_dir: Path, run_ids: tuple[str, ...], max_rows_per_run: int) -> dict[str, Any]:
    frames: list[tuple[str, pd.DataFrame, pd.DataFrame]] = []
    all_contracts: list[Contract] = []
    ranking_rows: list[Outcome] = []
    run_audits: list[dict[str, Any]] = []

    for run_id in run_ids:
        scan_path = repo_root / "backtesting" / "runs" / run_id / "scan.csv"
        if not scan_path.exists():
            raise FileNotFoundError(scan_path)
        df = pd.read_csv(scan_path, low_memory=False)
        df = df.sort_values("rank", kind="stable") if "rank" in df.columns else df
        sampled = df.head(max_rows_per_run).copy()
        run_audits.append(audit_run(df, run_id, sampled))
        frames.append((run_id, df, sampled))

        market_date = pd.to_datetime(sampled["market_date_et"].iloc[0], errors="coerce").date()
        for _, row in sampled.iterrows():
            contract = row_to_contract(row, run_id, market_date)
            if contract is not None:
                all_contracts.append(contract)

    tickers = sorted({contract.ticker for contract in all_contracts})
    earliest = min(contract.decision_date for contract in all_contracts) + timedelta(days=1)
    end = datetime.now(timezone.utc).date() + timedelta(days=2)
    histories, price_audit = fetch_yahoo_history(tickers, earliest, end)

    outcomes_by_id: dict[str, Outcome] = {}
    for contract in all_contracts:
        bars = histories.get(contract.ticker, [])
        outcomes_by_id[contract.observation_id] = evaluate_backtest(contract, bars)

    # RankingPromotionEngine operates on all ranked rows; rows that were not contract-eligible
    # remain present with a null outcome so invalid top-K selections are visible.
    for run_id, _, sampled in frames:
        market_date = pd.to_datetime(sampled["market_date_et"].iloc[0], errors="coerce").date()
        for _, row in sampled.iterrows():
            ticker = _text(row.get("ticker"))
            observation_id = f"{run_id}-{ticker}"
            existing = outcomes_by_id.get(observation_id)
            if existing is not None:
                ranking_rows.append(existing)
                continue
            legacy_rank = _int(row.get("legacy_rank")) or _int(row.get("rank")) or 999999
            proposed_rank = _int(row.get("trade_rank")) or legacy_rank
            trust = _text(row.get("run_trust_status"), "UNKNOWN").upper()
            ranking_rows.append(
                Outcome(
                    observation_id=observation_id,
                    run_id=run_id,
                    ticker=ticker,
                    decision_date=market_date.isoformat(),
                    setup_type=_text(row.get("setup_type")),
                    macro_regime=_text(row.get("market_regime")),
                    sector=_text(row.get("sector")),
                    final_signal=_text(row.get("signal"), "UNKNOWN").upper(),
                    legacy_rank=legacy_rank,
                    proposed_rank=proposed_rank,
                    p0_valid=trust == "TRUSTED",
                    eligible_for_contract=False,
                )
            )

    contract_outcomes = list(outcomes_by_id.values())
    wf = walk_forward(contract_outcomes)
    ranking = ranking_promotion(ranking_rows, wf["eligible_for_ranking_promotion"])
    aggregate_metrics = _metrics(contract_outcomes)
    aggregate = {
        "rows_audited": sum(run["rows"] for run in run_audits),
        "rows_sampled": sum(run["sampled_rows"] for run in run_audits),
        "diagnostic_contracts": len(contract_outcomes),
        "activated": aggregate_metrics["activated"],
        "closed_with_return": aggregate_metrics["closed_with_return"],
        "unresolved": len(contract_outcomes) - aggregate_metrics["closed_with_return"],
        "metrics": aggregate_metrics,
    }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "methodology": {
            "backtest_version": BACKTEST_VERSION,
            "expiration_sessions": EXPIRATION_SESSIONS,
            "entry_slippage_bps": ENTRY_SLIPPAGE_BPS,
            "exit_slippage_bps": EXIT_SLIPPAGE_BPS,
            "sample_rule": f"top {max_rows_per_run} immutable rows by production rank from each stratified run",
            "run_ids": list(run_ids),
            "historical_schema_adapter": "stored entry -> trigger; maximum effective entry = stored entry + mandatory 5bps slippage",
            "scan_day_bar_excluded": True,
        },
        "price_data": price_audit,
        "runs": run_audits,
        "aggregate": aggregate,
        "walk_forward": wf,
        "ranking_promotion": ranking,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "real_scan_recalc.json").write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    (output_dir / "real_scan_recalc.md").write_text(make_markdown(payload), encoding="utf-8")
    pd.DataFrame([asdict(row) for row in contract_outcomes]).to_csv(output_dir / "outcomes.csv", index=False)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit real immutable scans with backtest-fill-3 semantics")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=Path("audit-output/real-scan-recalc"))
    parser.add_argument("--max-rows-per-run", type=int, default=100)
    parser.add_argument("--run-id", action="append", dest="run_ids")
    args = parser.parse_args()
    if args.max_rows_per_run <= 0:
        raise SystemExit("--max-rows-per-run must be positive")
    run_ids = tuple(args.run_ids) if args.run_ids else DEFAULT_RUN_IDS
    payload = run_audit(args.repo_root, args.output_dir, run_ids, args.max_rows_per_run)
    print(json.dumps({
        "backtest_version": BACKTEST_VERSION,
        "price_data": payload["price_data"],
        "aggregate": payload["aggregate"],
        "walk_forward": payload["walk_forward"],
        "ranking_promotion": payload["ranking_promotion"],
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
