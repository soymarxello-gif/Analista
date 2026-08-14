from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = ("cache/", "logs/", "reports/")
FORBIDDEN_ROOT_NAMES = {
    "CONFIG_FRAGMENT_ADD_TO_CONFIG_YAML.txt",
    "CONFIG_FRAGMENT_OPTIONS_FLOW.yaml",
    "LOCAL_SYNC_STATUS.txt",
    "README_PATCH.txt",
}


def tracked_files() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line for line in result.stdout.splitlines() if line)


def hygiene_violations(paths: tuple[str, ...]) -> tuple[str, ...]:
    violations = []
    for path in paths:
        name = Path(path).name
        if path.startswith(FORBIDDEN_PREFIXES):
            violations.append(path)
        elif "/" not in path and (path in FORBIDDEN_ROOT_NAMES or name.startswith("Analista_patch_") or name == "Analista_MVP.zip"):
            violations.append(path)
        elif path in {"engine/SCANNER_ENGINE_OPTIONS_PATCH_NOTES.txt", "ui/DASHBOARD_OPTIONS_COLUMNS_NOTE.txt"}:
            violations.append(path)
    return tuple(sorted(violations))


def main() -> int:
    violations = hygiene_violations(tracked_files())
    if violations:
        formatted = "\n".join(f"- {path}" for path in violations)
        raise SystemExit(f"Generated or obsolete artifacts are tracked:\n{formatted}")
    print("OK repository hygiene: no generated caches, reports, logs, or obsolete patch artifacts are tracked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
