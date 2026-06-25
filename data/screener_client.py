from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


@dataclass
class ScreenerResult:
    dataframe: pd.DataFrame
    used_fallback: bool
    warnings: list[str]


def _extract_quotes(payload: Any) -> list[dict]:
    """Best-effort parser for yfinance.screen responses."""
    if payload is None:
        return []
    if isinstance(payload, dict):
        if "quotes" in payload and isinstance(payload["quotes"], list):
            return payload["quotes"]
        if "finance" in payload:
            return payload.get("finance", {}).get("result", [{}])[0].get("quotes", [])
        if "body" in payload and isinstance(payload["body"], dict):
            return payload["body"].get("quotes", [])
    if isinstance(payload, list):
        return payload
    return []


def _first_non_null(series: pd.Series):
    vals = series.dropna()
    if vals.empty:
        return None
    for value in vals:
        if str(value).strip() not in {"", "nan", "None"}:
            return value
    return vals.iloc[0]


def _join_unique(series: pd.Series) -> str:
    values = []
    seen = set()
    for value in series.dropna().astype(str):
        value = value.strip()
        if not value or value in seen:
            continue
        values.append(value)
        seen.add(value)
    return ",".join(values)


def _channel_weight(channel_name: str, screener_cfg: dict) -> float:
    weights = screener_cfg.get("channel_source_weights", {})
    return float(weights.get(channel_name, 1.0))


def _quote_to_row(q: dict, channel_name: str, rank_in_channel: int, channel_weight: float) -> dict | None:
    symbol = q.get("symbol") or q.get("ticker")
    if not symbol:
        return None

    market_cap = q.get("marketCap") or q.get("intradaymarketcap")
    price = q.get("regularMarketPrice") or q.get("intradayprice")

    return {
        "ticker": str(symbol).upper().strip(),
        "company": q.get("shortName") or q.get("longName") or q.get("name"),
        "exchange": q.get("exchange"),
        "quote_type": q.get("quoteType"),
        "sector": q.get("sector"),
        "industry": q.get("industry"),
        "price": price,
        "market_cap": market_cap,
        "source_channel": channel_name,
        "source_rank": rank_in_channel,
        "source_weight": channel_weight,
    }


def _aggregate_rows(df: pd.DataFrame, screener_cfg: dict) -> pd.DataFrame:
    if df.empty:
        return df

    numeric_cols = ["price", "market_cap", "source_rank", "source_weight"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    grouped = []

    for ticker, g in df.groupby("ticker", sort=False):
        source_channels = _join_unique(g["source_channel"])
        hit_count = int(g["source_channel"].nunique())
        weighted_hits = float(g.drop_duplicates("source_channel")["source_weight"].sum())

        # Lower average rank is better.
        avg_source_rank = float(g["source_rank"].mean()) if "source_rank" in g.columns else None
        best_source_rank = float(g["source_rank"].min()) if "source_rank" in g.columns else None

        primary_source_channel = None
        if "source_weight" in g.columns:
            sorted_sources = g.sort_values(["source_weight", "source_rank"], ascending=[False, True])
            primary_source_channel = sorted_sources["source_channel"].iloc[0]
        else:
            primary_source_channel = g["source_channel"].iloc[0]

        # A simple source quality score: more independent screens and stronger screen weights.
        # Bounded later to avoid dominating downstream scoring.
        source_quality_score = min(1.0, (weighted_hits / 3.0) + min(hit_count, 3) * 0.10)

        grouped.append(
            {
                "ticker": ticker,
                "company": _first_non_null(g.get("company", pd.Series(dtype=object))),
                "exchange": _first_non_null(g.get("exchange", pd.Series(dtype=object))),
                "quote_type": _first_non_null(g.get("quote_type", pd.Series(dtype=object))),
                "sector": _first_non_null(g.get("sector", pd.Series(dtype=object))),
                "industry": _first_non_null(g.get("industry", pd.Series(dtype=object))),
                "price": _first_non_null(g.get("price", pd.Series(dtype=object))),
                "market_cap": _first_non_null(g.get("market_cap", pd.Series(dtype=object))),
                "source_channel": primary_source_channel,
                "source_channels": source_channels,
                "screener_hit_count": hit_count,
                "screener_weighted_hits": round(weighted_hits, 4),
                "avg_source_rank": round(avg_source_rank, 4) if avg_source_rank is not None else None,
                "best_source_rank": best_source_rank,
                "source_quality_score": round(source_quality_score, 4),
            }
        )

    out = pd.DataFrame(grouped)

    sort_cols = []
    ascending = []

    if "screener_weighted_hits" in out.columns:
        sort_cols.append("screener_weighted_hits")
        ascending.append(False)
    if "screener_hit_count" in out.columns:
        sort_cols.append("screener_hit_count")
        ascending.append(False)
    if "best_source_rank" in out.columns:
        sort_cols.append("best_source_rank")
        ascending.append(True)
    if "market_cap" in out.columns:
        sort_cols.append("market_cap")
        ascending.append(False)

    if sort_cols:
        out = out.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)

    max_universe = screener_cfg.get("max_universe_after_dedupe")
    if max_universe:
        out = out.head(int(max_universe)).reset_index(drop=True)

    return out


def run_screeners(config: dict) -> ScreenerResult:
    warnings: list[str] = []
    rows: list[dict] = []
    used_fallback = False

    screener_cfg = config.get("screener", {})
    channels = screener_cfg.get("channels", {})
    cache_dir = Path("cache/screener")
    cache_dir.mkdir(parents=True, exist_ok=True)

    if yf is None:
        warnings.append("yfinance no está disponible. Se usará lista fallback.")
    else:
        for channel_name, channel_cfg in channels.items():
            if not channel_cfg or not channel_cfg.get("enabled", False):
                continue

            count = channel_cfg.get("max_results", screener_cfg.get("max_results_per_query", 250))
            channel_weight = _channel_weight(channel_name, screener_cfg)

            try:
                payload = yf.screen(channel_name, count=count)
                if config.get("development", {}).get("save_raw_screener_response", True):
                    with (cache_dir / f"{channel_name}.json").open("w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

                quotes = _extract_quotes(payload)
                if not quotes:
                    warnings.append(f"Screener '{channel_name}' sin quotes.")

                for rank, q in enumerate(quotes, start=1):
                    row = _quote_to_row(q, channel_name, rank_in_channel=rank, channel_weight=channel_weight)
                    if row:
                        rows.append(row)

            except Exception as exc:
                warnings.append(f"Fallo screener '{channel_name}': {exc}")

    if not rows:
        used_fallback = True
        tickers = screener_cfg.get("fallback_tickers", [])
        rows = [
            {
                "ticker": t,
                "source_channel": "manual_fallback",
                "source_channels": "manual_fallback",
                "screener_hit_count": 1,
                "screener_weighted_hits": 0.5,
                "source_quality_score": 0.25,
            }
            for t in tickers
        ]
        warnings.append("Se usó lista fallback manual de tickers.")

    df = pd.DataFrame(rows)
    if df.empty:
        return ScreenerResult(df, used_fallback, warnings)

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df = df[df["ticker"] != ""].reset_index(drop=True)

    df = _aggregate_rows(df, screener_cfg)

    return ScreenerResult(df, used_fallback, warnings)
