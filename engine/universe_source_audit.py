from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

MOMENTUM_DEFAULT_SOURCES = {
    "day_gainers",
    "most_actives",
    "small_cap_gainers",
    "aggressive_small_caps",
}


def _pct(x: float) -> float:
    return round(float(x) * 100, 2)


def _split_sources(value) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [x.strip() for x in str(value).split(",") if x.strip()]


def audit_universe_sources(df: pd.DataFrame, config: dict | None = None) -> dict:
    config = config or {}
    bias_cfg = config.get("screener", {}).get("bias_control", {})

    if df.empty:
        return {
            "status": "FAIL",
            "issues": ["universo vacío"],
            "warnings": [],
            "summary": {"rows": 0},
            "recommendations": ["Revisar conectividad y fallback_tickers."],
        }

    rows = len(df)
    issues: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    max_single_source_share = bias_cfg.get("max_single_source_share", 0.45)
    max_top_sector_share = bias_cfg.get("max_top_sector_share", 0.40)
    momentum_sources = set(bias_cfg.get("momentum_sources", list(MOMENTUM_DEFAULT_SOURCES)))
    max_momentum_share = bias_cfg.get("max_momentum_sources_share", 0.60)

    source_counts: dict[str, int] = {}
    if "source_channels" in df.columns:
        for sources in df["source_channels"]:
            for source in _split_sources(sources):
                source_counts[source] = source_counts.get(source, 0) + 1
    elif "source_channel" in df.columns:
        source_counts = df["source_channel"].fillna("MISSING").astype(str).value_counts().to_dict()

    source_shares = {k: v / rows for k, v in source_counts.items()}

    if source_shares:
        top_source, top_share = max(source_shares.items(), key=lambda kv: kv[1])
        if top_share > max_single_source_share:
            warnings.append(f"concentración alta en fuente '{top_source}': {_pct(top_share)}%")
            recommendations.append("Diversificar canales de screener o bajar peso del canal dominante.")

    momentum_hits = 0
    if "source_channels" in df.columns:
        for sources in df["source_channels"]:
            srcs = set(_split_sources(sources))
            if srcs & momentum_sources:
                momentum_hits += 1
    elif "source_channel" in df.columns:
        momentum_hits = int(df["source_channel"].fillna("").isin(momentum_sources).sum())

    momentum_share = momentum_hits / rows if rows else 0
    if momentum_share > max_momentum_share:
        warnings.append(f"universo excesivamente dependiente de fuentes momentum: {_pct(momentum_share)}%")
        recommendations.append("Agregar canales de value/quality/growth no basados en movimiento diario.")

    sector_counts = {}
    sector_shares = {}
    if "sector" in df.columns:
        sector_counts = df["sector"].fillna("MISSING").astype(str).value_counts().to_dict()
        sector_shares = {k: v / rows for k, v in sector_counts.items()}
        top_sector, top_sector_share = max(sector_shares.items(), key=lambda kv: kv[1])
        if top_sector_share > max_top_sector_share:
            warnings.append(f"concentración sectorial alta en '{top_sector}': {_pct(top_sector_share)}%")
            recommendations.append("Revisar si la concentración sectorial refleja rotación real o sesgo de screener.")

    avg_hit_count = None
    if "screener_hit_count" in df.columns:
        avg_hit_count = float(pd.to_numeric(df["screener_hit_count"], errors="coerce").mean())

    low_confirmation_rate = None
    if "screener_hit_count" in df.columns:
        low_confirmation_rate = float((pd.to_numeric(df["screener_hit_count"], errors="coerce") <= 1).mean())
        if low_confirmation_rate > 0.80 and rows >= 20:
            warnings.append(f"baja confirmación multi-screener: {_pct(low_confirmation_rate)}% con hit_count <= 1")
            recommendations.append("Aumentar variedad de canales o usar universe base independiente.")

    status = "PASS"
    if issues:
        status = "FAIL"
    elif warnings:
        status = "WARN"

    return {
        "status": status,
        "summary": {
            "rows": rows,
            "source_counts": source_counts,
            "source_shares_pct": {k: _pct(v) for k, v in source_shares.items()},
            "momentum_source_share_pct": _pct(momentum_share),
            "sector_counts": sector_counts,
            "sector_shares_pct": {k: _pct(v) for k, v in sector_shares.items()},
            "avg_screener_hit_count": round(avg_hit_count, 4) if avg_hit_count is not None else None,
            "low_confirmation_rate_pct": _pct(low_confirmation_rate) if low_confirmation_rate is not None else None,
        },
        "issues": issues,
        "warnings": warnings,
        "recommendations": list(dict.fromkeys(recommendations)),
    }


def audit_universe_file(csv_path: str | Path, output_json: str | Path | None = None, config: dict | None = None) -> dict:
    path = Path(csv_path)
    df = pd.read_csv(path)
    report = audit_universe_sources(df, config=config)

    if output_json is None:
        out_dir = Path("reports/audits")
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"universe_audit_{path.stem}.json"
    else:
        output_path = Path(output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    report["output_json"] = output_path.as_posix()
    return report


def print_universe_audit(report: dict) -> None:
    print("\n=== ANALISTA UNIVERSE SOURCE AUDIT ===")
    print(f"Status: {report.get('status')}")
    summary = report.get("summary", {})
    print(f"Rows: {summary.get('rows')}")
    print(f"Momentum source share: {summary.get('momentum_source_share_pct')}%")
    print(f"Avg screener hit count: {summary.get('avg_screener_hit_count')}")
    print(f"Low confirmation rate: {summary.get('low_confirmation_rate_pct')}%")

    print("\nSource shares:")
    for k, v in (summary.get("source_shares_pct") or {}).items():
        print(f"- {k}: {v}%")

    print("\nSector shares:")
    for k, v in list((summary.get("sector_shares_pct") or {}).items())[:12]:
        print(f"- {k}: {v}%")

    if report.get("issues"):
        print("\nISSUES:")
        for i in report["issues"]:
            print(f"- {i}")

    if report.get("warnings"):
        print("\nWARNINGS:")
        for w in report["warnings"]:
            print(f"- {w}")

    if report.get("recommendations"):
        print("\nRECOMMENDATIONS:")
        for r in report["recommendations"]:
            print(f"- {r}")

    if report.get("output_json"):
        print(f"\nAudit JSON: {report['output_json']}")
