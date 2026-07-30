from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.data_sources.analysis_quotes import fetch_alpaca_iex_analysis_quotes


BAD_QUOTE_STATUSES = {
    "INVALID",
    "STALE_POSSIBLE",
    "MISSING",
    "WIDE_OR_INCOHERENT",
}

RECHECK_RECOMMENDATIONS = {"RECHECK_LIVE_QUOTE"}

RECHECK_DECISIONS = {
    "KEEP_RECHECK",
    "WATCHLIST_MONITOR",
    "EXECUTION_OK_REVIEW_MANUALLY",
    "AVOID_EXECUTION_RISK",
    "DATA_UNAVAILABLE",
}

OUTPUT_COLUMNS = [
    "ticker",
    "prior_decision_lane",
    "selection_origin",
    "recheck_priority",
    "prior_level_type",
    "prior_signal",
    "prior_recommendation",
    "prior_quote_status",
    "prior_execution_quote_quality",
    "prior_actionable_entry",
    "prior_actionable_stop",
    "prior_actionable_target",
    "live_price",
    "live_bid",
    "live_ask",
    "live_spread_pct",
    "live_quote_status",
    "live_execution_quote_quality",
    "live_quote_source",
    "live_quote_timestamp",
    "live_quote_age_minutes",
    "live_data_freshness",
    "corroboration_price",
    "corroboration_bid",
    "corroboration_ask",
    "corroboration_source",
    "corroboration_timestamp",
    "corroboration_freshness",
    "corroboration_status",
    "price_vs_entry_pct",
    "price_within_entry_band",
    "recheck_decision",
    "recheck_reason",
    "manual_review_required",
]


def _safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _safe_float(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _missing(value) -> bool:
    return _safe_text(value) == ""


def _get_first_number(payload: dict, keys: list[str]):
    for key in keys:
        value = _safe_float(payload.get(key), None)
        if value is not None:
            return value
    return None


def _get_first_text(payload: dict, keys: list[str]) -> str:
    for key in keys:
        value = _safe_text(payload.get(key))
        if value:
            return value
    return ""


def _empty_output_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def is_quote_recheck_candidate(row: dict) -> bool:
    recommendation = _safe_text(row.get("recommendation")).upper()
    quote_status = _safe_text(row.get("quote_status")).upper()
    execution_quote_quality = _safe_text(row.get("execution_quote_quality")).upper()
    quote_recheck_priority = _safe_text(row.get("quote_recheck_priority")).upper()
    manual_quote_check_required = _bool(row.get("manual_quote_check_required"))

    return (
        recommendation in RECHECK_RECOMMENDATIONS
        or quote_status in BAD_QUOTE_STATUSES
        or execution_quote_quality == "LOW"
        or quote_recheck_priority in {"HIGH", "MEDIUM", "LOW"}
        or manual_quote_check_required
    )


def select_recheck_candidates(input_df: pd.DataFrame) -> pd.DataFrame:
    if input_df.empty or "ticker" not in input_df.columns:
        return pd.DataFrame()

    out = input_df.copy()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["_manual_order"] = range(len(out))

    mask = out.apply(lambda row: is_quote_recheck_candidate(row.to_dict()), axis=1)
    return out[mask].copy().reset_index(drop=True)


def _decision_lane(row: dict) -> str:
    lane = _get_first_text(row, ["prior_decision_lane", "decision_lane", "technical_analysis_lane"])
    return lane.upper() or "UNKNOWN"


def _candidate_priority(row: dict) -> int | None:
    lane = _decision_lane(row)
    recommendation = _safe_text(row.get("recommendation")).upper()
    bad_quote = (
        _safe_text(row.get("quote_status")).upper() in BAD_QUOTE_STATUSES
        or _safe_text(row.get("execution_quote_quality")).upper() == "LOW"
    )
    if lane == "EXECUTION_CANDIDATE" and bad_quote:
        return 0
    if recommendation in RECHECK_RECOMMENDATIONS:
        return 1
    if lane in {
        "TACTICAL_RESEARCH",
        "ADVANCE_RESEARCH_ANALYSIS",
        "LEADERSHIP_RESET_WATCH",
        "EXECUTION_CANDIDATE",
    } and bad_quote:
        return 2
    if is_quote_recheck_candidate(row) and _safe_text(row.get("signal")).upper() != "VETO":
        return 3
    return None


def build_recheck_input(
    manual_df: pd.DataFrame | None,
    scan_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for origin, frame in [("LATEST_SCAN", scan_df), ("MANUAL_REVIEW", manual_df)]:
        if frame is None or frame.empty or "ticker" not in frame.columns:
            continue
        current = frame.copy()
        current["ticker"] = current["ticker"].astype(str).str.strip().str.upper()
        current["selection_origin"] = origin
        frames.append(current)
    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True, sort=False)
    rows: list[dict] = []
    for ticker, group in combined.groupby("ticker", sort=False):
        scan_rows = group[group["selection_origin"] == "LATEST_SCAN"]
        manual_rows = group[group["selection_origin"] == "MANUAL_REVIEW"]
        base = (
            scan_rows.iloc[-1].to_dict()
            if not scan_rows.empty
            else manual_rows.iloc[-1].to_dict()
        )
        if not manual_rows.empty:
            for key, value in manual_rows.iloc[-1].to_dict().items():
                if not _missing(value):
                    base[key] = value
        origins = sorted(set(group["selection_origin"].astype(str)))
        base["ticker"] = ticker
        base["selection_origin"] = "+".join(origins)
        priority = _candidate_priority(base)
        if priority is None:
            continue
        base["prior_decision_lane"] = _decision_lane(base)
        base["recheck_priority"] = priority
        rows.append(base)

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    score_col = "operational_readiness_score" if "operational_readiness_score" in out.columns else "final_trade_score"
    sort_cols = ["recheck_priority"]
    ascending = [True]
    if score_col in out.columns:
        sort_cols.append(score_col)
        ascending.append(False)
    sort_cols.append("ticker")
    ascending.append(True)
    return out.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)


