from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REQUIRED_OPERATIONAL_COLUMNS = [
    "ticker",
    "signal",
    "final_score",
    "entry",
    "stop",
    "target",
    "rr",
    "setup_type",
    "trend_score",
    "liquidity_pass",
    "data_quality_score",
    "data_quality_confidence",
]

RECOMMENDED_COLUMNS = [
    "pre_veto_signal",
    "veto_reasons",
    "reason_summary",
    "bid_ask_valid",
    "bid_ask_warning",
    "spread_validated_pct",
    "options_score",
    "options_bias",
    "options_confidence",
    "options_liquidity_score",
    "options_crowded_bullish",
    "stop_method",
    "target_method",
    "risk_pct",
    "reward_pct",
    "recommendation",
    "all_veto_reasons",
    "penalty_reasons",
    "quote_status",
    "execution_quote_quality",
    "asset_quality_score",
    "setup_quality_score",
    "context_score",
    "institutional_score",
    "final_trade_score",
    "score_breakdown",
    "stop_atr_multiple",
    "stop_atr_status",
    "options_crowded_bearish",
    "legacy_rank",
    "trade_score_rank",
    "operational_rank",
    "rank_delta_trade_vs_legacy",
    "manual_quote_check_required",
    "quote_recheck_priority",
    "quote_recheck_reason",
]


def _pct(value: float) -> float:
    return round(float(value) * 100, 2)


def _safe_value_counts(df: pd.DataFrame, col: str) -> dict:
    if col not in df.columns:
        return {}
    return df[col].fillna("MISSING").astype(str).value_counts().to_dict()


def _missing_columns(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c not in df.columns]


def _explode_veto_reasons(df: pd.DataFrame) -> pd.Series:
    if "veto_reasons" not in df.columns:
        return pd.Series(dtype=str)
    s = df["veto_reasons"].fillna("").astype(str).str.split(",").explode().str.strip()
    return s[s != ""]


