from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPORTS_DIR = Path("reports")


def latest_csv() -> Path:
    audited = REPORTS_DIR / "latest_scan_audited.csv"
    if audited.exists():
        return audited

    csvs = sorted(REPORTS_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not csvs:
        raise FileNotFoundError("No se encontraron CSV en ./reports")
    return csvs[0]


def as_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_csv()
    df = pd.read_csv(path)

    print(f"Auditando: {path}")
    print(f"Filas: {len(df)}")
    print()

    required_columns = [
        "ticker",
        "signal",
        "price",
        "market_cap",
        "setup_type",
        "trigger_confirmed",
        "execution_quote_quality",
        "quote_status",
        "all_veto_reasons",
        "actionable_entry",
        "actionable_stop",
        "actionable_target",
    ]

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise AssertionError(f"Faltan columnas requeridas: {missing}")

    signal = df["signal"].astype(str)
    recommendation = (
        df["recommendation"].astype(str).str.upper()
        if "recommendation" in df.columns
        else pd.Series("", index=df.index)
    )
    trigger_confirmed = as_bool(df["trigger_confirmed"])
    execution_quote_quality = df["execution_quote_quality"].astype(str).str.upper()
    setup_type = df["setup_type"].astype(str)
    technical_prefilter_failed = (
        df.get("technical_prefilter_status", pd.Series("", index=df.index))
        .fillna("")
        .astype(str)
        .str.upper()
        .eq("FAIL")
    )
    allowed_prefilter_avoid = (
        technical_prefilter_failed
        & signal.str.upper().eq("AVOID")
        & recommendation.eq("AVOID_FOR_NOW")
    )

    actionable_signals = {"TRIGGER_CONFIRMED", "READY_WAIT_TRIGGER", "WATCHLIST"}

    checks = {}

    checks["BUY_SETUP_ACTIVE"] = (signal == "BUY_SETUP_ACTIVE").sum()

    checks["READY_WAIT_TRIGGER + trigger_confirmed=true"] = (
        (signal == "READY_WAIT_TRIGGER") & trigger_confirmed
    ).sum()

    checks["TRIGGER_CONFIRMED + execution_quote_quality=LOW"] = (
        (signal == "TRIGGER_CONFIRMED") & (execution_quote_quality == "LOW")
    ).sum()

    checks["WATCHLIST_or_better + price<10"] = (
        signal.isin(actionable_signals)
        & pd.to_numeric(df["price"], errors="coerce").lt(10)
    ).sum()

    checks["WATCHLIST_or_better + market_cap<2.5B"] = (
        signal.isin(actionable_signals)
        & pd.to_numeric(df["market_cap"], errors="coerce").lt(2_500_000_000)
    ).sum()

    checks["NO_VALID_SETUP fuera de VETO"] = (
        (setup_type == "NO_VALID_SETUP") & (signal != "VETO") & ~allowed_prefilter_avoid
    ).sum()

    veto = signal == "VETO"
    checks["VETO con actionable_entry no nulo"] = (
        veto & df["actionable_entry"].notna()
    ).sum()
    checks["VETO con actionable_stop no nulo"] = (
        veto & df["actionable_stop"].notna()
    ).sum()
    checks["VETO con actionable_target no nulo"] = (
        veto & df["actionable_target"].notna()
    ).sum()

    print("Distribución de señales:")
    print(df["signal"].value_counts(dropna=False))
    print()

    print("Distribución de quote_status:")
    print(df["quote_status"].value_counts(dropna=False))
    print()

    print("Distribución de execution_quote_quality:")
    print(df["execution_quote_quality"].value_counts(dropna=False))
    print()

    print("Checks P0:")
    for name, count in checks.items():
        print(f"- {name}: {count}")

    failed = {name: count for name, count in checks.items() if int(count) != 0}

    if failed:
        print()
        print("FALLAS:")
        for name, count in failed.items():
            print(f"- {name}: {count}")
        raise AssertionError("El nuevo scan no cumple los invariantes P0.")

    print()
    print("Bloque F OK: el nuevo scan cumple invariantes P0.")


if __name__ == "__main__":
    main()