def _timestamp_context(value, *, now: datetime | None = None) -> tuple[str, float | None, str]:
    if value is None or _safe_text(value) == "":
        return "", None, "UNKNOWN"
    try:
        if isinstance(value, (int, float)) or _safe_text(value).isdigit():
            timestamp = datetime.fromtimestamp(float(value), tz=timezone.utc)
        else:
            timestamp = pd.to_datetime(value, utc=True).to_pydatetime()
        current = now or datetime.now(timezone.utc)
        age_minutes = max((current - timestamp).total_seconds() / 60.0, 0.0)
        freshness = "REALTIME" if age_minutes <= 2 else "DELAYED_15_MIN" if age_minutes <= 20 else "STALE"
        return timestamp.isoformat(), round(float(age_minutes), 2), freshness
    except Exception:
        return _safe_text(value), None, "UNKNOWN"


def validate_live_quote(
    last_price: float | None,
    bid: float | None,
    ask: float | None,
    max_quote_distance_pct: float = 0.10,
    max_spread_pct: float | None = 0.03,
    quote_timestamp=None,
    require_timestamp: bool = False,
    max_quote_age_minutes: float = 15.0,
) -> dict:
    normalized_timestamp, age_minutes, freshness = _timestamp_context(quote_timestamp)
    timestamp_fields = {
        "live_quote_timestamp": normalized_timestamp,
        "live_quote_age_minutes": age_minutes,
        "live_data_freshness": freshness,
    }
    if last_price is None or last_price <= 0:
        return {
            **timestamp_fields,
            "live_quote_status": "MISSING",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": None,
            "live_quote_warning": "missing_or_invalid_last_price",
            "live_recheck_decision": "DATA_UNAVAILABLE",
        }

    if bid is None or ask is None:
        return {
            **timestamp_fields,
            "live_quote_status": "MISSING",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": None,
            "live_quote_warning": "missing_bid_or_ask_spread_unknown",
            "live_recheck_decision": "DATA_UNAVAILABLE",
        }

    if bid <= 0 or ask <= 0:
        return {
            **timestamp_fields,
            "live_quote_status": "INVALID",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": None,
            "live_quote_warning": "bid_or_ask_zero_or_negative",
            "live_recheck_decision": "DATA_UNAVAILABLE",
        }

    if ask <= bid:
        return {
            **timestamp_fields,
            "live_quote_status": "INVALID",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": None,
            "live_quote_warning": "ask_less_or_equal_bid",
            "live_recheck_decision": "DATA_UNAVAILABLE",
        }

    bid_distance = abs(bid - last_price) / last_price
    ask_distance = abs(ask - last_price) / last_price
    spread_pct = (ask - bid) / last_price

    if bid_distance > max_quote_distance_pct or ask_distance > max_quote_distance_pct:
        return {
            **timestamp_fields,
            "live_quote_status": "STALE_POSSIBLE",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": round(float(spread_pct), 6),
            "live_quote_warning": "bid_ask_far_from_last_price",
            "live_recheck_decision": "KEEP_RECHECK",
        }

    if max_spread_pct is not None and spread_pct > max_spread_pct:
        return {
            **timestamp_fields,
            "live_quote_status": "WIDE_OR_INCOHERENT",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": round(float(spread_pct), 6),
            "live_quote_warning": "spread_above_max",
            "live_recheck_decision": "AVOID_EXECUTION_RISK",
        }

    if require_timestamp and (age_minutes is None or age_minutes > max_quote_age_minutes):
        return {
            **timestamp_fields,
            "live_quote_status": "STALE_POSSIBLE",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": round(float(spread_pct), 6),
            "live_quote_warning": "missing_or_stale_verifiable_timestamp",
            "live_recheck_decision": "KEEP_RECHECK",
        }

    return {
        **timestamp_fields,
        "live_quote_status": "VALID",
        "live_execution_quote_quality": "HIGH",
        "live_spread_pct": round(float(spread_pct), 6),
        "live_quote_warning": "",
        "live_recheck_decision": "EXECUTION_OK_REVIEW_MANUALLY",
    }


