from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import yfinance as yf
from loguru import logger


DEFAULT_HORIZONS = [4, 7, 10, 15, 21]


def _infer_scan_date(scan_path: Path, scan_df: pd.DataFrame) -> pd.Timestamp:
    if "scan_timestamp" in scan_df.columns and scan_df["scan_timestamp"].notna().any():
        return pd.to_datetime(scan_df["scan_timestamp"].dropna().iloc[0]).tz_localize(None).normalize()

    # Fallback: file modification date.
    return pd.Timestamp(datetime.fromtimestamp(scan_path.stat().st_mtime)).normalize()


def _download_history(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={c: c.lower().replace(" ", "_") for c in df.columns})
    return df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])


def _get_entry_idx(hist: pd.DataFrame, scan_date: pd.Timestamp) -> int | None:
    if hist.empty:
        return None
    dates = pd.to_datetime(hist.index).tz_localize(None).normalize()
    candidates = [i for i, d in enumerate(dates) if d >= scan_date]
    return candidates[0] if candidates else None


def run_posttest(
    scan_csv: str | Path,
    horizons: list[int] | None = None,
    output_csv: str | Path | None = None,
) -> pd.DataFrame:
    scan_path = Path(scan_csv)
    horizons = horizons or DEFAULT_HORIZONS

    scan_df = pd.read_csv(scan_path)
    if scan_df.empty:
        raise ValueError(f"Scan vacío: {scan_path}")

    scan_date = _infer_scan_date(scan_path, scan_df)
    max_h = max(horizons)

    start = scan_date - timedelta(days=10)
    end = scan_date + timedelta(days=max_h * 2 + 14)

    rows = []

    for _, row in scan_df.iterrows():
        ticker = str(row.get("ticker", "")).upper().strip()
        if not ticker:
            continue

        try:
            hist = _download_history(ticker, start, end)
        except Exception as exc:
            logger.warning(f"Post-test: falló descarga {ticker}: {exc}")
            continue

        entry_idx = _get_entry_idx(hist, scan_date)
        if entry_idx is None:
            continue

        entry_price = row.get("entry")
        try:
            entry_price = float(entry_price)
        except Exception:
            entry_price = float(hist.iloc[entry_idx]["close"])

        stop = row.get("stop")
        target = row.get("target")
        try:
            stop = float(stop)
        except Exception:
            stop = None
        try:
            target = float(target)
        except Exception:
            target = None

        base = {
            "scan_file": scan_path.name,
            "scan_date": scan_date.date().isoformat(),
            "ticker": ticker,
            "signal": row.get("signal"),
            "setup_type": row.get("setup_type"),
            "final_score": row.get("final_score"),
            "options_bias": row.get("options_bias"),
            "entry": entry_price,
            "stop": stop,
            "target": target,
        }

        for h in horizons:
            h_idx = entry_idx + h
            if h_idx >= len(hist):
                continue

            window = hist.iloc[entry_idx : h_idx + 1]
            close_h = float(hist.iloc[h_idx]["close"])
            high_max = float(window["high"].max())
            low_min = float(window["low"].min())

            ret_close = close_h / entry_price - 1
            mfe = high_max / entry_price - 1
            mae = low_min / entry_price - 1

            hit_target = bool(target is not None and high_max >= target)
            hit_stop = bool(stop is not None and low_min <= stop)

            # Approximate sequence with daily bars only: conservative if both hit.
            outcome = "OPEN"
            if hit_target and hit_stop:
                outcome = "BOTH_HIT_DAILY_UNKNOWN_SEQUENCE"
            elif hit_target:
                outcome = "TARGET_HIT"
            elif hit_stop:
                outcome = "STOP_HIT"
            elif ret_close > 0:
                outcome = "POSITIVE_CLOSE"
            else:
                outcome = "NEGATIVE_CLOSE"

            rows.append(
                {
                    **base,
                    "horizon_days": h,
                    "close_h": close_h,
                    "return_close_pct": ret_close,
                    "mfe_pct": mfe,
                    "mae_pct": mae,
                    "hit_target": hit_target,
                    "hit_stop": hit_stop,
                    "outcome": outcome,
                }
            )

    out = pd.DataFrame(rows)

    if output_csv:
        output_path = Path(output_csv)
    else:
        out_dir = Path("reports/posttests")
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"posttest_{scan_path.stem}.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False, float_format="%.4f")
    logger.info(f"Post-test guardado en {output_path}")

    return out
