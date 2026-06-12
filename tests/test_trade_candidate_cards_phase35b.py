from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools import daily_validation
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS
from tools.trade_candidate_cards import (
    build_trade_candidate_cards_dataframe,
    build_trade_candidate_cards_markdown,
    save_trade_candidate_cards_reports,
)


def _candidate(**overrides) -> dict:
    row = {
        "ticker": "AAA",
        "checklist_status": "REVIEW_MANUALLY",
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "setup_type": "BREAKOUT",
        "sector": "Technology",
        "industry": "Software",
        "final_trade_score": 82,
        "checklist_score": 80,
        "setup_quality_score": 86,
        "asset_quality_score": 84,
        "institutional_score": 60,
        "options_score": 0.55,
        "options_bias": "NEUTRAL_WITH_DATA",
        "options_confidence": "HIGH",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "actionable_entry": 100,
        "actionable_stop": 95,
        "actionable_target": 112,
        "rr": 2.4,
        "stop_atr_status": "IDEAL",
        "next_earnings_date": "2026-08-01",
        "checklist_blockers": "",
        "checklist_warnings": "spread_unknown",
        "checklist_required_actions": "treat_options_as_context_not_trigger",
        "manual_decision_note": "Revision manual obligatoria.",
    }
    row.update(overrides)
    return row


def test_missing_input_returns_controlled_fail_and_outputs(tmp_path: Path):
    reports = tmp_path / "reports"

    result = save_trade_candidate_cards_reports(
        input_path=reports / "missing.csv",
        markdown_out=reports / "trade_candidate_cards_latest.md",
        json_out=reports / "trade_candidate_cards_latest.json",
        root=tmp_path,
    )

    assert result["status"] == "FAIL"
    assert result["rows"] == 0
    assert result["error"] == "input_csv_not_found"
    assert (reports / "trade_candidate_cards_latest.md").exists()
    assert (reports / "trade_candidate_cards_latest.json").exists()