def fetch_yahoo_live_quote(ticker: str) -> dict:
    try:
        import yfinance as yf
    except Exception as exc:
        return {
            "ticker": ticker,
            "live_fetch_status": "FAIL",
            "live_fetch_error": f"yfinance_import_error:{exc}",
            "live_price": None,
            "live_bid": None,
            "live_ask": None,
            "live_quote_source": "YAHOO_FINANCE",
        }

    try:
        tk = yf.Ticker(ticker)

        fast_info = {}
        try:
            raw_fast_info = tk.fast_info
            fast_info = dict(raw_fast_info) if raw_fast_info is not None else {}
        except Exception:
            fast_info = {}

        info = {}
        try:
            info = tk.get_info() or {}
        except Exception:
            try:
                info = tk.info or {}
            except Exception:
                info = {}

        live_price = _get_first_number(
            fast_info,
            [
                "lastPrice",
                "last_price",
            ],
        )
        if live_price is None:
            live_price = _get_first_number(
                info,
                ["regularMarketPrice", "currentPrice", "previousClose"],
            )
        live_bid = _get_first_number(info, ["bid"])
        live_ask = _get_first_number(info, ["ask"])
        raw_timestamp = (
            fast_info.get("last_trade_time")
            or fast_info.get("lastTradeTime")
            or info.get("regularMarketTime")
            or info.get("postMarketTime")
        )
        normalized_timestamp, _, _ = _timestamp_context(raw_timestamp)

        return {
            "ticker": ticker,
            "live_fetch_status": "PASS" if live_price is not None else "FAIL",
            "live_fetch_error": "" if live_price is not None else "missing_price_from_yfinance",
            "live_price": live_price,
            "live_bid": live_bid,
            "live_ask": live_ask,
            "live_quote_source": "YAHOO_FINANCE",
            "live_quote_timestamp": normalized_timestamp,
        }

    except Exception as exc:
        return {
            "ticker": ticker,
            "live_fetch_status": "FAIL",
            "live_fetch_error": str(exc),
            "live_price": None,
            "live_bid": None,
            "live_ask": None,
            "live_quote_source": "YAHOO_FINANCE",
        }


