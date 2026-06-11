from __future__ import annotations

import argparse
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

RECHECK_RECOMMENDATIONS = {
    "RECHECK_LIVE_QUOTE",
}


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


def _get_first_number(payload: dict, keys: list[str]):
    for key in keys:
        value = _safe_float(payload.get(key), None)
        if value is not None:
            return value
    return None


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


def select_recheck_candidates(manual_df: pd.DataFrame) -> pd.DataFrame:
    if manual_df.empty:
        return pd.DataFrame()

    if "ticker" not in manual_df.columns:
        return pd.DataFrame()

    out = manual_df.copy()
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
            "live_recheck_decision": "QUOTE_FETCH_FAILED",
        }

    if bid is None or ask is None:
        return {
            "live_quote_status": "MISSING",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": None,
            "live_quote_warning": "missing_bid_or_ask",
            "live_recheck_decision": "QUOTE_STILL_UNCONFIRMED",
        }

    if bid <= 0 or ask <= 0:
        return {
            "live_quote_status": "INVALID",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": None,
            "live_quote_warning": "bid_or_ask_zero_or_negative",
            "live_recheck_decision": "QUOTE_STILL_UNCONFIRMED",
        }

    if ask <= bid:
        return {
            "live_quote_status": "INVALID",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": None,
            "live_quote_warning": "ask_less_or_equal_bid",
            "live_recheck_decision": "QUOTE_STILL_UNCONFIRMED",
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
            "live_recheck_decision": "QUOTE_STILL_UNCONFIRMED",
        }

    if max_spread_pct is not None and spread_pct > max_spread_pct:
        return {
            "live_quote_status": "WIDE_OR_INCOHERENT",
            "live_execution_quote_quality": "LOW",
            "live_spread_pct": round(float(spread_pct), 6),
            "live_quote_warning": "spread_above_max",
            "live_recheck_decision": "QUOTE_STILL_UNCONFIRMED",
        }

    return {
        "live_quote_status": "VALID",
        "live_execution_quote_quality": "HIGH",
        "live_spread_pct": round(float(spread_pct), 6),
        "live_quote_warning": "",
        "live_recheck_decision": "QUOTE_OK_FOR_MANUAL_REVIEW",
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
            "live_source": "yfinance",
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
            "live_source": "yfinance",
        }

    except Exception as exc:
        return {
            "ticker": ticker,
            "live_fetch_status": "FAIL",
            "live_fetch_error": str(exc),
            "live_price": None,
            "live_bid": None,
            "live_ask": None,
            "live_source": "yfinance",
        }


def build_live_quote_recheck_dataframe(
    manual_df: pd.DataFrame,
    fetcher: Callable[[str], dict] | None = None,
    max_tickers: int | None = None,
    max_quote_distance_pct: float = 0.10,
    max_spread_pct: float | None = 0.03,
) -> pd.DataFrame:
    fetcher = fetcher or fetch_yahoo_live_quote

    candidates = select_recheck_candidates(manual_df)

    if candidates.empty:
        return pd.DataFrame()

    if max_tickers is not None and max_tickers > 0:
        candidates = candidates.head(max_tickers).copy()

    rows: list[dict] = []

    for _, row in candidates.iterrows():
        original = row.to_dict()
        ticker = _safe_text(original.get("ticker")).upper()

        quote = fetcher(ticker)

        validation = validate_live_quote(
            last_price=_safe_float(quote.get("live_price"), None),
            bid=_safe_float(quote.get("live_bid"), None),
            ask=_safe_float(quote.get("live_ask"), None),
            max_quote_distance_pct=max_quote_distance_pct,
            max_spread_pct=max_spread_pct,
        )

        if quote.get("live_fetch_status") != "PASS":
            validation["live_recheck_decision"] = "QUOTE_FETCH_FAILED"

        rows.append(
            {
                "recheck_timestamp": datetime.now(timezone.utc).isoformat(),
                "rank": original.get("rank"),
                "ticker": ticker,
                "signal": original.get("signal"),
                "recommendation": original.get("recommendation"),
                "quote_status": original.get("quote_status"),
                "execution_quote_quality": original.get("execution_quote_quality"),
                "quote_recheck_priority": original.get("quote_recheck_priority"),
                "setup_persistence_score": original.get("setup_persistence_score"),
                "setup_persistence_bucket": original.get("setup_persistence_bucket"),
                "final_trade_score": original.get("final_trade_score"),
                "setup_quality_score": original.get("setup_quality_score"),
                "rr": original.get("rr"),
                "setup_type": original.get("setup_type"),
                "signal_path": original.get("signal_path"),
                "live_fetch_status": quote.get("live_fetch_status"),
                "live_fetch_error": quote.get("live_fetch_error"),
                "live_source": quote.get("live_source"),
                "live_price": quote.get("live_price"),
                "live_bid": quote.get("live_bid"),
                "live_ask": quote.get("live_ask"),
                **validation,
            }
        )

    out = pd.DataFrame(rows)

    if not out.empty:
        decision_order = {
            "QUOTE_OK_FOR_MANUAL_REVIEW": 0,
            "QUOTE_STILL_UNCONFIRMED": 1,
            "QUOTE_FETCH_FAILED": 2,
        }
        out["_decision_order"] = out["live_recheck_decision"].map(decision_order).fillna(99).astype(int)

        sort_cols = [
            "_decision_order",
            "rank",
            "setup_persistence_score",
            "final_trade_score",
        ]
        sort_cols = [col for col in sort_cols if col in out.columns]

        ascending = []
        for col in sort_cols:
            ascending.append(False if col in {"setup_persistence_score", "final_trade_score"} else True)

        out = out.sort_values(sort_cols, ascending=ascending).drop(columns=["_decision_order"])

    return out.reset_index(drop=True)


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


