from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import json

import pandas as pd
from loguru import logger

from engine.posttest_engine import run_posttest


DEFAULT_SCAN_PATTERNS = [
    "reports/*.csv",
    "reports/history/*.csv",
]

EXCLUDE_PATTERNS = [
    "posttest",
    "audit",
    "calibration",
]


def _is_excluded(path: Path) -> bool:
    text = path.as_posix().lower()
    return any(token in text for token in EXCLUDE_PATTERNS)


def discover_scan_csvs(patterns: list[str] | None = None) -> list[Path]:
    patterns = patterns or DEFAULT_SCAN_PATTERNS
    files: list[Path] = []

    for pattern in patterns:
        files.extend(Path(".").glob(pattern))

    unique = []
    seen = set()

    for f in files:
        if not f.exists() or f.suffix.lower() != ".csv":
            continue
        if _is_excluded(f):
            continue
        key = str(f.resolve())
        if key not in seen:
            unique.append(f)
            seen.add(key)

    return sorted(unique, key=lambda p: p.stat().st_mtime)


def infer_scan_date(scan_csv: str | Path) -> pd.Timestamp | None:
    path = Path(scan_csv)

    try:
        df = pd.read_csv(path, nrows=5)
    except Exception:
        return None

    if "scan_timestamp" in df.columns and df["scan_timestamp"].notna().any():
        try:
            return pd.to_datetime(df["scan_timestamp"].dropna().iloc[0]).tz_localize(None).normalize()
        except Exception:
            pass

    try:
        return pd.Timestamp(datetime.fromtimestamp(path.stat().st_mtime)).normalize()
    except Exception:
        return None


def eligible_scans(
    scan_files: list[Path],
    min_age_days: int = 4,
    now: datetime | None = None,
) -> list[dict]:
    now_ts = pd.Timestamp(now or datetime.now()).normalize()
    out = []

    for scan in scan_files:
        scan_date = infer_scan_date(scan)
        if scan_date is None:
            continue

        age_days = int((now_ts - scan_date).days)
        if age_days >= min_age_days:
            out.append(
                {
                    "scan_csv": scan,
                    "scan_date": scan_date.date().isoformat(),
                    "age_days": age_days,
                }
            )

    return out


def posttest_output_path(scan_csv: str | Path, output_dir: str | Path = "reports/posttests") -> Path:
    scan_csv = Path(scan_csv)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"posttest_{scan_csv.stem}.csv"


def run_posttest_batch(
    patterns: list[str] | None = None,
    horizons: list[int] | None = None,
    min_age_days: int | None = None,
    output_dir: str | Path = "reports/posttests",
    overwrite: bool = False,
) -> dict:
    horizons = horizons or [4, 7, 10, 15, 21]
    min_age_days = min_age_days if min_age_days is not None else min(horizons)

    scan_files = discover_scan_csvs(patterns)
    candidates = eligible_scans(scan_files, min_age_days=min_age_days)

    results = []
    skipped = []

    for item in candidates:
        scan_csv = item["scan_csv"]
        out_path = posttest_output_path(scan_csv, output_dir=output_dir)

        if out_path.exists() and not overwrite:
            skipped.append(
                {
                    "scan_csv": scan_csv.as_posix(),
                    "reason": "posttest_exists",
                    "output_csv": out_path.as_posix(),
                }
            )
            continue

        try:
            df = run_posttest(scan_csv, horizons=horizons, output_csv=out_path)
            results.append(
                {
                    "scan_csv": scan_csv.as_posix(),
                    "scan_date": item["scan_date"],
                    "age_days": item["age_days"],
                    "output_csv": out_path.as_posix(),
                    "rows": int(len(df)),
                    "status": "OK" if len(df) else "EMPTY",
                }
            )
        except Exception as exc:
            logger.exception(f"Falló posttest batch para {scan_csv}")
            results.append(
                {
                    "scan_csv": scan_csv.as_posix(),
                    "scan_date": item["scan_date"],
                    "age_days": item["age_days"],
                    "output_csv": out_path.as_posix(),
                    "rows": 0,
                    "status": "ERROR",
                    "error": str(exc),
                }
            )

    report = {
        "status": "OK",
        "scan_files_discovered": len(scan_files),
        "eligible_scans": len(candidates),
        "posttests_created": len([r for r in results if r.get("status") == "OK"]),
        "posttests_empty": len([r for r in results if r.get("status") == "EMPTY"]),
        "posttests_error": len([r for r in results if r.get("status") == "ERROR"]),
        "skipped": skipped,
        "results": results,
    }

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    summary_path = Path(output_dir) / "posttest_batch_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    report["summary_json"] = summary_path.as_posix()
    return report


def print_batch_report(report: dict) -> None:
    print("\n=== ANALISTA POSTTEST BATCH ===")
    print(f"Scans discovered: {report.get('scan_files_discovered')}")
    print(f"Eligible scans: {report.get('eligible_scans')}")
    print(f"Posttests created: {report.get('posttests_created')}")
    print(f"Posttests empty: {report.get('posttests_empty')}")
    print(f"Posttests error: {report.get('posttests_error')}")
    print(f"Skipped: {len(report.get('skipped') or [])}")
    print(f"Summary JSON: {report.get('summary_json')}")

    results = report.get("results") or []
    if results:
        print("\nResults:")
        for r in results[:20]:
            print(f"- {r.get('status')} | {r.get('scan_csv')} -> {r.get('output_csv')} | rows={r.get('rows')}")

    skipped = report.get("skipped") or []
    if skipped:
        print("\nSkipped:")
        for s in skipped[:20]:
            print(f"- {s.get('reason')} | {s.get('scan_csv')}")
