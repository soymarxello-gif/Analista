from __future__ import annotations

from pathlib import Path
import glob
import json
import math

import pandas as pd


COMPONENT_SCORE_COLUMNS = {
    "rs_score": "relative_strength",
    "trend_score": "trend",
    "market_regime_score": "market_regime",
    "volume_score": "volume_accumulation",
    "sector_score": "sector_rotation",
    "structure_score": "structure_trigger",
    "rr_score": "risk_reward_atr",
    "liquidity_score": "liquidity",
    "momentum_score": "momentum",
    "options_score": "options_flow",
    "fundamental_score": "fundamentals",
    "sentiment_score": "sentiment",
    "data_quality_score": "data_quality",
}

GROUP_COLUMNS = [
    "signal",
    "pre_veto_signal",
    "setup_type",
    "options_bias",
    "options_confidence",
    "data_quality_confidence",
    "sector",
]


def _read_posttest_files(paths: list[str | Path]) -> pd.DataFrame:
    files: list[Path] = []

    for p in paths:
        text = str(p)
        expanded = [Path(x) for x in glob.glob(text)]
        if expanded:
            files.extend(expanded)
        else:
            files.append(Path(text))

    frames = []
    for file in files:
        if file.exists():
            df = pd.read_csv(file)
            df["_source_file"] = file.name
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def _safe_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _summarize_group(df: pd.DataFrame, group_col: str, horizon: int | None = None, min_samples: int = 3) -> pd.DataFrame:
    if group_col not in df.columns or df.empty:
        return pd.DataFrame()

    data = df.copy()
    if horizon is not None and "horizon_days" in data.columns:
        data = data[data["horizon_days"] == horizon]

    if data.empty:
        return pd.DataFrame()

    rows = []
    for value, g in data.groupby(group_col, dropna=False):
        n = len(g)
        if n < min_samples:
            continue

        ret = pd.to_numeric(g["return_close_pct"], errors="coerce")
        mfe = pd.to_numeric(g.get("mfe_pct", pd.Series(index=g.index)), errors="coerce")
        mae = pd.to_numeric(g.get("mae_pct", pd.Series(index=g.index)), errors="coerce")

        hit_rate = float((ret > 0).mean()) if len(ret.dropna()) else math.nan
        avg_return = float(ret.mean()) if len(ret.dropna()) else math.nan
        median_return = float(ret.median()) if len(ret.dropna()) else math.nan
        avg_mfe = float(mfe.mean()) if len(mfe.dropna()) else math.nan
        avg_mae = float(mae.mean()) if len(mae.dropna()) else math.nan

        target_hit = float(pd.to_numeric(g.get("hit_target", pd.Series(False, index=g.index)), errors="coerce").mean())
        stop_hit = float(pd.to_numeric(g.get("hit_stop", pd.Series(False, index=g.index)), errors="coerce").mean())

        # Expectancy proxy: average close return plus asymmetry from MFE/MAE.
        expectancy_proxy = avg_return
        if not math.isnan(avg_mfe) and not math.isnan(avg_mae):
            expectancy_proxy = avg_return + 0.25 * (avg_mfe + avg_mae)

        rows.append(
            {
                "group": group_col,
                "value": "MISSING" if pd.isna(value) else value,
                "horizon_days": horizon if horizon is not None else "ALL",
                "samples": n,
                "hit_rate": hit_rate,
                "avg_return_close": avg_return,
                "median_return_close": median_return,
                "avg_mfe": avg_mfe,
                "avg_mae": avg_mae,
                "target_hit_rate": target_hit,
                "stop_hit_rate": stop_hit,
                "expectancy_proxy": expectancy_proxy,
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["expectancy_proxy", "samples"], ascending=[False, False]).reset_index(drop=True)
    return out


def summarize_posttest(posttest_paths: list[str | Path], min_samples: int = 3) -> dict:
    df = _read_posttest_files(posttest_paths)

    if df.empty:
        return {
            "status": "NO_DATA",
            "summary": {},
            "group_summaries": {},
            "warning": "No encontré archivos post-test válidos.",
        }

    numeric_cols = [
        "horizon_days",
        "return_close_pct",
        "mfe_pct",
        "mae_pct",
        "final_score",
        "rr",
        "options_score",
        "data_quality_score",
    ]
    df = _safe_numeric(df, numeric_cols)

    horizons = sorted([int(x) for x in df["horizon_days"].dropna().unique()]) if "horizon_days" in df.columns else []

    summary = {
        "rows": len(df),
        "tickers": int(df["ticker"].nunique()) if "ticker" in df.columns else None,
        "horizons": horizons,
        "sources": sorted(df["_source_file"].dropna().unique().tolist()) if "_source_file" in df.columns else [],
        "avg_return_close": float(df["return_close_pct"].mean()) if "return_close_pct" in df.columns else None,
        "median_return_close": float(df["return_close_pct"].median()) if "return_close_pct" in df.columns else None,
        "hit_rate": float((df["return_close_pct"] > 0).mean()) if "return_close_pct" in df.columns else None,
    }

    group_summaries: dict[str, list[dict]] = {}

    for group_col in GROUP_COLUMNS:
        if group_col not in df.columns:
            continue

        all_summary = _summarize_group(df, group_col, horizon=None, min_samples=min_samples)
        if not all_summary.empty:
            group_summaries[f"{group_col}_ALL"] = all_summary.to_dict(orient="records")

        for h in horizons:
            h_summary = _summarize_group(df, group_col, horizon=h, min_samples=min_samples)
            if not h_summary.empty:
                group_summaries[f"{group_col}_{h}d"] = h_summary.to_dict(orient="records")

    return {
        "status": "OK",
        "summary": summary,
        "group_summaries": group_summaries,
    }


def _current_weights_from_config(config: dict) -> dict:
    return {k: float(v) for k, v in config.get("scoring_weights", {}).items()}


def _normalize_weights(weights: dict[str, float], target_sum: float = 100.0) -> dict[str, float]:
    total = sum(max(float(v), 0.0) for v in weights.values())
    if total <= 0:
        return weights
    return {k: round(max(float(v), 0.0) / total * target_sum, 4) for k, v in weights.items()}


def calibrate_weights_from_posttest(
    posttest_paths: list[str | Path],
    config: dict,
    horizon: int = 10,
    min_samples: int = 20,
    max_delta_pct: float = 0.20,
) -> dict:
    """
    Evidence-based first-pass calibration.

    Uses Spearman correlation between component scores and future close return.
    This is not automatic optimization. It proposes conservative deltas only.
    """
    df = _read_posttest_files(posttest_paths)

    if df.empty:
        return {
            "status": "NO_DATA",
            "message": "No hay post-tests para calibrar.",
            "proposed_weights": _current_weights_from_config(config),
        }

    df = _safe_numeric(df, ["horizon_days", "return_close_pct"] + list(COMPONENT_SCORE_COLUMNS.keys()))

    if "horizon_days" in df.columns:
        df = df[df["horizon_days"] == horizon]

    df = df.dropna(subset=["return_close_pct"])

    if len(df) < min_samples:
        return {
            "status": "INSUFFICIENT_SAMPLES",
            "message": f"Muestras insuficientes para calibrar: {len(df)} < {min_samples}.",
            "samples": len(df),
            "horizon_days": horizon,
            "proposed_weights": _current_weights_from_config(config),
        }

    current = _current_weights_from_config(config)
    rows = []
    proposed = current.copy()

    for score_col, weight_key in COMPONENT_SCORE_COLUMNS.items():
        if score_col not in df.columns or weight_key not in current:
            continue

        subset = df[[score_col, "return_close_pct"]].dropna()
        if len(subset) < min_samples:
            continue

        ranked = subset[[score_col, "return_close_pct"]].rank(method="average")
        corr = ranked[score_col].corr(ranked["return_close_pct"])
        
        if pd.isna(corr):
            corr = 0.0

        # Convert correlation to conservative multiplier.
        # corr +0.30 => +20% cap; corr -0.30 => -20% cap.
        raw_delta = float(corr) / 0.30 * max_delta_pct
        delta = max(-max_delta_pct, min(max_delta_pct, raw_delta))
        multiplier = 1.0 + delta

        old_weight = current[weight_key]
        proposed[weight_key] = old_weight * multiplier

        rows.append(
            {
                "score_col": score_col,
                "weight_key": weight_key,
                "samples": len(subset),
                "spearman_corr": round(float(corr), 4),
                "old_weight": old_weight,
                "raw_multiplier": round(multiplier, 4),
                "uncapped_new_weight": round(old_weight * multiplier, 4),
            }
        )

    proposed_norm = _normalize_weights(proposed, target_sum=100.0)

    detail = pd.DataFrame(rows)
    if not detail.empty:
        detail["proposed_weight"] = detail["weight_key"].map(proposed_norm)
        detail["delta_weight"] = detail["proposed_weight"] - detail["old_weight"]
        detail = detail.sort_values("spearman_corr", ascending=False).reset_index(drop=True)

    return {
        "status": "OK",
        "horizon_days": horizon,
        "samples": len(df),
        "method": "spearman_correlation_conservative_capped",
        "max_delta_pct": max_delta_pct,
        "current_weights": current,
        "proposed_weights": proposed_norm,
        "details": detail.to_dict(orient="records") if not detail.empty else [],
        "warning": "Propuesta exploratoria. No aplicar automáticamente sin validar out-of-sample.",
    }


def save_calibration_report(report: dict, output_json: str | Path, output_csv: str | Path | None = None) -> None:
    output_json = Path(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    if output_csv and report.get("details"):
        output_csv = Path(output_csv)
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(report["details"]).to_csv(output_csv, index=False)
