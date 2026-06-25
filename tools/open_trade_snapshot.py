from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SNAPSHOT_COLUMNS = [
    "snapshot_timestamp",
    "trade_id",
    "ticker",
    "entry_date",
    "entry_price",
    "stop_price",
    "target_price",
    "current_price",
    "unrealized_pnl_pct",
    "unrealized_r_multiple",
    "distance_to_stop_pct",
    "distance_to_target_pct",
    "source_rank",
    "source_signal",
    "source_recommendation",
    "source_final_trade_score",
    "source_setup_quality_score",
    "source_setup_persistence_score",
    "trade_status_note",
    "price_source",
    "price_fetch_status",
    "price_fetch_error",
    "notes",
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


def load_open_trades(outcomes_path: Path) -> pd.DataFrame:
    if not outcomes_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(outcomes_path)

    if df.empty or "status" not in df.columns:
        return pd.DataFrame()

    status = df["status"].fillna("").astype(str).str.upper()
    return df[status == "OPEN"].copy().reset_index(drop=True)


def fetch_yahoo_price(ticker: str) -> dict:
    try:
        import yfinance as yf
    except Exception as exc:
        return {
            "ticker": ticker,
            "current_price": None,
            "price_source": "yfinance",
            "price_fetch_status": "FAIL",
            "price_fetch_error": f"yfinance_import_error:{exc}",
        }

    try:
        tk = yf.Ticker(ticker)

        fast_info = {}
        try:
            raw_fast_info = tk.fast_info
            fast_info = dict(raw_fast_info) if raw_fast_info is not None else {}
        except Exception:
            fast_info = {}

        current_price = None

        for key in ["lastPrice", "last_price", "regularMarketPrice"]:
            value = _safe_float(fast_info.get(key), None)
            if value is not None:
                current_price = value
                break

        if current_price is None:
            try:
                hist = tk.history(period="1d", interval="1d")
                if hist is not None and not hist.empty:
                    current_price = _safe_float(hist["Close"].iloc[-1], None)
            except Exception:
                current_price = None

        return {
            "ticker": ticker,
            "current_price": current_price,
            "price_source": "yfinance",
            "price_fetch_status": "PASS" if current_price is not None else "FAIL",
            "price_fetch_error": "" if current_price is not None else "missing_current_price",
        }

    except Exception as exc:
        return {
            "ticker": ticker,
            "current_price": None,
            "price_source": "yfinance",
            "price_fetch_status": "FAIL",
            "price_fetch_error": str(exc),
        }


def calculate_open_trade_snapshot_row(
    trade: dict,
    current_price: float | None,
    price_source: str = "",
    price_fetch_status: str = "",
    price_fetch_error: str = "",
) -> dict:
    entry_price = _safe_float(trade.get("entry_price"))
    stop_price = _safe_float(trade.get("stop_price"))
    target_price = _safe_float(trade.get("target_price"))

    unrealized_pnl_pct = None
    unrealized_r_multiple = None
    distance_to_stop_pct = None
    distance_to_target_pct = None
    trade_status_note = ""

    if current_price is None:
        trade_status_note = "PRICE_UNAVAILABLE"

    elif entry_price is None or entry_price <= 0:
        trade_status_note = "INVALID_ENTRY_PRICE"

    elif stop_price is None or stop_price <= 0:
        trade_status_note = "INVALID_STOP_PRICE"

    elif target_price is None or target_price <= 0:
        trade_status_note = "INVALID_TARGET_PRICE"

    else:
        risk_pct = abs(entry_price - stop_price) / entry_price
        unrealized_pnl_pct = (current_price - entry_price) / entry_price

        if risk_pct > 0:
            unrealized_r_multiple = unrealized_pnl_pct / risk_pct

        distance_to_stop_pct = (current_price - stop_price) / current_price
        distance_to_target_pct = (target_price - current_price) / current_price

        if current_price <= stop_price:
            trade_status_note = "AT_OR_BELOW_STOP"
        elif current_price >= target_price:
            trade_status_note = "AT_OR_ABOVE_TARGET"
        elif unrealized_pnl_pct > 0:
            trade_status_note = "OPEN_PROFIT"
        elif unrealized_pnl_pct < 0:
            trade_status_note = "OPEN_LOSS"
        else:
            trade_status_note = "AT_ENTRY"

    return {
        "snapshot_timestamp": datetime.now().isoformat(timespec="seconds"),
        "trade_id": trade.get("trade_id", ""),
        "ticker": _safe_text(trade.get("ticker")).upper(),
        "entry_date": trade.get("entry_date", ""),
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "current_price": current_price,
        "unrealized_pnl_pct": round(float(unrealized_pnl_pct), 6) if unrealized_pnl_pct is not None else "",
        "unrealized_r_multiple": round(float(unrealized_r_multiple), 6) if unrealized_r_multiple is not None else "",
        "distance_to_stop_pct": round(float(distance_to_stop_pct), 6) if distance_to_stop_pct is not None else "",
        "distance_to_target_pct": round(float(distance_to_target_pct), 6) if distance_to_target_pct is not None else "",
        "source_rank": trade.get("source_rank", ""),
        "source_signal": trade.get("source_signal", ""),
        "source_recommendation": trade.get("source_recommendation", ""),
        "source_final_trade_score": trade.get("source_final_trade_score", ""),
        "source_setup_quality_score": trade.get("source_setup_quality_score", ""),
        "source_setup_persistence_score": trade.get("source_setup_persistence_score", ""),
        "trade_status_note": trade_status_note,
        "price_source": price_source,
        "price_fetch_status": price_fetch_status,
        "price_fetch_error": price_fetch_error,
        "notes": trade.get("notes", ""),
    }


def build_open_trade_snapshot_dataframe(
    outcomes_path: Path,
    price_fetcher: Callable[[str], dict] | None = None,
) -> pd.DataFrame:
    price_fetcher = price_fetcher or fetch_yahoo_price

    open_trades = load_open_trades(outcomes_path)

    if open_trades.empty:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)

    rows: list[dict] = []

    for _, trade_row in open_trades.iterrows():
        trade = trade_row.to_dict()
        ticker = _safe_text(trade.get("ticker")).upper()

        price_payload = price_fetcher(ticker)

        row = calculate_open_trade_snapshot_row(
            trade=trade,
            current_price=_safe_float(price_payload.get("current_price"), None),
            price_source=price_payload.get("price_source", ""),
            price_fetch_status=price_payload.get("price_fetch_status", ""),
            price_fetch_error=price_payload.get("price_fetch_error", ""),
        )

        rows.append(row)

    df = pd.DataFrame(rows)

    for col in SNAPSHOT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[SNAPSHOT_COLUMNS]


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin operaciones abiertas._"

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