def build_live_quote_recheck_markdown(df: pd.DataFrame) -> str:
    lines: list[str] = []

    lines.append("# Analista — live quote recheck")
    lines.append("")
    lines.append("> Revalidación auxiliar. No modifica ranking, señales ni recomendaciones.")
    lines.append("")

    if df.empty:
        lines.append("_No hay candidatos que requieran recheck de quote._")
        return "\n".join(lines)

    lines.append("## Resumen")
    lines.append("")

    decisions = df["live_recheck_decision"].value_counts().to_dict()
    for key in ["QUOTE_OK_FOR_MANUAL_REVIEW", "QUOTE_STILL_UNCONFIRMED", "QUOTE_FETCH_FAILED"]:
        lines.append(f"- {key}: {int(decisions.get(key, 0))}")

    lines.append("")

    display_cols = [
        "rank",
        "ticker",
        "signal",
        "recommendation",
        "quote_status",
        "execution_quote_quality",
        "live_recheck_decision",
        "live_quote_status",
        "live_execution_quote_quality",
        "live_price",
        "live_bid",
        "live_ask",
        "live_spread_pct",
        "setup_persistence_score",
        "final_trade_score",
        "rr",
        "live_quote_warning",
        "live_fetch_error",
    ]
    display_cols = [col for col in display_cols if col in df.columns]

    for decision in ["QUOTE_OK_FOR_MANUAL_REVIEW", "QUOTE_STILL_UNCONFIRMED", "QUOTE_FETCH_FAILED"]:
        group_df = df[df["live_recheck_decision"] == decision].copy()
        lines.append(f"## {decision}")
        lines.append("")

        if group_df.empty:
            lines.append("_Sin candidatos._")
            lines.append("")
            continue

        lines.append(_df_to_markdown_table(group_df[display_cols]))
        lines.append("")

    return "\n".join(lines)


def save_live_quote_recheck_reports(
    manual_csv: Path,
    csv_out: Path,
    markdown_out: Path,
    max_tickers: int | None = None,
    max_quote_distance_pct: float = 0.10,
    max_spread_pct: float | None = 0.03,
) -> dict:
    if not manual_csv.exists():
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.parent.mkdir(parents=True, exist_ok=True)

        pd.DataFrame().to_csv(csv_out, index=False)
        markdown_out.write_text(
            "# Analista — live quote recheck\n\nNo existe manual_review_latest.csv.\n",
            encoding="utf-8",
        )

        return {
            "status": "FAIL",
            "rows": 0,
            "decisions": {},
            "csv_out": str(csv_out),
            "markdown_out": str(markdown_out),
        }

    manual_df = pd.read_csv(manual_csv)

    out = build_live_quote_recheck_dataframe(
        manual_df=manual_df,
        max_tickers=max_tickers,
        max_quote_distance_pct=max_quote_distance_pct,
        max_spread_pct=max_spread_pct,
    )

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    out.to_csv(csv_out, index=False)

    markdown = build_live_quote_recheck_markdown(out)
    markdown_out.write_text(markdown, encoding="utf-8")

    decisions = out["live_recheck_decision"].value_counts().to_dict() if not out.empty else {}

    return {
        "status": "PASS" if not out.empty else "WARN",
        "rows": int(len(out)),
        "decisions": decisions,
        "csv_out": str(csv_out),
        "markdown_out": str(markdown_out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Revalida quotes live para candidatos RECHECK_LIVE_QUOTE.")
    parser.add_argument("--manual-csv", default="reports/manual_review_latest.csv")
    parser.add_argument("--csv-out", default="reports/live_quote_recheck_latest.csv")
    parser.add_argument("--markdown-out", default="reports/live_quote_recheck_latest.md")
    parser.add_argument("--max-tickers", type=int, default=25)
    parser.add_argument("--max-quote-distance-pct", type=float, default=0.10)
    parser.add_argument("--max-spread-pct", type=float, default=0.03)
    args = parser.parse_args()

    result = save_live_quote_recheck_reports(
        manual_csv=ROOT / args.manual_csv,
        csv_out=ROOT / args.csv_out,
        markdown_out=ROOT / args.markdown_out,
        max_tickers=args.max_tickers,
        max_quote_distance_pct=args.max_quote_distance_pct,
        max_spread_pct=args.max_spread_pct,
    )

    print("=== ANALISTA LIVE QUOTE RECHECK ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result['rows']}")
    print(f"Decisions: {result['decisions']}")
    print(f"CSV: {result['csv_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())