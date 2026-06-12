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


NO_REAL_ORDER_NOTICE = "paper trading only; no real order"

FOLLOWUP_DECISIONS = {
    "HOLD_PAPER",
    "REVIEW_NEAR_STOP",
    "REVIEW_NEAR_TARGET",
    "STOP_HIT_REVIEW_CLOSE",
    "TARGET_HIT_REVIEW_CLOSE",
    "DATA_UNAVAILABLE",
    "INVALIDATED_REVIEW",
    "NO_OPEN_PAPER_TRADES",
}

OUTPUT_COLUMNS = [
    "journal_id",
    "ticker",
    "run_date",
    "manual_decision",
    "followup_status",
    "simulated_entry_price",
    "simulated_stop",
    "simulated_target",
    "latest_price",
    "latest_quote_source",
    "latest_quote_status",
    "unrealized_pnl_pct",
    "unrealized_r_multiple",
    "distance_to_stop_pct",
    "distance_to_target_pct",
    "stop_hit_intraday",
    "target_hit_intraday",
    "followup_decision",
    "followup_reason",
    "manual_review_required",
]


def _safe_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _safe_float(value):
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _empty_output_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _load_journal(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        return pd.DataFrame(), "journal_csv_not_found"
    try:
        return pd.read_csv(path, dtype=str).fillna(""), ""
    except Exception as exc:
        return pd.DataFrame(), f"journal_csv_read_failed:{exc}"


def is_open_paper_followup_row(row: dict) -> bool:
    manual_decision = _safe_text(row.get("manual_decision")).upper()
    followup_status = _safe_text(row.get("followup_status")).upper()

    if manual_decision == "PAPER_ENTER":
        return True

    if manual_decision == "PAPER_WATCH" and followup_status == "OPEN_MONITORING":
        return True

    if followup_status == "ENTERED_PAPER":
        return True

    return False


def select_open_paper_trades(journal_df: pd.DataFrame) -> pd.DataFrame:
    if journal_df.empty or "ticker" not in journal_df.columns:
        return pd.DataFrame()

    out = journal_df.copy()
    mask = out.apply(lambda row: is_open_paper_followup_row(row.to_dict()), axis=1)
    return out[mask].copy().reset_index(drop=True)


def fetch_yahoo_latest_price(ticker: str) -> dict:
    try:
        import yfinance as yf
    except Exception as exc:
        return {
            "latest_price": None,
            "latest_quote_source": "YAHOO_FINANCE",
            "latest_quote_status": "MISSING",
            "latest_quote_error": f"yfinance_import_error:{exc}",
        }

    try:
        tk = yf.Ticker(ticker)
        payload = {}
        try:
            fast_info = tk.fast_info
            payload.update(dict(fast_info) if fast_info is not None else {})
        except Exception:
            pass
        try:
            info = tk.get_info() or {}
        except Exception:
            try:
                info = tk.info or {}
            except Exception:
                info = {}
        payload.update(info)

        latest_price = None
        for key in ["lastPrice", "last_price", "regularMarketPrice", "currentPrice", "previousClose"]:
            latest_price = _safe_float(payload.get(key))
            if latest_price is not None:
                break

        return {
            "latest_price": latest_price,
            "latest_quote_source": "YAHOO_FINANCE",
            "latest_quote_status": "VALID" if latest_price is not None and latest_price > 0 else "MISSING",
            "latest_quote_error": "" if latest_price is not None and latest_price > 0 else "missing_price_from_yfinance",
        }
    except Exception as exc:
        return {
            "latest_price": None,
            "latest_quote_source": "YAHOO_FINANCE",
            "latest_quote_status": "MISSING",
            "latest_quote_error": str(exc),
        }


def decide_followup(
    row: dict,
    quote: dict,
    *,
    near_stop_pct: float = 0.03,
    near_target_pct: float = 0.03,
) -> dict:
    latest_price = _safe_float(quote.get("latest_price"))
    entry = _safe_float(row.get("simulated_entry_price") or row.get("actionable_entry"))
    stop = _safe_float(row.get("simulated_stop") or row.get("actionable_stop"))
    target = _safe_float(row.get("simulated_target") or row.get("actionable_target"))
    quote_status = _safe_text(quote.get("latest_quote_status")).upper() or "MISSING"

    if latest_price is None or latest_price <= 0 or quote_status in {"MISSING", "INVALID", "STALE_POSSIBLE"}:
        return {
            "latest_price": latest_price,
            "latest_quote_status": quote_status if quote_status else "MISSING",
            "unrealized_pnl_pct": None,
            "unrealized_r_multiple": None,
            "distance_to_stop_pct": None,
            "distance_to_target_pct": None,
            "stop_hit_intraday": False,
            "target_hit_intraday": False,
            "followup_decision": "DATA_UNAVAILABLE",
            "followup_reason": _safe_text(quote.get("latest_quote_error")) or "latest_price_unavailable",
            "manual_review_required": True,
        }

    if entry is None or stop is None or target is None or min(entry, stop, target) <= 0:
        return {
            "latest_price": latest_price,
            "latest_quote_status": quote_status,
            "unrealized_pnl_pct": None,
            "unrealized_r_multiple": None,
            "distance_to_stop_pct": None,
            "distance_to_target_pct": None,
            "stop_hit_intraday": False,
            "target_hit_intraday": False,
            "followup_decision": "INVALIDATED_REVIEW",
            "followup_reason": "missing_or_invalid_simulated_entry_stop_target",
            "manual_review_required": True,
        }

    risk = entry - stop
    if risk <= 0 or target <= entry:
        return {
            "latest_price": latest_price,
            "latest_quote_status": quote_status,
            "unrealized_pnl_pct": None,
            "unrealized_r_multiple": None,
            "distance_to_stop_pct": None,
            "distance_to_target_pct": None,
            "stop_hit_intraday": False,
            "target_hit_intraday": False,
            "followup_decision": "INVALIDATED_REVIEW",
            "followup_reason": "invalid_long_risk_reward_levels",
            "manual_review_required": True,
        }

    pnl_pct = (latest_price - entry) / entry
    r_multiple = (latest_price - entry) / risk
    distance_to_stop_pct = (latest_price - stop) / latest_price
    distance_to_target_pct = (target - latest_price) / latest_price
    stop_hit = latest_price <= stop
    target_hit = latest_price >= target

    if stop_hit:
        decision = "STOP_HIT_REVIEW_CLOSE"
        reason = "latest_price_at_or_below_simulated_stop"
    elif target_hit:
        decision = "TARGET_HIT_REVIEW_CLOSE"
        reason = "latest_price_at_or_above_simulated_target"
    elif distance_to_stop_pct <= near_stop_pct:
        decision = "REVIEW_NEAR_STOP"
        reason = "latest_price_near_simulated_stop"
    elif distance_to_target_pct <= near_target_pct:
        decision = "REVIEW_NEAR_TARGET"
        reason = "latest_price_near_simulated_target"
    else:
        decision = "HOLD_PAPER"
        reason = "price_between_simulated_stop_and_target"

    return {
        "latest_price": latest_price,
        "latest_quote_status": quote_status,
        "unrealized_pnl_pct": round(float(pnl_pct), 6),
        "unrealized_r_multiple": round(float(r_multiple), 6),
        "distance_to_stop_pct": round(float(distance_to_stop_pct), 6),
        "distance_to_target_pct": round(float(distance_to_target_pct), 6),
        "stop_hit_intraday": bool(stop_hit),
        "target_hit_intraday": bool(target_hit),
        "followup_decision": decision,
        "followup_reason": reason,
        "manual_review_required": decision != "HOLD_PAPER",
    }


def build_paper_trade_followup_dataframe(
    journal_df: pd.DataFrame,
    *,
    fetcher: Callable[[str], dict] | None = None,
    near_stop_pct: float = 0.03,
    near_target_pct: float = 0.03,
) -> pd.DataFrame:
    fetcher = fetcher or fetch_yahoo_latest_price
    open_df = select_open_paper_trades(journal_df)

    if open_df.empty:
        return _empty_output_dataframe()

    rows: list[dict] = []
    for _, item in open_df.iterrows():
        original = item.to_dict()
        ticker = _safe_text(original.get("ticker")).upper()
        quote = fetcher(ticker)
        decision = decide_followup(
            original,
            quote,
            near_stop_pct=near_stop_pct,
            near_target_pct=near_target_pct,
        )

        rows.append(
            {
                "journal_id": _safe_text(original.get("journal_id")),
                "ticker": ticker,
                "run_date": _safe_text(original.get("run_date")),
                "manual_decision": _safe_text(original.get("manual_decision")).upper(),
                "followup_status": _safe_text(original.get("followup_status")).upper(),
                "simulated_entry_price": _safe_float(original.get("simulated_entry_price")),
                "simulated_stop": _safe_float(original.get("simulated_stop")),
                "simulated_target": _safe_float(original.get("simulated_target")),
                "latest_price": decision.get("latest_price"),
                "latest_quote_source": _safe_text(quote.get("latest_quote_source")) or "UNKNOWN",
                "latest_quote_status": decision.get("latest_quote_status"),
                "unrealized_pnl_pct": decision.get("unrealized_pnl_pct"),
                "unrealized_r_multiple": decision.get("unrealized_r_multiple"),
                "distance_to_stop_pct": decision.get("distance_to_stop_pct"),
                "distance_to_target_pct": decision.get("distance_to_target_pct"),
                "stop_hit_intraday": decision.get("stop_hit_intraday"),
                "target_hit_intraday": decision.get("target_hit_intraday"),
                "followup_decision": decision.get("followup_decision"),
                "followup_reason": decision.get("followup_reason"),
                "manual_review_required": decision.get("manual_review_required"),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return _empty_output_dataframe()

    decision_order = {
        "STOP_HIT_REVIEW_CLOSE": 0,
        "TARGET_HIT_REVIEW_CLOSE": 1,
        "REVIEW_NEAR_STOP": 2,
        "REVIEW_NEAR_TARGET": 3,
        "DATA_UNAVAILABLE": 4,
        "INVALIDATED_REVIEW": 5,
        "HOLD_PAPER": 6,
    }
    out["_decision_order"] = out["followup_decision"].map(decision_order).fillna(99).astype(int)
    out = out.sort_values(["_decision_order", "ticker"]).drop(columns=["_decision_order"])
    return out[OUTPUT_COLUMNS].reset_index(drop=True)


def build_summary_payload(
    df: pd.DataFrame,
    *,
    status: str = "PASS",
    error: str = "",
    journal_path: Path | None = None,
    csv_out: Path | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    decisions = df["followup_decision"].value_counts().to_dict() if not df.empty else {}
    return {
        "status": status,
        "rows": int(len(df)),
        "hold_paper": int(decisions.get("HOLD_PAPER", 0)),
        "review_near_stop": int(decisions.get("REVIEW_NEAR_STOP", 0)),
        "review_near_target": int(decisions.get("REVIEW_NEAR_TARGET", 0)),
        "stop_hit_review_close": int(decisions.get("STOP_HIT_REVIEW_CLOSE", 0)),
        "target_hit_review_close": int(decisions.get("TARGET_HIT_REVIEW_CLOSE", 0)),
        "data_unavailable": int(decisions.get("DATA_UNAVAILABLE", 0)),
        "invalidated_review": int(decisions.get("INVALIDATED_REVIEW", 0)),
        "no_open_paper_trades": 1 if df.empty and not error else 0,
        "decisions": {str(key): int(value) for key, value in decisions.items()},
        "error": error,
        "journal_path": str(journal_path or ""),
        "csv_out": str(csv_out or ""),
        "json_out": str(json_out or ""),
        "markdown_out": str(markdown_out or ""),
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin paper trades abiertos._"
    columns = list(df.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in df.iterrows():
        values = []
        for col in columns:
            value = row.get(col)
            if pd.isna(value):
                value = ""
            values.append(str(value).replace("\n", " ").replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_markdown(payload: dict, df: pd.DataFrame) -> str:
    lines: list[str] = []
    lines.append("# Analista - paper trade follow-up")
    lines.append("")
    lines.append(f"- status: {payload.get('status')}")
    lines.append(f"- rows: {payload.get('rows')}")
    lines.append(f"- hold_paper: {payload.get('hold_paper')}")
    lines.append(f"- review_near_stop: {payload.get('review_near_stop')}")
    lines.append(f"- review_near_target: {payload.get('review_near_target')}")
    lines.append(f"- stop_hit_review_close: {payload.get('stop_hit_review_close')}")
    lines.append(f"- target_hit_review_close: {payload.get('target_hit_review_close')}")
    lines.append(f"- data_unavailable: {payload.get('data_unavailable')}")
    lines.append(f"- notice: {NO_REAL_ORDER_NOTICE}")
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    lines.append("- Paper trading only; no real order.")
    lines.append("- No broker connection is used.")
    lines.append("- This report does not close positions or modify the paper journal.")
    lines.append("- Review close/hold decisions manually.")
    lines.append("")
    lines.append("## Follow-up rows")
    lines.append("")
    display_cols = [
        "ticker",
        "manual_decision",
        "followup_status",
        "latest_price",
        "unrealized_pnl_pct",
        "unrealized_r_multiple",
        "distance_to_stop_pct",
        "distance_to_target_pct",
        "followup_decision",
        "followup_reason",
    ]
    display_cols = [col for col in display_cols if col in df.columns]
    lines.append(_df_to_markdown_table(df[display_cols] if display_cols else df))
    return "\n".join(lines)


def write_reports(df: pd.DataFrame, payload: dict, *, csv_out: Path, json_out: Path, markdown_out: Path) -> None:
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_out, index=False)
    json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(payload, df), encoding="utf-8")


def save_paper_trade_followup_reports(
    *,
    journal_path: Path | None = None,
    csv_out: Path | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    root: Path = ROOT,
    fetcher: Callable[[str], dict] | None = None,
    near_stop_pct: float = 0.03,
    near_target_pct: float = 0.03,
) -> dict:
    journal_path = journal_path or root / "data" / "paper_trading_journal.csv"
    csv_out = csv_out or root / "reports" / "paper_trade_followup_latest.csv"
    json_out = json_out or root / "reports" / "paper_trade_followup_latest.json"
    markdown_out = markdown_out or root / "reports" / "paper_trade_followup_latest.md"

    journal_df, error = _load_journal(journal_path)
    status = "PASS"
    if error and error != "journal_csv_not_found":
        status = "FAIL"
    elif error == "journal_csv_not_found":
        status = "WARN"

    if error:
        out = _empty_output_dataframe()
        payload = build_summary_payload(
            out,
            status=status,
            error=error,
            journal_path=journal_path,
            csv_out=csv_out,
            json_out=json_out,
            markdown_out=markdown_out,
        )
        write_reports(out, payload, csv_out=csv_out, json_out=json_out, markdown_out=markdown_out)
        return payload

    out = build_paper_trade_followup_dataframe(
        journal_df,
        fetcher=fetcher,
        near_stop_pct=near_stop_pct,
        near_target_pct=near_target_pct,
    )
    payload = build_summary_payload(
        out,
        status="PASS",
        journal_path=journal_path,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=markdown_out,
    )
    write_reports(out, payload, csv_out=csv_out, json_out=json_out, markdown_out=markdown_out)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera seguimiento diario de paper trades abiertos.")
    parser.add_argument("--journal-path", default="data/paper_trading_journal.csv")
    parser.add_argument("--csv-out", default="reports/paper_trade_followup_latest.csv")
    parser.add_argument("--json-out", default="reports/paper_trade_followup_latest.json")
    parser.add_argument("--markdown-out", default="reports/paper_trade_followup_latest.md")
    parser.add_argument("--near-stop-pct", type=float, default=0.03)
    parser.add_argument("--near-target-pct", type=float, default=0.03)
    args = parser.parse_args()

    result = save_paper_trade_followup_reports(
        root=ROOT,
        journal_path=ROOT / args.journal_path,
        csv_out=ROOT / args.csv_out,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
        near_stop_pct=args.near_stop_pct,
        near_target_pct=args.near_target_pct,
    )

    print("=== ANALISTA PAPER TRADE FOLLOW-UP ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result['rows']}")
    print(f"Hold paper: {result['hold_paper']}")
    print(f"Review near stop: {result['review_near_stop']}")
    print(f"Review near target: {result['review_near_target']}")
    print(f"Stop hit review close: {result['stop_hit_review_close']}")
    print(f"Target hit review close: {result['target_hit_review_close']}")
    print(f"Data unavailable: {result['data_unavailable']}")
    print(f"Notice: {result['no_real_order_notice']}")
    print(f"CSV: {result['csv_out']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    if result.get("error"):
        print(f"Error: {result['error']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
