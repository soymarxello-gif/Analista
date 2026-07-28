from __future__ import annotations

from pathlib import Path

NO_REAL_ORDER_NOTICE = "manual review only; no real order"

FORBIDDEN_TERMS = {
    "send_order",
    "place_order",
    "buy_order",
    "sell_order",
    "broker",
    "ibapi",
    "alpaca",
    "interactivebrokers",
    "robinhood",
    "real_order",
}


def scan_file_for_forbidden_terms(path: Path | str) -> dict:
    target = Path(path)
    if not target.exists():
        return {"ok": False, "path": str(target), "hits": [], "error": "file_missing"}
    try:
        text = target.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception as exc:
        return {"ok": False, "path": str(target), "hits": [], "error": str(exc)}
    hits = sorted(term for term in FORBIDDEN_TERMS if term.lower() in text)
    return {"ok": not hits, "path": str(target), "hits": hits, "error": ""}