def _levels(row: dict) -> tuple[float | None, float | None, float | None, str]:
    actionable = tuple(
        _safe_float(row.get(key), None)
        for key in ("actionable_entry", "actionable_stop", "actionable_target")
    )
    if all(value is not None for value in actionable):
        return actionable[0], actionable[1], actionable[2], "ACTIONABLE"

    scenario = tuple(
        _safe_float(row.get(key), None)
        for key in ("scenario_entry", "scenario_stop", "scenario_target")
    )
    if all(value is not None for value in scenario):
        return scenario[0], scenario[1], scenario[2], "SCENARIO_DIAGNOSTIC"

    entry = _safe_float(row.get("entry") or row.get("theoretical_entry"), None)
    stop = _safe_float(row.get("stop") or row.get("theoretical_stop"), None)
    target = _safe_float(row.get("target") or row.get("theoretical_target"), None)
    return entry, stop, target, "LEGACY_DIAGNOSTIC"


def _live_rr(live_price: float | None, stop: float | None, target: float | None) -> float | None:
    if live_price is None or stop is None or target is None:
        return None
    risk = live_price - stop
    reward = target - live_price
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


def _append_reason(reasons: list[str], reason: str) -> None:
    if reason and reason not in reasons:
        reasons.append(reason)


def decide_recheck(
    original: dict,
    quote: dict,
    validation: dict,
    entry_band_pct: float = 0.02,
    avoid_price_distance_pct: float = 0.05,
    min_live_rr: float = 1.50,
) -> dict:
    live_price = _safe_float(quote.get("live_price"), None)
    entry, stop, target, level_type = _levels(original)

    price_vs_entry_pct = None
    price_within_entry_band = False
    if live_price is not None and entry is not None and entry > 0:
        price_vs_entry_pct = (live_price - entry) / entry
        price_within_entry_band = abs(price_vs_entry_pct) <= entry_band_pct

    reasons: list[str] = []
    status = _safe_text(validation.get("live_quote_status")).upper()
    quality = _safe_text(validation.get("live_execution_quote_quality")).upper()
    warning = _safe_text(validation.get("live_quote_warning"))
    if warning:
        _append_reason(reasons, warning)

    decision = "KEEP_RECHECK"

    if live_price is None:
        decision = "DATA_UNAVAILABLE"
        _append_reason(reasons, "live_price_unavailable")
    elif quote.get("live_fetch_status") != "PASS":
        decision = "DATA_UNAVAILABLE"
        _append_reason(reasons, _safe_text(quote.get("live_fetch_error")) or "quote_fetch_failed")
    elif status == "WIDE_OR_INCOHERENT":
        decision = "AVOID_EXECUTION_RISK"
        _append_reason(reasons, "spread_excessive")
    elif status in {"MISSING", "INVALID"}:
        decision = "DATA_UNAVAILABLE"
        _append_reason(reasons, f"live_quote_status_{status.lower()}")
    elif status == "STALE_POSSIBLE" or quality == "LOW":
        decision = "KEEP_RECHECK"
        _append_reason(reasons, "live_quote_not_executable")
    elif entry is None or stop is None or target is None:
        decision = "KEEP_RECHECK"
        _append_reason(reasons, "missing_actionable_entry_stop_or_target")
    elif min(entry, stop, target) <= 0:
        decision = "KEEP_RECHECK"
        _append_reason(reasons, "invalid_actionable_entry_stop_or_target")
    elif price_vs_entry_pct is not None and abs(price_vs_entry_pct) > avoid_price_distance_pct:
        decision = "AVOID_EXECUTION_RISK"
        _append_reason(reasons, "price_too_far_from_entry")
    elif price_vs_entry_pct is not None and abs(price_vs_entry_pct) > entry_band_pct:
        decision = "WATCHLIST_MONITOR"
        _append_reason(reasons, "price_outside_entry_band")
    else:
        live_rr = _live_rr(live_price, stop, target)
        if live_rr is None or live_rr < min_live_rr:
            decision = "KEEP_RECHECK"
            _append_reason(reasons, "live_rr_invalid_or_below_min")
        else:
            decision = "EXECUTION_OK_REVIEW_MANUALLY"
            _append_reason(reasons, "valid_live_quote_low_spread_price_near_entry")

    if decision not in RECHECK_DECISIONS:
        decision = "KEEP_RECHECK"
        _append_reason(reasons, "unknown_decision_guard")

    prior_lane = _decision_lane(original)
    if (
        decision == "EXECUTION_OK_REVIEW_MANUALLY"
        and prior_lane not in {"UNKNOWN", "EXECUTION_CANDIDATE"}
    ):
        decision = "WATCHLIST_MONITOR"
        _append_reason(reasons, "technical_lane_not_execution_eligible")

    return {
        "prior_actionable_entry": entry,
        "prior_actionable_stop": stop,
        "prior_actionable_target": target,
        "prior_level_type": level_type,
        "price_vs_entry_pct": round(float(price_vs_entry_pct), 6) if price_vs_entry_pct is not None else None,
        "price_within_entry_band": bool(price_within_entry_band),
        "recheck_decision": decision,
        "recheck_reason": "; ".join(reasons),
        "manual_review_required": True,
    }


