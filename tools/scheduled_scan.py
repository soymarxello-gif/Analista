from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.market_clock import evaluate_scheduled_slot


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Analista once at 09:20 America/New_York")
    parser.add_argument("--scheduled-slot", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    gate = evaluate_scheduled_slot(args.scheduled_slot)
    print(f"NYSE schedule gate: run={gate.should_run} reason={gate.reason} target={gate.scheduled_for_et}")
    if not gate.should_run and not args.force:
        return 0
    command = [sys.executable, str(ROOT / "run_scanner.py")]
    if args.config:
        command.extend(["--config", args.config])
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
