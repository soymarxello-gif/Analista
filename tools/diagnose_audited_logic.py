from __future__ import annotations

from tools.validate_audited_logic import (
    validate_config,
    validate_final_score,
    validate_options,
    validate_postprocessor,
    validate_signals,
)


def run_stage(name: str, function) -> None:
    print(f"START: {name}", flush=True)
    function()
    print(f"PASS: {name}", flush=True)


def main() -> int:
    run_stage("config", validate_config)
    run_stage("final_score", validate_final_score)
    run_stage("signals", validate_signals)
    run_stage("options", validate_options)
    run_stage("postprocessor", validate_postprocessor)
    print("OK: all audited validation stages passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