def build_live_quote_recheck_dataframe(
    input_df: pd.DataFrame,
    fetcher: Callable[[str], dict] | None = None,
    max_tickers: int | None = None,
    max_quote_distance_pct: float = 0.10,
    max_spread_pct: float | None = 0.03,
    entry_band_pct: float = 0.02,
    avoid_price_distance_pct: float = 0.05,
    min_live_rr: float = 1.50,
    require_timestamp: bool = False,
    max_quote_age_minutes: float = 15.0,
    alpaca_fetcher: Callable[[list[str]], dict[str, dict]] | None = None,
) -> pd.DataFrame:
    fetcher = fetcher or fetch_yahoo_live_quote

    candidates = select_recheck_candidates(input_df)
    if candidates.empty:
        return _empty_output_dataframe()

    if max_tickers is not None and max_tickers > 0:
        candidates = candidates.head(max_tickers).copy()

    corroboration_quotes: dict[str, dict] = {}
    tickers = candidates["ticker"].astype(str).str.upper().tolist()
    if alpaca_fetcher is not None:
        try:
            corroboration_quotes = alpaca_fetcher(tickers) or {}
        except Exception:
            corroboration_quotes = {}
    elif fetcher is fetch_yahoo_live_quote:
        try:
            corroboration_quotes = fetch_alpaca_iex_analysis_quotes(tickers)
        except Exception:
            corroboration_quotes = {}

    rows: list[dict] = []

    for _, row in candidates.iterrows():
        original = row.to_dict()
        ticker = _safe_text(original.get("ticker")).upper()
        timestamp = datetime.now(timezone.utc).isoformat()

        quote = fetcher(ticker)
        if "live_quote_source" not in quote and "live_source" in quote:
            quote["live_quote_source"] = quote.get("live_source")

        validation = validate_live_quote(
            last_price=_safe_float(quote.get("live_price"), None),
            bid=_safe_float(quote.get("live_bid"), None),
            ask=_safe_float(quote.get("live_ask"), None),
            max_quote_distance_pct=max_quote_distance_pct,
            max_spread_pct=max_spread_pct,
            quote_timestamp=quote.get("live_quote_timestamp"),
            require_timestamp=require_timestamp,
            max_quote_age_minutes=max_quote_age_minutes,
        )
        corroboration = corroboration_quotes.get(ticker, {})

        decision = decide_recheck(
            original=original,
            quote=quote,
            validation=validation,
            entry_band_pct=entry_band_pct,
            avoid_price_distance_pct=avoid_price_distance_pct,
            min_live_rr=min_live_rr,
        )

        rows.append(
            {
                "recheck_timestamp": timestamp,
                "rank": original.get("rank"),
                "ticker": ticker,
                "prior_decision_lane": original.get("prior_decision_lane") or _decision_lane(original),
                "selection_origin": original.get("selection_origin") or "INPUT",
                "recheck_priority": original.get("recheck_priority"),
                "prior_level_type": decision.get("prior_level_type"),
                "prior_signal": _get_first_text(original, ["signal", "source_signal"]),
                "prior_recommendation": _get_first_text(original, ["recommendation", "source_recommendation"]),
                "prior_quote_status": _get_first_text(original, ["quote_status", "source_quote_status"]),
                "prior_execution_quote_quality": _get_first_text(
                    original,
                    ["execution_quote_quality", "source_execution_quote_quality"],
                ),
                "prior_actionable_entry": decision.get("prior_actionable_entry"),
                "prior_actionable_stop": decision.get("prior_actionable_stop"),
                "prior_actionable_target": decision.get("prior_actionable_target"),
                "prior_rr": original.get("rr"),
                "setup_type": original.get("setup_type"),
                "final_trade_score": original.get("final_trade_score"),
                "quote_recheck_priority": original.get("quote_recheck_priority"),
                "live_fetch_status": quote.get("live_fetch_status"),
                "live_fetch_error": quote.get("live_fetch_error"),
                "live_price": quote.get("live_price"),
                "live_bid": quote.get("live_bid"),
                "live_ask": quote.get("live_ask"),
                "live_spread_pct": validation.get("live_spread_pct"),
                "live_quote_status": validation.get("live_quote_status"),
                "live_execution_quote_quality": validation.get("live_execution_quote_quality"),
                "live_quote_source": quote.get("live_quote_source") or "UNKNOWN",
                "live_quote_timestamp": validation.get("live_quote_timestamp") or quote.get("live_quote_timestamp") or timestamp,
                "live_quote_age_minutes": validation.get("live_quote_age_minutes"),
                "live_data_freshness": validation.get("live_data_freshness"),
                "corroboration_price": corroboration.get("analysis_price"),
                "corroboration_bid": corroboration.get("analysis_bid"),
                "corroboration_ask": corroboration.get("analysis_ask"),
                "corroboration_source": corroboration.get("analysis_quote_source"),
                "corroboration_timestamp": corroboration.get("analysis_quote_timestamp"),
                "corroboration_freshness": corroboration.get("analysis_quote_freshness"),
                "corroboration_status": corroboration.get("status"),
                "live_quote_warning": validation.get("live_quote_warning"),
                "price_vs_entry_pct": decision.get("price_vs_entry_pct"),
                "price_within_entry_band": decision.get("price_within_entry_band"),
                "recheck_decision": decision.get("recheck_decision"),
                "live_recheck_decision": decision.get("recheck_decision"),
                "recheck_reason": decision.get("recheck_reason"),
                "manual_review_required": decision.get("manual_review_required"),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return _empty_output_dataframe()

    decision_order = {
        "EXECUTION_OK_REVIEW_MANUALLY": 0,
        "KEEP_RECHECK": 1,
        "WATCHLIST_MONITOR": 2,
        "AVOID_EXECUTION_RISK": 3,
        "DATA_UNAVAILABLE": 4,
    }
    out["_decision_order"] = out["recheck_decision"].map(decision_order).fillna(99).astype(int)

    sort_cols = [col for col in ["recheck_priority", "_decision_order", "rank", "final_trade_score"] if col in out.columns]
    ascending = [False if col == "final_trade_score" else True for col in sort_cols]
    out = out.sort_values(sort_cols, ascending=ascending).drop(columns=["_decision_order"])

    ordered = [col for col in OUTPUT_COLUMNS if col in out.columns]
    extras = [col for col in out.columns if col not in ordered]
    return out[ordered + extras].reset_index(drop=True)


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin candidatos._"

    columns = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")

    for _, row in df.iterrows():
        values = []
        for col in columns:
            value = row.get(col)
            if pd.isna(value):
                value = ""
            values.append(str(value).replace("\n", " ").replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def build_live_quote_recheck_markdown(df: pd.DataFrame, status: str = "PASS") -> str:
    lines: list[str] = []

    lines.append("# Analista - live quote recheck")
    lines.append("")
    lines.append("> Revalidacion auxiliar. No modifica ranking, senales ni recomendaciones.")
    lines.append("")
    lines.append(f"- status: {status}")
    lines.append(f"- rows: {int(len(df))}")
    lines.append("")

    if df.empty:
        lines.append("_No hay candidatos que requieran recheck de quote._")
        return "\n".join(lines)

    decisions = df["recheck_decision"].value_counts().to_dict()

    lines.append("## Resumen")
    lines.append("")
    for key in [
        "EXECUTION_OK_REVIEW_MANUALLY",
        "KEEP_RECHECK",
        "WATCHLIST_MONITOR",
        "AVOID_EXECUTION_RISK",
        "DATA_UNAVAILABLE",
    ]:
        lines.append(f"- {key}: {int(decisions.get(key, 0))}")
    lines.append("")

    display_cols = [
        "rank",
        "ticker",
        "prior_signal",
        "prior_recommendation",
        "live_price",
        "live_bid",
        "live_ask",
        "live_spread_pct",
        "live_quote_status",
        "live_execution_quote_quality",
        "price_vs_entry_pct",
        "price_within_entry_band",
        "recheck_decision",
        "recheck_reason",
    ]
    display_cols = [col for col in display_cols if col in df.columns]

    for decision in [
        "EXECUTION_OK_REVIEW_MANUALLY",
        "KEEP_RECHECK",
        "WATCHLIST_MONITOR",
        "AVOID_EXECUTION_RISK",
        "DATA_UNAVAILABLE",
    ]:
        group_df = df[df["recheck_decision"] == decision].copy()
        lines.append(f"## {decision}")
        lines.append("")
        lines.append(_df_to_markdown_table(group_df[display_cols]))
        lines.append("")

    return "\n".join(lines)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def save_live_quote_recheck_reports(
    input_csv: Path | None = None,
    scan_csv: Path | None = None,
    csv_out: Path | None = None,
    markdown_out: Path | None = None,
    json_out: Path | None = None,
    manual_csv: Path | None = None,
    max_tickers: int | None = None,
    max_quote_distance_pct: float = 0.10,
    max_spread_pct: float | None = 0.03,
    entry_band_pct: float = 0.02,
    avoid_price_distance_pct: float = 0.05,
    min_live_rr: float = 1.50,
    fetcher: Callable[[str], dict] | None = None,
    alpaca_fetcher: Callable[[list[str]], dict[str, dict]] | None = None,
    require_timestamp: bool | None = None,
) -> dict:
    explicit_manual_input = input_csv is not None or manual_csv is not None
    input_csv = input_csv or manual_csv or ROOT / "reports" / "manual_review_latest.csv"
    if scan_csv is None and not explicit_manual_input:
        scan_csv = ROOT / "reports" / "latest_scan_audited.csv"
    csv_out = csv_out or ROOT / "reports" / "live_quote_recheck_latest.csv"
    markdown_out = markdown_out or ROOT / "reports" / "live_quote_recheck_latest.md"
    json_out = json_out or ROOT / "reports" / "live_quote_recheck_latest.json"

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)

    scan_exists = bool(scan_csv is not None and scan_csv.exists())
    if not input_csv.exists() and not scan_exists:
        out = _empty_output_dataframe()
        out.to_csv(csv_out, index=False)
        markdown_out.write_text(
            "# Analista - live quote recheck\n\nStatus: FAIL\n\nInput no encontrado: "
            + f"{input_csv} / {scan_csv or 'not_provided'}"
            + "\n",
            encoding="utf-8",
        )
        result = {
            "status": "FAIL",
            "rows": 0,
            "decisions": {},
            "input_csv": str(input_csv),
            "csv_out": str(csv_out),
            "markdown_out": str(markdown_out),
            "json_out": str(json_out),
            "scan_csv": str(scan_csv) if scan_csv else "",
            "error": "input_csv_not_found" if explicit_manual_input and scan_csv is None else "recheck_inputs_not_found",
        }
        _write_json(json_out, result)
        return result

    manual_df = pd.DataFrame()
    scan_df = pd.DataFrame()
    read_errors: list[str] = []
    if input_csv.exists():
        try:
            manual_df = pd.read_csv(input_csv)
        except Exception as exc:
            read_errors.append(f"manual_input_read_failed:{exc}")
    if scan_exists and scan_csv is not None:
        try:
            scan_df = pd.read_csv(scan_csv)
        except Exception as exc:
            read_errors.append(f"scan_input_read_failed:{exc}")
    if manual_df.empty and scan_df.empty and read_errors:
        out = _empty_output_dataframe()
        out.to_csv(csv_out, index=False)
        result = {
            "status": "FAIL",
            "rows": 0,
            "decisions": {},
            "input_csv": str(input_csv),
            "csv_out": str(csv_out),
            "markdown_out": str(markdown_out),
            "json_out": str(json_out),
            "scan_csv": str(scan_csv) if scan_csv else "",
            "error": "; ".join(read_errors),
        }
        markdown_out.write_text(build_live_quote_recheck_markdown(out, status="FAIL"), encoding="utf-8")
        _write_json(json_out, result)
        return result

    input_df = build_recheck_input(manual_df, scan_df)
    effective_require_timestamp = fetcher is None if require_timestamp is None else bool(require_timestamp)
    out = build_live_quote_recheck_dataframe(
        input_df=input_df,
        fetcher=fetcher,
        max_tickers=max_tickers,
        max_quote_distance_pct=max_quote_distance_pct,
        max_spread_pct=max_spread_pct,
        entry_band_pct=entry_band_pct,
        avoid_price_distance_pct=avoid_price_distance_pct,
        min_live_rr=min_live_rr,
        require_timestamp=effective_require_timestamp,
        alpaca_fetcher=alpaca_fetcher,
    )

    out.to_csv(csv_out, index=False)
    markdown_out.write_text(build_live_quote_recheck_markdown(out, status="PASS"), encoding="utf-8")

    decisions = out["recheck_decision"].value_counts().to_dict() if not out.empty else {}
    result = {
        "status": "PASS",
        "rows": int(len(out)),
        "decisions": {str(k): int(v) for k, v in decisions.items()},
        "execution_ok_review_manually": int(decisions.get("EXECUTION_OK_REVIEW_MANUALLY", 0)),
        "keep_recheck": int(decisions.get("KEEP_RECHECK", 0)),
        "watchlist_monitor": int(decisions.get("WATCHLIST_MONITOR", 0)),
        "avoid_execution_risk": int(decisions.get("AVOID_EXECUTION_RISK", 0)),
        "data_unavailable": int(decisions.get("DATA_UNAVAILABLE", 0)),
        "input_csv": str(input_csv),
        "scan_csv": str(scan_csv) if scan_csv else "",
        "input_read_warnings": read_errors,
        "csv_out": str(csv_out),
        "markdown_out": str(markdown_out),
        "json_out": str(json_out),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(json_out, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Revalida quotes live para candidatos RECHECK_LIVE_QUOTE.")
    parser.add_argument("--input-csv", default="reports/manual_review_latest.csv")
    parser.add_argument("--scan-csv", default="reports/latest_scan_audited.csv")
    parser.add_argument("--manual-csv", default=None, help="Alias legacy de --input-csv.")
    parser.add_argument("--csv-out", default="reports/live_quote_recheck_latest.csv")
    parser.add_argument("--markdown-out", default="reports/live_quote_recheck_latest.md")
    parser.add_argument("--json-out", default="reports/live_quote_recheck_latest.json")
    parser.add_argument("--max-tickers", type=int, default=25)
    parser.add_argument("--max-quote-distance-pct", type=float, default=0.10)
    parser.add_argument("--max-spread-pct", type=float, default=0.03)
    parser.add_argument("--entry-band-pct", type=float, default=0.02)
    parser.add_argument("--avoid-price-distance-pct", type=float, default=0.05)
    parser.add_argument("--min-live-rr", type=float, default=1.50)
    args = parser.parse_args()

    input_arg = args.manual_csv or args.input_csv

    result = save_live_quote_recheck_reports(
        input_csv=ROOT / input_arg,
        scan_csv=ROOT / args.scan_csv,
        csv_out=ROOT / args.csv_out,
        markdown_out=ROOT / args.markdown_out,
        json_out=ROOT / args.json_out,
        max_tickers=args.max_tickers,
        max_quote_distance_pct=args.max_quote_distance_pct,
        max_spread_pct=args.max_spread_pct,
        entry_band_pct=args.entry_band_pct,
        avoid_price_distance_pct=args.avoid_price_distance_pct,
        min_live_rr=args.min_live_rr,
    )

    print("=== ANALISTA LIVE QUOTE RECHECK ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result['rows']}")
    print(f"Decisions: {result['decisions']}")
    print(f"CSV: {result['csv_out']}")
    print(f"Markdown: {result['markdown_out']}")
    print(f"JSON: {result['json_out']}")
    if result.get("error"):
        print(f"Error: {result['error']}")

    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
