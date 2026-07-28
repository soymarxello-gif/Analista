from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.price_client import download_daily_prices
from indicators.pipeline import add_all_indicators

NOTICE = "consulta puntual diagnostica; no paso por screener completo; no real order"


def clean_ticker(value: Any) -> str:
    text = str(value or "").strip().upper()
    return "".join(char for char in text if char.isalnum() or char in ".-_")[:16]


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _last_value(df: pd.DataFrame, column: str) -> Any:
    if df is None or df.empty or column not in df.columns:
        return ""
    values = df[column].dropna()
    return values.iloc[-1] if not values.empty else ""


def build_diagnostic_row(ticker: str, *, config: dict | None = None) -> dict[str, Any]:
    clean = clean_ticker(ticker)
    row: dict[str, Any] = {
        "ticker": clean,
        "manual_deep_dive_decision": "DIAGNOSTIC_REVIEW_ONLY",
        "signal": "",
        "recommendation": "",
        "quote_status": "MISSING",
        "execution_quote_quality": "LOW",
        "analysis_quote_source": "UNKNOWN",
        "analysis_quote_freshness": "UNKNOWN",
        "creates_trading_signal": False,
        "creates_trigger_confirmed": False,
        "broker_execution": False,
        "notice": NOTICE,
    }
    if not clean:
        row["status"] = "FAIL"
        row["warning"] = "ticker_required"
        return row
    try:
        prices = download_daily_prices([clean], period="1y", interval="1d", max_individual_fallbacks=1)
        hist = prices.get(clean, pd.DataFrame())
    except Exception as exc:
        row["status"] = "WARN"
        row["warning"] = f"price_download_failed:{type(exc).__name__}"
        return row
    if hist.empty:
        row["status"] = "WARN"
        row["warning"] = "price_history_unavailable"
        return row
    try:
        enriched = add_all_indicators(hist, config or {})
    except Exception:
        enriched = hist.copy()
    close = _safe_float(_last_value(enriched, "close"))
    atr = _safe_float(_last_value(enriched, "atr"))
    rsi = _safe_float(_last_value(enriched, "rsi"))
    sma20 = _safe_float(_last_value(enriched, "sma20"))
    entry = close
    stop = close - (1.5 * atr) if close is not None and atr is not None else None
    target = close + (3.0 * atr) if close is not None and atr is not None else None
    rr = ((target - entry) / (entry - stop)) if entry and stop and target and entry > stop else None
    momentum = "UNKNOWN"
    if rsi is not None:
        momentum = "STRONG" if rsi >= 55 else "WEAK" if rsi < 45 else "STABLE"
    extension = "UNKNOWN"
    if close is not None and sma20 not in (None, 0) and atr not in (None, 0):
        distance_atr = (close - sma20) / atr
        extension = "OVEREXTENDED" if distance_atr > 1.5 else "HEALTHY"
    row.update(
        {
            "status": "PASS",
            "latest_price": close,
            "actionable_entry": entry,
            "actionable_stop": stop,
            "actionable_target": target,
            "rr": rr,
            "technical_rsi": rsi,
            "technical_atr": atr,
            "technical_sma20": sma20,
            "momentum_state": momentum,
            "extension_state": extension,
            "entry_timing_status": "DIAGNOSTIC_ONLY",
            "scenario_status": "WAIT_FOR_CONFIRMATION",
            "scenario_confidence": "LOW",
            "setup_type": "DIAGNOSTIC",
            "final_trade_score": "",
            "manual_review_only": True,
            "analysis_quote_source": "yfinance",
            "analysis_quote_freshness": "DELAYED_OR_EOD",
            "scenario_thesis": "Consulta puntual para investigacion manual; no es senal operativa.",
            "warnings": "no_full_screener_no_macro_filter",
            "required_actions": "review_chart_volume_spread_news_earnings_macro_sector",
        }
    )
    return row


def save_single_ticker_deep_dive_reports(
    ticker: str,
    *,
    config: dict | None = None,
    json_out: Path = ROOT / "reports" / "single_ticker_deep_dive_latest.json",
    markdown_out: Path = ROOT / "reports" / "single_ticker_deep_dive_latest.md",
) -> dict[str, Any]:
    row = build_diagnostic_row(ticker, config=config)
    payload = {
        "status": row.get("status", "WARN"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ticker": row.get("ticker", clean_ticker(ticker)),
        "row": row,
        "json_out": str(json_out),
        "markdown_out": str(markdown_out),
        "notice": NOTICE,
        "manual_review_only": True,
        "creates_trading_signal": False,
        "creates_trigger_confirmed": False,
        "broker_execution": False,
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Analista - Consulta puntual",
        "",
        f"- status: {payload.get('status')}",
        f"- ticker: {payload.get('ticker')}",
        f"- notice: {NOTICE}",
        "",
        "## Diagnostico",
        f"- latest_price: {row.get('latest_price', '')}",
        f"- momentum_state: {row.get('momentum_state', '')}",
        f"- extension_state: {row.get('extension_state', '')}",
        f"- scenario_status: {row.get('scenario_status', '')}",
        "",
        "## Guardrails",
        "",
        "- No paso por screener completo ni filtro macro.",
        "- No crea señales.",
        "- No real order.",
    ]
    markdown_out.write_text("\n".join(lines), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="")
    parser.add_argument("--json-out", default=str(ROOT / "reports" / "single_ticker_deep_dive_latest.json"))
    parser.add_argument("--markdown-out", default=str(ROOT / "reports" / "single_ticker_deep_dive_latest.md"))
    args = parser.parse_args()
    payload = save_single_ticker_deep_dive_reports(
        args.ticker,
        json_out=Path(args.json_out),
        markdown_out=Path(args.markdown_out),
    )
    print("=== ANALISTA SINGLE TICKER DEEP DIVE ===")
    print(f"Status: {payload.get('status')}")
    print(f"Ticker: {payload.get('ticker')}")
    return 0 if payload.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
