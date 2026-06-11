from __future__ import annotations

YAHOO_FINANCE = "YAHOO_FINANCE"
FINVIZ = "FINVIZ"
MARKETWATCH = "MARKETWATCH"
TRADINGVIEW_MANUAL = "TRADINGVIEW_MANUAL"
MISSING = "MISSING"
UNKNOWN = "UNKNOWN"

SOURCE_PRIORITY = [
    YAHOO_FINANCE,
    FINVIZ,
    MARKETWATCH,
    TRADINGVIEW_MANUAL,
]

SOURCE_ALIASES = {
    "yahoo": YAHOO_FINANCE,
    "yahoo_finance": YAHOO_FINANCE,
    "yfinance": YAHOO_FINANCE,
    "finviz": FINVIZ,
    "marketwatch": MARKETWATCH,
    "tradingview": TRADINGVIEW_MANUAL,
    "tradingview_free": TRADINGVIEW_MANUAL,
    "tradingview_manual": TRADINGVIEW_MANUAL,
    "manual": TRADINGVIEW_MANUAL,
    "missing": MISSING,
    "unknown": UNKNOWN,
    "none": MISSING,
    "error": UNKNOWN,
}


def normalize_source(value: object, default: str = UNKNOWN) -> str:
    text = str(value or "").strip()
    if not text:
        return default

    normalized = text.lower().replace("-", "_").replace(" ", "_")
    return SOURCE_ALIASES.get(normalized, text.upper())