def audit_scan_dataframe(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "status": "FAIL",
            "summary": {"rows": 0},
            "issues": ["scan vacío"],
            "recommendations": ["Revisar screener, filtros de liquidez o fuente de datos."],
        }

    issues: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    missing_required = _missing_columns(df, REQUIRED_OPERATIONAL_COLUMNS)
    missing_recommended = _missing_columns(df, RECOMMENDED_COLUMNS)

    if missing_required:
        issues.append("faltan columnas operativas requeridas: " + ", ".join(missing_required))
        recommendations.append("Corregir engine/scanner_engine.py para incluir columnas operativas requeridas en row.")

    if missing_recommended:
        warnings.append("faltan columnas recomendadas: " + ", ".join(missing_recommended))

    rows = len(df)

    signal_counts = _safe_value_counts(df, "signal")
    veto_count = int(signal_counts.get("VETO", 0))
    trigger_count = int(signal_counts.get("TRIGGER_CONFIRMED", 0))
    legacy_buy_count = int(signal_counts.get("BUY_SETUP_ACTIVE", 0))
    ready_count = int(signal_counts.get("READY_WAIT_TRIGGER", 0))
    watch_count = int(signal_counts.get("WATCHLIST", 0))

    veto_rate = veto_count / rows if rows else 0

    if rows >= 10 and veto_rate >= 0.95:
        warnings.append(f"veto_rate muy alto: {_pct(veto_rate)}%")
        recommendations.append("Revisar veto_reasons; si domina rr_below_minimum, validar columnas rr/stop/target.")

    veto_reasons = _explode_veto_reasons(df)
    veto_reason_counts = veto_reasons.value_counts().to_dict() if not veto_reasons.empty else {}

    rr_missing_rate = None
    if "rr" in df.columns:
        rr_missing_rate = float(df["rr"].isna().mean())
        if rr_missing_rate > 0:
            warnings.append(f"rr faltante en {_pct(rr_missing_rate)}% de filas")
        if rr_missing_rate >= 0.50:
            issues.append("rr faltante en más del 50% de filas")
            recommendations.append("Verificar que row incluya rr_data.get('rr') dentro de scanner_engine.py.")

    if veto_reason_counts.get("rr_below_minimum", 0) == rows and rows >= 5:
        warnings.append("todos los candidatos tienen rr_below_minimum")
        recommendations.append("Auditar si rr está faltante o si el nuevo cálculo R:R quedó demasiado estricto.")

    low_quality_rate = None
    if "data_quality_confidence" in df.columns:
        low_quality_rate = float((df["data_quality_confidence"].fillna("").astype(str).str.upper() == "LOW").mean())
        if low_quality_rate >= 0.25:
            warnings.append(f"data_quality LOW elevado: {_pct(low_quality_rate)}%")
            recommendations.append("Revisar campos críticos faltantes y calidad de metadata/opciones.")

    if "missing_critical_fields" in df.columns:
        missing_core_col = (
            "core_missing_fields"
            if "core_missing_fields" in df.columns
            else "missing_critical_fields"
        )

        if missing_core_col in df.columns:
            missing_core_rate = float(
                df[missing_core_col]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
                .mean()
            )
            if missing_core_rate >= 0.10:
                warnings.append(f"campos críticos core faltantes en {_pct(missing_core_rate)}% de filas")

    if "bid_ask_valid" in df.columns:
        invalid_bid_ask_rate = float((df["bid_ask_valid"] == False).mean())  # noqa: E712
        if invalid_bid_ask_rate >= 0.25:
            warnings.append(f"bid/ask inválido o stale en {_pct(invalid_bid_ask_rate)}% de filas")
            recommendations.append("No usar bid/ask de Yahoo como veto automático; validar ejecución manualmente.")

    if "options_confidence" in df.columns:
        low_options_conf_rate = float((df["options_confidence"].fillna("").astype(str).str.upper() == "LOW").mean())
        if low_options_conf_rate >= 0.25:
            warnings.append(f"options_confidence LOW elevado: {_pct(low_options_conf_rate)}%")

    if "options_bias" in df.columns:
        crowded_rate = float(
            df["options_bias"]
            .fillna("")
            .astype(str)
            .str.upper()
            .isin(["CROWDED_BULLISH", "CROWDED_BEARISH"])
            .mean()
        )
        if crowded_rate >= 0.20:
            warnings.append(f"flujo crowded elevado: {_pct(crowded_rate)}%")
            recommendations.append("Evitar tratar calls crowded como confirmación bullish limpia.")
        unknown_options_rate = float(
            (
                df["options_bias"]
                .fillna("")
                .astype(str)
                .str.upper()
                == "UNKNOWN_OPTIONS_FLOW"
            ).mean()
        )
        if unknown_options_rate >= 0.50:
            warnings.append(f"options flow desconocido en {_pct(unknown_options_rate)}% de filas")
            recommendations.append(
                "Opciones no disponibles o no consultadas para gran parte del universo; tratar institutional_score como confirmatorio, no como filtro."
            )

    if "pre_veto_signal" in df.columns and "signal" in df.columns:
        blocked_buy = df[
            (df["pre_veto_signal"].isin(["TRIGGER_CONFIRMED", "BUY_SETUP_ACTIVE"]))
            & (df["signal"] == "VETO")
        ]
        if len(blocked_buy) > 0:
            warnings.append(f"{len(blocked_buy)} candidatos habrían sido BUY pre-veto, pero fueron bloqueados")
            recommendations.append("Revisar esos tickers manualmente para confirmar si el veto es legítimo o problema de datos.")

    score_stats = {}
    for col in [
        "final_score",
        "final_trade_score",
        "asset_quality_score",
        "setup_quality_score",
        "rr",
        "liquidity_score",
        "data_quality_score",
        "options_score",
        "stop_atr_multiple",
    ]:
        if col in df.columns:
            score_stats[col] = {
                "mean": round(float(pd.to_numeric(df[col], errors="coerce").mean()), 4),
                "median": round(float(pd.to_numeric(df[col], errors="coerce").median()), 4),
                "min": round(float(pd.to_numeric(df[col], errors="coerce").min()), 4),
                "max": round(float(pd.to_numeric(df[col], errors="coerce").max()), 4),
            }

    sector_counts = _safe_value_counts(df, "sector")
    setup_counts = _safe_value_counts(df, "setup_type")
    options_counts = _safe_value_counts(df, "options_bias")

    top_candidates_cols = [
        "rank",
        "ticker",
        "signal",
        "recommendation",
        "setup_type",
        "final_trade_score",
        "asset_quality_score",
        "setup_quality_score",
        "final_score",
        "rr",
        "stop_atr_multiple",
        "quote_status",
        "execution_quote_quality",
        "veto_reasons",
        "penalty_reasons",
        "reason_summary",
        "data_quality_confidence",
        "options_bias",
        "options_confidence",
        "liquidity_score",
    ]
    top_candidates_cols = [c for c in top_candidates_cols if c in df.columns]

    sort_col = "final_trade_score" if "final_trade_score" in df.columns else "final_score"

    if sort_col in df.columns and top_candidates_cols:
        top_candidates = (
            df.sort_values(sort_col, ascending=False)[top_candidates_cols]
            .head(10)
            .to_dict(orient="records")
        )
    else:
        top_candidates = []

    status = "PASS"
    if issues:
        status = "FAIL"
    elif warnings:
        status = "WARN"

    return {
        "status": status,
        "summary": {
            "rows": rows,
            "signals": signal_counts,
            "veto_rate_pct": _pct(veto_rate),
            "buy_ready_watch_count": trigger_count + legacy_buy_count + ready_count + watch_count,
            "missing_required_columns": missing_required,
            "missing_recommended_columns": missing_recommended,
        },
        "score_stats": score_stats,
        "veto_reason_counts": veto_reason_counts,
        "sector_counts": sector_counts,
        "setup_counts": setup_counts,
        "options_bias_counts": options_counts,
        "issues": issues,
        "warnings": warnings,
        "recommendations": list(dict.fromkeys(recommendations)),
        "top_candidates": top_candidates,
    }


def audit_scan_file(scan_csv: str | Path, output_json: str | Path | None = None) -> dict:
    path = Path(scan_csv)
    df = pd.read_csv(path)
    report = audit_scan_dataframe(df)

    if output_json is None:
        out_dir = Path("reports/audits")
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"audit_{path.stem}.json"
    else:
        output_path = Path(output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    report["output_json"] = str(output_path)
    return report


def print_audit_report(report: dict) -> None:
    print("\n=== ANALISTA SCAN AUDIT ===")
    print(f"Status: {report.get('status')}")
    print(f"Rows: {report.get('summary', {}).get('rows')}")
    print(f"Veto rate: {report.get('summary', {}).get('veto_rate_pct')}%")
    print(f"Signals: {report.get('summary', {}).get('signals')}")

    issues = report.get("issues") or []
    warnings = report.get("warnings") or []
    recommendations = report.get("recommendations") or []

    if issues:
        print("\nISSUES:")
        for i in issues:
            print(f"- {i}")

    if warnings:
        print("\nWARNINGS:")
        for w in warnings:
            print(f"- {w}")

    if recommendations:
        print("\nRECOMMENDATIONS:")
        for r in recommendations:
            print(f"- {r}")

    print(f"\nAudit JSON: {report.get('output_json', 'not saved')}")
