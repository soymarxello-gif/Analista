from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROVIDERS = {"PROMPT_ONLY", "OPENAI", "ANTHROPIC", "GEMINI"}
SYSTEM_INSTRUCTION = (
    "You are an independent, conservative swing-trading reviewer. "
    "Analyze only the supplied evidence. Identify contradictions, late entries, "
    "weak momentum, unrealistic levels and missing data. Do not create orders, "
    "do not alter system scores or signals, and do not use direct purchase language."
)


def _clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if value != value:
            return None
    except Exception:
        pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def build_candidate_package(row: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "ticker",
        "company",
        "sector",
        "industry",
        "signal",
        "recommendation",
        "setup_type",
        "scenario_status",
        "scenario_confidence",
        "scenario_thesis",
        "scenario_evidence",
        "scenario_contradictions",
        "momentum_state",
        "extension_state",
        "ema20_extension_status",
        "entry_timing_status",
        "macd_histogram_state",
        "timing_quality_score",
        "momentum_confirmation_score",
        "required_confirmation",
        "engine_recommendation",
        "final_trade_score",
        "setup_quality_score",
        "asset_quality_score",
        "institutional_score",
        "actionable_entry",
        "actionable_stop",
        "actionable_target",
        "scenario_entry",
        "scenario_stop",
        "scenario_target",
        "rr",
        "stop_atr_status",
        "quote_status",
        "execution_quote_quality",
        "technical_rsi",
        "technical_rsi_change_5d",
        "technical_macd",
        "technical_macd_signal",
        "technical_macd_hist",
        "technical_macd_hist_change_1d",
        "technical_macd_hist_change_3d",
        "technical_ema20",
        "technical_sma20",
        "technical_sma50",
        "technical_sma200",
        "technical_distance_ema20_pct",
        "technical_distance_sma20_pct",
        "technical_distance_sma50_pct",
        "technical_distance_ema20_atr",
        "technical_distance_sma20_atr",
        "technical_distance_sma50_atr",
        "technical_trigger_distance_pct",
        "technical_trigger_distance_atr",
        "technical_relative_volume",
        "technical_atr_pct",
        "options_bias",
        "options_confidence",
        "options_notes",
        "earnings_date",
        "days_to_earnings",
        "revenue_growth",
        "earnings_growth",
        "operating_margins",
        "profit_margins",
        "debt_to_equity",
        "return_on_equity",
        "macro_risk_flag",
        "macro_notes",
        "metadata_source",
        "quote_source",
        "options_source",
        "warnings",
        "penalty_reasons",
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_mode": "MANUAL_SECOND_OPINION",
        "guardrails": {
            "automatic_changes": False,
            "execution_actions": False,
            "human_review_required": True,
        },
        "candidate": {field: _clean(row.get(field)) for field in fields if field in row},
    }


def build_review_prompt(package: dict[str, Any]) -> str:
    schema = {
        "thesis": "string",
        "supporting_evidence": ["string"],
        "contradictions": ["string"],
        "momentum_assessment": "string",
        "extension_assessment": "string",
        "level_quality": "string",
        "risks": ["string"],
        "missing_data": ["string"],
        "manual_review_verdict": "REJECT | WAIT | REVIEWABLE",
    }
    return (
        f"{SYSTEM_INSTRUCTION}\n\n"
        "Return valid JSON using this schema:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Candidate evidence:\n"
        f"{json.dumps(package, ensure_ascii=False, indent=2, default=str)}"
    )


def provider_credentials_present(provider: str) -> bool:
    provider = str(provider or "").upper()
    env_by_provider = {
        "OPENAI": "OPENAI_API_KEY",
        "ANTHROPIC": "ANTHROPIC_API_KEY",
        "GEMINI": "GEMINI_API_KEY",
    }
    return provider == "PROMPT_ONLY" or bool(os.getenv(env_by_provider.get(provider, "")))


def _post_json(url: str, *, headers: dict[str, str], payload: dict, timeout_seconds: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"http_{exc.code}:{message}") from exc


def _call_provider(provider: str, prompt: str, *, model: str, timeout_seconds: int) -> str:
    provider = provider.upper()
    if provider == "OPENAI":
        payload = {
            "model": model or "gpt-5-mini",
            "input": prompt,
        }
        data = _post_json(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        if data.get("output_text"):
            return str(data["output_text"])
        texts = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                if content.get("text"):
                    texts.append(str(content["text"]))
        return "\n".join(texts)
    if provider == "ANTHROPIC":
        payload = {
            "model": model or "claude-sonnet-4-20250514",
            "max_tokens": 1800,
            "system": SYSTEM_INSTRUCTION,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
            },
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
        return "\n".join(
            str(item.get("text"))
            for item in data.get("content", []) or []
            if item.get("text")
        )
    if provider == "GEMINI":
        chosen_model = model or "gemini-2.5-flash"
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{chosen_model}:generateContent"
            f"?key={os.environ['GEMINI_API_KEY']}"
        )
        data = _post_json(
            url,
            headers={},
            payload={"contents": [{"parts": [{"text": prompt}]}]},
            timeout_seconds=timeout_seconds,
        )
        return "\n".join(
            str(part.get("text"))
            for candidate in data.get("candidates", []) or []
            for part in candidate.get("content", {}).get("parts", []) or []
            if part.get("text")
        )
    raise ValueError("unsupported_provider")


def save_ai_review(
    *,
    root: Path,
    row: dict[str, Any],
    provider: str = "PROMPT_ONLY",
    model: str = "",
    execute: bool = False,
    timeout_seconds: int = 45,
) -> dict[str, Any]:
    provider = str(provider or "PROMPT_ONLY").upper()
    if provider not in PROVIDERS:
        return {"status": "FAIL", "error": "unsupported_provider"}
    package = build_candidate_package(row)
    prompt = build_review_prompt(package)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    response_text = ""
    status = "PASS"
    error = ""
    if execute and provider != "PROMPT_ONLY":
        if not provider_credentials_present(provider):
            status = "WARN"
            error = "provider_credentials_missing"
        else:
            try:
                response_text = _call_provider(
                    provider,
                    prompt,
                    model=model,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                status = "WARN"
                error = f"provider_call_failed:{type(exc).__name__}:{str(exc)[:500]}"

    result = {
        "status": status,
        "generated_at": package["generated_at"],
        "ticker": package["candidate"].get("ticker", ""),
        "provider": provider,
        "model": model,
        "executed": bool(execute and provider != "PROMPT_ONLY" and response_text),
        "prompt_hash": prompt_hash,
        "prompt": prompt,
        "response": response_text,
        "error": error,
        "manual_review_only": True,
        "automatic_changes": False,
        "execution_actions": False,
    }
    reports = root / "reports" / "ai_reviews"
    reports.mkdir(parents=True, exist_ok=True)
    ticker = str(result["ticker"] or "UNKNOWN").upper()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output = reports / f"ai_review_{ticker}_{timestamp}.json"
    latest = root / "reports" / "ai_review_latest.json"
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    output.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    result["output"] = str(output)
    result["latest_output"] = str(latest)
    return result
