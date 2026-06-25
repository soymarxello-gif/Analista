from __future__ import annotations

import json
from pathlib import Path

from ui import ai_review


def _row() -> dict:
    return {
        "ticker": "AAA",
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "setup_type": "PULLBACK",
        "scenario_status": "WAIT_FOR_CONFIRMATION",
        "scenario_thesis": "Orderly pullback pending rejection confirmation.",
        "scenario_contradictions": '["no_bullish_rejection_confirmation"]',
        "momentum_state": "IMPROVING",
        "extension_state": "HEALTHY",
        "technical_rsi": 58.2,
        "actionable_entry": 100,
        "actionable_stop": 95,
        "actionable_target": 110,
    }


def test_candidate_package_is_manual_and_read_only() -> None:
    package = ai_review.build_candidate_package(_row())

    assert package["candidate"]["ticker"] == "AAA"
    assert package["guardrails"]["automatic_changes"] is False
    assert package["guardrails"]["execution_actions"] is False


def test_prompt_requires_contradictions_and_structured_verdict() -> None:
    prompt = ai_review.build_review_prompt(ai_review.build_candidate_package(_row()))

    assert "contradictions" in prompt
    assert "extension_assessment" in prompt
    assert "manual_review_verdict" in prompt
    assert "do not alter system scores or signals" in prompt


def test_prompt_only_saves_auditable_report_without_network(tmp_path: Path) -> None:
    result = ai_review.save_ai_review(
        root=tmp_path,
        row=_row(),
        provider="PROMPT_ONLY",
        execute=False,
    )

    assert result["status"] == "PASS"
    assert result["executed"] is False
    assert result["response"] == ""
    assert len(result["prompt_hash"]) == 64
    saved = json.loads((tmp_path / "reports" / "ai_review_latest.json").read_text(encoding="utf-8"))
    assert saved["automatic_changes"] is False


def test_missing_provider_credentials_is_controlled_warn(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = ai_review.save_ai_review(
        root=tmp_path,
        row=_row(),
        provider="OPENAI",
        execute=True,
    )

    assert result["status"] == "WARN"
    assert result["error"] == "provider_credentials_missing"
    assert result["executed"] is False


def test_provider_call_is_mockable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(ai_review, "_call_provider", lambda *args, **kwargs: '{"manual_review_verdict":"WAIT"}')

    result = ai_review.save_ai_review(
        root=tmp_path,
        row=_row(),
        provider="OPENAI",
        model="test-model",
        execute=True,
    )

    assert result["status"] == "PASS"
    assert result["executed"] is True
    assert "WAIT" in result["response"]
