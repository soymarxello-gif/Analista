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


def validate_live_quote(
    last_price: float | None,
    bid: float | None,
    ask: float | None,
    max_quote_distance_pct: float = 0.10,
    max_spread_pct: float | None = 0.03,
) -> dict:
    if last_price is None or last_price <= 0:
        return {
            "live_quote_status": "MISSING",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": None,
            "live_quote_warning": "missing_or_invalid_last_price",
            "live_recheck_decision": "DATA_UNAVAILABLE",
        }

    if bid is None or ask is None:
        return {
            "live_quote_status": "MISSING",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": None,
            "live_quote_warning": "missing_bid_or_ask_spread_unknown",
            "live_recheck_decision": "DATA_UNAVAILABLE",
        }

    if bid <= 0 or ask <= 0:
        return {
            "live_quote_status": "INVALID",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": None,
            "live_quote_warning": "bid_or_ask_zero_or_negative",
            "live_recheck_decision": "DATA_UNAVAILABLE",
        }

    if ask <= bid:
        return {
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
            "live_quote_status": "STALE_POSSIBLE",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": round(float(spread_pct), 6),
            "live_quote_warning": "bid_ask_far_from_last_price",
            "live_recheck_decision": "KEEP_RECHECK",
        }

    if max_spread_pct is not None and spread_pct > max_spread_pct:
        return {
            "live_quote_status": "WIDE_OR_INCOHERENT",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": round(float(spread_pct), 6),
            "live_quote_warning": "spread_above_max",
            "live_recheck_decision": "AVOID_EXECUTION_RISK",
        }

    return {
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

        payload = {}
        payload.update(fast_info)
        payload.update(info)

        live_price = _get_first_number(
            payload,
            [
                "lastPrice",
                "last_price",
                "regularMarketPrice",
                "currentPrice",
                "previousClose",
            ],
        )
        live_bid = _get_first_number(payload, ["bid"])
        live_ask = _get_first_number(payload, ["ask"])

        return {
            "ticker": ticker,
            "live_fetch_status": "PASS" if live_price is not None else "FAIL",
            "live_fetch_error": "" if live_price is not None else "missing_price_from_yfinance",
            "live_price": live_price,
            "live_bid": live_bid,
            "live_ask": live_ask,
            "live_quote_source": "YAHOO_FINANCE",
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


def _levels(row: dict) -> tuple[float | None, float | None, float | None]:
    entry = _safe_float(row.get("actionable_entry") or row.get("entry") or row.get("theoretical_entry"), None)
    stop = _safe_float(row.get("actionable_stop") or row.get("stop") or row.get("theoretical_stop"), None)
    target = _safe_float(row.get("actionable_target") or row.get("target") or row.get("theoretical_target"), None)
    return entry, stop, target


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
    entry, stop, target = _levels(original)

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

    return {
        "prior_actionable_entry": entry,
        "prior_actionable_stop": stop,
        "prior_actionable_target": target,
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
) -> pd.DataFrame:
    fetcher = fetcher or fetch_yahoo_live_quote

    candidates = select_recheck_candidates(input_df)
    if candidates.empty:
        return _empty_output_dataframe()

    if max_tickers is not None and max_tickers > 0:
        candidates = candidates.head(max_tickers).copy()

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
        )

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
                "live_quote_timestamp": timestamp,
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

    sort_cols = [col for col in ["_decision_order", "rank", "final_trade_score"] if col in out.columns]
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
) -> dict:
    input_csv = input_csv or manual_csv or ROOT / "reports" / "manual_review_latest.csv"
    csv_out = csv_out or ROOT / "reports" / "live_quote_recheck_latest.csv"
    markdown_out = markdown_out or ROOT / "reports" / "live_quote_recheck_latest.md"
    json_out = json_out or ROOT / "reports" / "live_quote_recheck_latest.json"

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        out = _empty_output_dataframe()
        out.to_csv(csv_out, index=False)
        markdown_out.write_text(
            "# Analista - live quote recheck\n\nStatus: FAIL\n\nInput no encontrado: "
            + str(input_csv)
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
            "error": "input_csv_not_found",
        }
        _write_json(json_out, result)
        return result

    try:
        input_df = pd.read_csv(input_csv)
    except Exception as exc:
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
            "error": f"input_csv_read_failed:{exc}",
        }
        markdown_out.write_text(build_live_quote_recheck_markdown(out, status="FAIL"), encoding="utf-8")
        _write_json(json_out, result)
        return result

    out = build_live_quote_recheck_dataframe(
        input_df=input_df,
        fetcher=fetcher,
        max_tickers=max_tickers,
        max_quote_distance_pct=max_quote_distance_pct,
        max_spread_pct=max_spread_pct,
        entry_band_pct=entry_band_pct,
        avoid_price_distance_pct=avoid_price_distance_pct,
        min_live_rr=min_live_rr,
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
