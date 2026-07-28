from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NOTICE = "read-only Nasdaq regime context; no automatic trading"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def collect_regime(macro_path: Path = ROOT / "reports" / "macro_event_context_latest.json") -> dict[str, Any]:
    macro = _load_json(macro_path)
    macro_mode = str(macro.get("macro_regime_mode", "UNKNOWN")).upper()
    risk_flag = str(macro.get("macro_risk_flag", "UNKNOWN")).upper()
    event_risk = str(macro.get("event_risk_status", "UNKNOWN")).upper()
    liquidity = str(macro.get("liquidity_context", "UNKNOWN")).upper()
    score = 50
    if "RISK_ON" in macro_mode or liquidity == "EXPANDING":
        score += 15
    if event_risk in {"TODAY", "WITHIN_1_DAY"}:
        score -= 20
    elif event_risk == "WITHIN_3_DAYS":
        score -= 10
    if risk_flag in {"ELEVATED", "RISK_OFF", "DEFENSIVE"}:
        score -= 15
    score = max(0, min(100, score))
    if score >= 70:
        semaforo = "VERDE"
        dominant = "NORMAL"
    elif score >= 45:
        semaforo = "AMARILLO"
        dominant = "CAUTION"
    else:
        semaforo = "ROJO"
        dominant = "DEFENSIVE"
    status = "PASS" if macro else "WARN"
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "macro_regime_mode": macro_mode,
        "macro_regime_confidence": macro.get("macro_regime_confidence", "UNKNOWN"),
        "macro_risk_flag": risk_flag,
        "macro_event_risk": event_risk,
        "macro_liquidity_bias": liquidity,
        "nasdaq_risk_score": score,
        "nasdaq_risk_semaforo": semaforo,
        "dominant_regime": dominant,
        "p_normal": round(score / 100.0, 4),
        "p_omega": round(max(0, 70 - score) / 100.0, 4),
        "p_sigma": round(max(0, 55 - score) / 100.0, 4),
        "p_phi": round(max(0, 45 - score) / 100.0, 4),
        "warnings_count": 0 if macro else 1,
        "macro_regime_notes": macro.get("macro_regime_notes", "macro_context_missing"),
        "notice": NOTICE,
        "broker_execution": False,
        "creates_trigger_confirmed": False,
    }


def save_reports(data: dict[str, Any], *, json_out: Path, markdown_out: Path) -> dict[str, Any]:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Analista - Nasdaq risk regime audit",
        "",
        f"- status: {data.get('status')}",
        f"- macro_regime_mode: {data.get('macro_regime_mode')}",
        f"- nasdaq_risk_score: {data.get('nasdaq_risk_score')}",
        f"- nasdaq_risk_semaforo: {data.get('nasdaq_risk_semaforo')}",
        f"- dominant_regime: {data.get('dominant_regime')}",
        f"- notice: {NOTICE}",
        "",
        "## Guardrails",
        "",
        "- No automatic trading.",
        "- No broker execution.",
        "- No trigger creation.",
    ]
    markdown_out.write_text("\n".join(lines), encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=str(ROOT / "reports" / "nasdaq_risk_regime_latest.json"))
    parser.add_argument("--markdown-out", default=str(ROOT / "reports" / "nasdaq_risk_regime_latest.md"))
    args = parser.parse_args()
    data = collect_regime()
    save_reports(data, json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))
    print("=== ANALISTA NASDAQ RISK REGIME AUDIT ===")
    print(f"Status: {data.get('status')}")
    print(f"Nasdaq risk score: {data.get('nasdaq_risk_score')}")
    return 0 if data.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
