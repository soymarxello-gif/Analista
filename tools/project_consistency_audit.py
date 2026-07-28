from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

LEGACY_TERMS = [
    "BUY_SETUP_ACTIVE",
    "NEUTRAL_NO_DATA",
    "NEUTRAL_DISABLED",
    "NEUTRAL_CROWDED",
    '"BULLISH"',
    '"BEARISH"',
    '"NEUTRAL"',
]

ALLOWED_LEGACY_FILES = {
    "tests",
    "reports",
    "cache",
    ".venv",
    ".pytest_cache",
    "__pycache__",
}

ALLOWED_LEGACY_PATHS = {
    Path("tools/project_consistency_audit.py"),
    Path("validate_latest_scan_p0.py"),
    Path("engine/scanner_engine.py"),
    Path("engine/scan_audit_engine.py"),
    Path("scoring/signal_classifier.py"),
}

REQUIRED_CONFIG_PATHS = [
    ("strategy", "direction"),
    ("strategy", "horizon_days"),
    ("strategy", "portfolio_construction"),
    ("signals", "buy_setup_active_enabled"),
    ("filters", "min_price"),
    ("filters", "min_market_cap_usd"),
    ("risk_profile", "mode"),
    ("risk_profile", "stop_atr_multiple"),
]

REQUIRED_SCAN_COLUMNS = [
    "rank",
    "legacy_rank",
    "trade_score_rank",
    "operational_rank",
    "rank_delta_trade_vs_legacy",
    "ticker",
    "signal",
    "recommendation",
    "setup_type",
    "final_score",
    "final_trade_score",
    "asset_quality_score",
    "setup_quality_score",
    "context_score",
    "institutional_score",
    "score_breakdown",
    "quote_status",
    "execution_quote_quality",
    "all_veto_reasons",
    "penalty_reasons",
    "actionable_entry",
    "actionable_stop",
    "actionable_target",
    "theoretical_entry",
    "theoretical_stop",
    "theoretical_target",
    "atr",
    "stop_atr_multiple",
    "stop_atr_status",
    "options_bias",
    "options_confidence",
    "options_crowded_bullish",
    "options_crowded_bearish",
    "core_data_quality_score",
    "market_data_quality_score",
    "fundamental_data_quality_score",
    "options_data_quality_score",
    "execution_data_quality_score",
    "core_missing_fields",
    "market_missing_fields",
    "fundamental_missing_fields",
    "options_missing_fields",
    "manual_quote_check_required",
    "quote_recheck_priority",
    "quote_recheck_reason",
]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_nested(config: dict, keys: tuple[str, ...]):
    cur = config
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _is_ignored(path: Path) -> bool:
    rel = path.relative_to(ROOT)

    if rel in ALLOWED_LEGACY_PATHS:
        return True

    rel_parts = set(rel.parts)
    return bool(rel_parts & ALLOWED_LEGACY_FILES)


def audit_legacy_terms() -> list[str]:
    findings: list[str] = []

    for path in ROOT.rglob("*.py"):
        if _is_ignored(path):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for term in LEGACY_TERMS:
            if term in text:
                findings.append(f"{path.relative_to(ROOT)} contiene {term}")

    return findings


def audit_config() -> list[str]:
    issues: list[str] = []

    config = _load_yaml(ROOT / "config.yaml")
    if not config:
        return ["config.yaml no existe o está vacío"]

    for keys in REQUIRED_CONFIG_PATHS:
        value = _get_nested(config, keys)
        if value is None:
            issues.append("config.yaml falta: " + ".".join(keys))

    if _get_nested(config, ("strategy", "direction")) != "long_only":
        issues.append("strategy.direction debe ser long_only")

    if _get_nested(config, ("strategy", "portfolio_construction")) is not False:
        issues.append("strategy.portfolio_construction debe ser false")

    if _get_nested(config, ("signals", "buy_setup_active_enabled")) is not False:
        issues.append("signals.buy_setup_active_enabled debe ser false")

    min_price = _get_nested(config, ("filters", "min_price"))
    if min_price != 10:
        issues.append("filters.min_price debe ser 10")

    min_market_cap = _get_nested(config, ("filters", "min_market_cap_usd"))
    if min_market_cap != 2_500_000_000:
        issues.append("filters.min_market_cap_usd debe ser 2500000000")

    return issues


def audit_latest_scan() -> list[str]:
    issues: list[str] = []

    csv_path = ROOT / "reports" / "latest_scan_audited.csv"
    if not csv_path.exists():
        return ["reports/latest_scan_audited.csv no existe"]

    df = pd.read_csv(csv_path)

    missing = [c for c in REQUIRED_SCAN_COLUMNS if c not in df.columns]
    if missing:
        issues.append("CSV falta columnas: " + ", ".join(missing))

    if "rank" in df.columns and "operational_rank" in df.columns:
        if not (df["rank"] == df["operational_rank"]).all():
            issues.append("rank no coincide con operational_rank")

    if "signal" in df.columns:
        signals = set(df["signal"].dropna().astype(str))
        if "BUY_SETUP_ACTIVE" in signals:
            issues.append("CSV contiene BUY_SETUP_ACTIVE")

        if ((df["signal"].astype(str) == "VETO") & (df["rank"] <= 20)).any():
            issues.append("VETO aparece en top 20 operativo")

    if "options_bias" in df.columns:
        legacy_options = {
            "NEUTRAL_NO_DATA",
            "NEUTRAL_DISABLED",
            "NEUTRAL_CROWDED",
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
        }
        found = sorted(set(df["options_bias"].dropna().astype(str)) & legacy_options)
        if found:
            issues.append("CSV contiene options_bias legacy: " + ", ".join(found))

    if {"signal", "execution_quote_quality"}.issubset(df.columns):
        bad = df[
            (df["signal"].astype(str) == "TRIGGER_CONFIRMED")
            & (df["execution_quote_quality"].astype(str) == "LOW")
        ]
        if len(bad) > 0:
            issues.append("TRIGGER_CONFIRMED con execution_quote_quality LOW")

    if {"signal", "setup_type"}.issubset(df.columns):
        recommendation = (
            df["recommendation"].astype(str).str.upper()
            if "recommendation" in df.columns
            else pd.Series("", index=df.index)
        )
        technical_prefilter_failed = (
            df.get("technical_prefilter_status", pd.Series("", index=df.index))
            .fillna("")
            .astype(str)
            .str.upper()
            .eq("FAIL")
        )
        allowed_prefilter_avoid = (
            technical_prefilter_failed
            & df["signal"].astype(str).str.upper().eq("AVOID")
            & recommendation.eq("AVOID_FOR_NOW")
        )
        bad_setup = df[
            (df["setup_type"].astype(str) == "NO_VALID_SETUP")
            & (df["signal"].astype(str) != "VETO")
            & ~allowed_prefilter_avoid
        ]
        if len(bad_setup) > 0:
            issues.append("NO_VALID_SETUP fuera de VETO")

    return issues


def main() -> int:
    sections = {
        "legacy_terms": audit_legacy_terms(),
        "config": audit_config(),
        "latest_scan": audit_latest_scan(),
    }

    failed = False

    print("\n=== ANALISTA PROJECT CONSISTENCY AUDIT ===")

    for section, issues in sections.items():
        print(f"\n[{section}]")
        if issues:
            failed = True
            for issue in issues:
                print(f"- FAIL: {issue}")
        else:
            print("- OK")

    if failed:
        print("\nResultado: FAIL")
        return 1

    print("\nResultado: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