def build_open_trade_snapshot_markdown(df: pd.DataFrame) -> str:
    lines: list[str] = []

    lines.append("# Analista — open trade snapshot")
    lines.append("")
    lines.append(f"- generated_at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- rows: {len(df)}")
    lines.append("")

    if df.empty:
        lines.append("_No hay operaciones abiertas._")
        return "\n".join(lines)

    lines.append("## Resumen")
    lines.append("")

    notes = df["trade_status_note"].fillna("").astype(str).value_counts().to_dict()

    for key in [
        "OPEN_PROFIT",
        "OPEN_LOSS",
        "AT_ENTRY",
        "AT_OR_BELOW_STOP",
        "AT_OR_ABOVE_TARGET",
        "PRICE_UNAVAILABLE",
    ]:
        lines.append(f"- {key}: {int(notes.get(key, 0))}")

    lines.append("")
    lines.append("## Operaciones abiertas")
    lines.append("")

    display_cols = [
        "ticker",
        "entry_date",
        "entry_price",
        "stop_price",
        "target_price",
        "current_price",
        "unrealized_pnl_pct",
        "unrealized_r_multiple",
        "distance_to_stop_pct",
        "distance_to_target_pct",
        "source_recommendation",
        "source_final_trade_score",
        "source_setup_persistence_score",
        "trade_status_note",
        "notes",
    ]
    display_cols = [col for col in display_cols if col in df.columns]

    lines.append(_df_to_markdown_table(df[display_cols]))

    return "\n".join(lines)


def save_open_trade_snapshot_reports(
    outcomes_path: Path,
    csv_out: Path,
    markdown_out: Path,
) -> dict:
    df = build_open_trade_snapshot_dataframe(outcomes_path=outcomes_path)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(csv_out, index=False)
    markdown_out.write_text(build_open_trade_snapshot_markdown(df), encoding="utf-8")

    return {
        "status": "PASS",
        "rows": int(len(df)),
        "csv_out": str(csv_out),
        "markdown_out": str(markdown_out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera snapshot de operaciones abiertas.")
    parser.add_argument("--outcomes-path", default="reports/trade_outcomes.csv")
    parser.add_argument("--csv-out", default="reports/open_trades_snapshot_latest.csv")
    parser.add_argument("--markdown-out", default="reports/open_trades_snapshot_latest.md")
    args = parser.parse_args()

    result = save_open_trade_snapshot_reports(
        outcomes_path=ROOT / args.outcomes_path,
        csv_out=ROOT / args.csv_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA OPEN TRADE SNAPSHOT ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result['rows']}")
    print(f"CSV: {result['csv_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())