from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger


def format_numeric_columns(df: pd.DataFrame, decimals: int = 2) -> pd.DataFrame:
    """
    Round every numeric column for user-facing outputs.
    Internal calculations can keep higher precision before this step.
    """
    out = df.copy()

    numeric_cols = out.select_dtypes(include=["number"]).columns.tolist()
    for col in numeric_cols:
        out[col] = out[col].round(decimals)

    return out


def save_reports(
    df: pd.DataFrame,
    config: dict,
    json_out: str | None = None,
    csv_out: str | None = None,
) -> None:
    files = config.get("outputs", {}).get("files", {})

    json_path = Path(json_out or files.get("latest_scan", "reports/latest_scan.json"))
    csv_path = Path(csv_out or files.get("latest_csv", "reports/latest_scan.csv"))
    hist_dir = Path(files.get("history_dir", "reports/history"))

    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    hist_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    history_json = hist_dir / f"scan_{stamp}.json"
    history_csv = hist_dir / f"scan_{stamp}.csv"

    output_df = format_numeric_columns(df, decimals=2)

    # Always save historical outputs first.
    output_df.to_json(history_json, orient="records", indent=2, force_ascii=False)
    output_df.to_csv(history_csv, index=False, float_format="%.2f")

    # Try updating latest JSON.
    try:
        output_df.to_json(json_path, orient="records", indent=2, force_ascii=False)
    except PermissionError:
        logger.warning(
            f"No se pudo sobrescribir {json_path}. "
            f"El archivo puede estar abierto. Histórico guardado en {history_json}."
        )

    # Try updating latest CSV.
    try:
        output_df.to_csv(csv_path, index=False, float_format="%.2f")
    except PermissionError:
        logger.warning(
            f"No se pudo sobrescribir {csv_path}. "
            f"El archivo puede estar abierto en Excel/Streamlit. "
            f"Histórico guardado en {history_csv}."
        )
