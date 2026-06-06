from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=ROOT)


def main() -> int:
    checks = [
        [sys.executable, "tools/validate_project.py"],
        [sys.executable, "-m", "compileall", "."],
        [sys.executable, "-m", "pytest"],
    ]

    for cmd in checks:
        rc = run(cmd)
        if rc != 0:
            return rc

    print("\nOK: validación completa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
