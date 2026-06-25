from datetime import datetime
from pathlib import Path

import pandas as pd

from engine.posttest_batch_engine import eligible_scans, infer_scan_date, posttest_output_path


def test_infer_scan_date_from_timestamp(tmp_path: Path):
    file = tmp_path / "scan.csv"
    pd.DataFrame([{"scan_timestamp": "2026-06-01T10:00:00+00:00", "ticker": "AAA"}]).to_csv(file, index=False)

    date = infer_scan_date(file)
    assert date.date().isoformat() == "2026-06-01"


def test_eligible_scans(tmp_path: Path):
    file = tmp_path / "scan.csv"
    pd.DataFrame([{"scan_timestamp": "2026-06-01T10:00:00+00:00", "ticker": "AAA"}]).to_csv(file, index=False)

    scans = eligible_scans([file], min_age_days=4, now=datetime(2026, 6, 7))
    assert len(scans) == 1
    assert scans[0]["age_days"] >= 4


def test_posttest_output_path():
    out = posttest_output_path("reports/latest_scan_phase1_4.csv", output_dir="reports/posttests")
    assert out.as_posix().endswith("reports/posttests/posttest_latest_scan_phase1_4.csv")