def test_empty_input_generates_report_without_cards(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    input_csv = reports / "trade_decision_checklist_latest.csv"
    pd.DataFrame(columns=["ticker", "checklist_status"]).to_csv(input_csv, index=False)

    result = save_trade_candidate_cards_reports(
        input_path=input_csv,
        markdown_out=reports / "trade_candidate_cards_latest.md",
        json_out=reports / "trade_candidate_cards_latest.json",
        root=tmp_path,
    )

    text = (reports / "trade_candidate_cards_latest.md").read_text(encoding="utf-8")
    assert result["status"] == "PASS"
    assert result["rows"] == 0
    assert "_Sin candidatos para generar fichas._" in text


def test_blocked_card_shows_no_operable():
    df = build_trade_candidate_cards_dataframe(pd.DataFrame([_candidate(checklist_status="BLOCKED")]))
    text = build_trade_candidate_cards_markdown(df)

    assert "## AAA - BLOCKED" in text
    assert "**NO OPERABLE**" in text


def test_needs_live_quote_recheck_card_shows_required_live_quote():
    df = build_trade_candidate_cards_dataframe(
        pd.DataFrame([_candidate(checklist_status="NEEDS_LIVE_QUOTE_RECHECK")])
    )
    text = build_trade_candidate_cards_markdown(df)

    assert "**REQUIERE LIVE QUOTE**" in text
    assert "- live quote recheck: requerido" in text


def test_high_quality_review_card_does_not_use_buy_language():
    df = build_trade_candidate_cards_dataframe(
        pd.DataFrame([_candidate(checklist_status="HIGH_QUALITY_REVIEW")])
    )
    text = build_trade_candidate_cards_markdown(df)
    card_text = text.split("## AAA - HIGH_QUALITY_REVIEW", 1)[1]

    assert "ALTA CALIDAD PARA REVISION MANUAL" in card_text
    assert "BUY" not in card_text.upper()
    assert "COMPRA" not in card_text.upper()


def test_cards_are_sorted_by_priority_score_and_ticker():
    df = pd.DataFrame(
        [
            _candidate(ticker="CCC", checklist_status="BLOCKED", checklist_score=99),
            _candidate(ticker="BBB", checklist_status="REVIEW_MANUALLY", checklist_score=80),
            _candidate(ticker="DDD", checklist_status="HIGH_QUALITY_REVIEW", checklist_score=70),
            _candidate(ticker="AAA", checklist_status="HIGH_QUALITY_REVIEW", checklist_score=90),
            _candidate(ticker="EEE", checklist_status="NEEDS_LIVE_QUOTE_RECHECK", checklist_score=95),
        ]
    )

    out = build_trade_candidate_cards_dataframe(df)

    assert list(out["ticker"]) == ["AAA", "DDD", "BBB", "EEE", "CCC"]


def test_markdown_contains_operational_levels():
    df = build_trade_candidate_cards_dataframe(pd.DataFrame([_candidate()]))
    text = build_trade_candidate_cards_markdown(df)

    assert "### Niveles operativos" in text
    assert "- Entrada: 100" in text
    assert "- Stop: 95" in text
    assert "- Target: 112" in text
    assert "- R/R: 2.4" in text


def test_markdown_contains_options_flow_section():
    df = build_trade_candidate_cards_dataframe(
        pd.DataFrame([_candidate(options_bias="CROWDED_BULLISH")])
    )
    text = build_trade_candidate_cards_markdown(df)

    assert "### Opciones / flujo institucional" in text
    assert "lectura contrarian" in text
    assert "Sentimiento alcista saturado" in text


def test_save_cards_writes_json_payload(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    input_csv = reports / "trade_decision_checklist_latest.csv"
    pd.DataFrame([_candidate()]).to_csv(input_csv, index=False)

    result = save_trade_candidate_cards_reports(
        input_path=input_csv,
        markdown_out=reports / "trade_candidate_cards_latest.md",
        json_out=reports / "trade_candidate_cards_latest.json",
        root=tmp_path,
    )
    payload = json.loads((reports / "trade_candidate_cards_latest.json").read_text(encoding="utf-8"))

    assert result["status"] == "PASS"
    assert result["rows"] == 1
    assert payload["cards"][0]["ticker"] == "AAA"


def test_default_input_falls_back_to_manual_review_top_with_warning(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    pd.DataFrame([_candidate()]).to_csv(reports / "manual_review_top.csv", index=False)

    result = save_trade_candidate_cards_reports(
        markdown_out=reports / "trade_candidate_cards_latest.md",
        json_out=reports / "trade_candidate_cards_latest.json",
        root=tmp_path,
    )

    assert result["status"] == "PASS"
    assert result["warning"] == "trade_decision_checklist_missing_using_manual_review_top"


def test_daily_validation_has_optional_trade_candidate_cards_after_checklist():
    post_names = [item["name"] for item in daily_validation.POST_SUMMARY_STEPS]

    assert "trade_candidate_cards" in post_names
    assert post_names.index("trade_decision_checklist") < post_names.index("trade_candidate_cards")

    step = next(item for item in daily_validation.POST_SUMMARY_STEPS if item["name"] == "trade_candidate_cards")
    assert step["required"] is False
    assert "tools/trade_candidate_cards.py" in step["cmd"]
    assert "reports/trade_candidate_cards_latest.md" in step["cmd"]
    assert "reports/trade_candidate_cards_latest.json" in step["cmd"]


def test_daily_operator_index_renders_trade_candidate_cards_summary():
    text = build_daily_operator_index_markdown(
        {
            "generated_at": "2026-06-11T00:00:00",
            "validation_status": "PASS",
            "scan_rows": 1,
            "manual_review_rows": 1,
            "manual_top_rows": 1,
            "open_trades_rows": 0,
            "analytics_rows": 0,
            "trigger_count": 0,
            "watchlist_count": 1,
            "recheck_count": 0,
            "signals": {"WATCHLIST": 1},
            "recommendations": {"WATCHLIST_MONITOR": 1},
            "quote_recheck_priority": {},
            "quality_gate": {"available": False},
            "live_quote_recheck": {"available": False},
            "trade_decision_checklist": {"available": False},
            "trade_candidate_cards": {
                "available": True,
                "status": "PASS",
                "rows": 4,
                "high_quality_review": 1,
                "review_manually": 1,
                "needs_live_quote_recheck": 1,
                "blocked": 1,
            },
            "top_candidates": pd.DataFrame(),
            "recheck_candidates": pd.DataFrame(),
            "open_trades": pd.DataFrame(),
            "analytics_overall": pd.DataFrame(),
            "cleanup": {},
            "preflight": {},
            "encoding_audit": {},
            "report_status": [],
        }
    )

    assert "## Trade candidate cards" in text
    assert "- high_quality_review: 1" in text
    assert "reports/trade_candidate_cards_latest.md" in text


def test_daily_run_manifest_tracks_trade_candidate_cards_outputs():
    assert "tools/trade_candidate_cards.py" in KEY_SCRIPT_PATHS
    assert "reports/trade_candidate_cards_latest.md" in KEY_REPORT_PATHS
    assert "reports/trade_candidate_cards_latest.json" in KEY_REPORT_PATHS


def test_cards_do_not_create_buy_setup_active_or_trigger_confirmed():
    df = build_trade_candidate_cards_dataframe(pd.DataFrame([_candidate()]))
    text = build_trade_candidate_cards_markdown(df)

    assert "BUY_SETUP_ACTIVE" not in text
    assert "TRIGGER_CONFIRMED" not in set(df["checklist_status"].astype(str))
