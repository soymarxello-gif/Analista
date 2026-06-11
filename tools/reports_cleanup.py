from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_PATTERNS = [
    "*_test.csv",
    "*_test.md",
    "*_test.json",
    "*_test.txt",
    "trade_outcomes_*_test*.csv",
    "trade_outcomes_*_test*.md",
    "trade_outcome_analytics_test.*",
    "open_trades_snapshot_test.*",
    "manual_review_*_test.*",
]


PROTECTED_REPORT_NAMES = {
    "latest_scan_audited.csv",
    "latest_scan_audited.json",
    "manual_review_latest.csv",
    "manual_review_latest.md",
    "manual_review_top.csv",
    "manual_review_top.md",
    "daily_validation_summary.txt",
    "daily_operator_index.md",
    "open_trades_snapshot_latest.csv",
    "open_trades_snapshot_latest.md",
    "trade_outcome_analytics_latest.csv",
    "trade_outcome_analytics_latest.md",
    "source_coverage_latest.json",
    "history_evolution_latest.csv",
    "history_evolution_latest.md",
    "setup_persistence_latest.csv",
    "setup_persistence_latest.md",
    "trade_outcomes.csv",
    "reports_cleanup_latest.json",
    "reports_cleanup_latest.md",
}


def _relative(path: Path, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _file_status(path: Path, root: Path = ROOT, matched_pattern: str = "") -> dict:
    exists = path.exists()

    return {
        "path": _relative(path, root),
        "name": path.name,
        "matched_pattern": matched_pattern,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        if exists
        else "",
    }


def is_protected_report(path: Path) -> bool:
    if path.name in PROTECTED_REPORT_NAMES:
        return True

    parts = {part.lower() for part in path.parts}

    if "history" in parts:
        return True

    if "tmp" in parts:
        return True

    return False


def discover_temporary_reports(
    reports_dir: Path,
    root: Path = ROOT,
    patterns: list[str] | None = None,
) -> list[dict]:
    patterns = patterns or DEFAULT_PATTERNS

    if not reports_dir.exists():
        return []

    found: dict[Path, dict] = {}

    for pattern in patterns:
        for path in reports_dir.glob(pattern):
            if not path.is_file():
                continue

            if is_protected_report(path):
                continue

            resolved = path.resolve()

            if resolved not in found:
                found[resolved] = _file_status(path, root=root, matched_pattern=pattern)

    return sorted(found.values(), key=lambda item: item["path"])


def _safe_destination(path: Path, archive_dir: Path) -> Path:
    destination = archive_dir / path.name

    if not destination.exists():
        return destination

    stem = path.stem
    suffix = path.suffix

    for idx in range(1, 1000):
        candidate = archive_dir / f"{stem}_{idx}{suffix}"
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"No se pudo crear destino único para: {path}")


def cleanup_temporary_reports(
    root: Path = ROOT,
    reports_dir: Path | None = None,
    apply: bool = False,
    archive_dir: Path | None = None,
) -> dict:
    reports_dir = reports_dir or root / "reports"

    candidates = discover_temporary_reports(
        reports_dir=reports_dir,
        root=root,
    )

    archive_dir = archive_dir or reports_dir / "tmp" / f"temp_reports_{_timestamp()}"

    moved: list[dict] = []

    for item in candidates:
        source = root / item["path"]

        # For tests using tmp_path, item["path"] is relative to tmp root.
        if not source.exists():
            source = Path(item["path"])

        move_item = dict(item)
        move_item["moved"] = False
        move_item["destination"] = ""

        if apply:
            archive_dir.mkdir(parents=True, exist_ok=True)
            destination = _safe_destination(source, archive_dir)
            shutil.move(str(source), str(destination))

            move_item["moved"] = True
            move_item["destination"] = _relative(destination, root)

        moved.append(move_item)

    return {
        "status": "PASS",
        "mode": "APPLY" if apply else "DRY_RUN",
        "reports_dir": _relative(reports_dir, root),
        "archive_dir": _relative(archive_dir, root),
        "candidate_count": len(candidates),
        "moved_count": sum(1 for item in moved if item.get("moved")),
        "items": moved,
    }


def _markdown_table(items: list[dict]) -> str:
    if not items:
        return "_No se detectaron reportes temporales._"

    columns = [
        "path",
        "matched_pattern",
        "size_bytes",
        "modified",
        "moved",
        "destination",
    ]

    lines: list[str] = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")

    for item in items:
        values = []
        for col in columns:
            value = item.get(col, "")
            values.append(str(value).replace("\n", " ").replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def build_cleanup_markdown(result: dict) -> str:
    lines: list[str] = []

    lines.append("# Analista - reports cleanup")
    lines.append("")
    lines.append(f"- generated_at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- status: {result.get('status')}")
    lines.append(f"- mode: {result.get('mode')}")
    lines.append(f"- reports_dir: {result.get('reports_dir')}")
    lines.append(f"- archive_dir: {result.get('archive_dir')}")
    lines.append(f"- candidate_count: {result.get('candidate_count')}")
    lines.append(f"- moved_count: {result.get('moved_count')}")
    lines.append("")

    lines.append("## Resultado")
    lines.append("")
    lines.append(_markdown_table(result.get("items", [])))
    lines.append("")

    lines.append("## Regla de seguridad")
    lines.append("")
    lines.append("- Este script no borra archivos.")
    lines.append("- Sin `--apply`, solo simula la limpieza.")
    lines.append("- Con `--apply`, mueve temporales a `reports/tmp/`.")
    lines.append("- Los reportes operativos `latest`, `manual_review`, `daily_operator_index`, analytics y bitácora real están protegidos.")

    return "\n".join(lines)


def save_cleanup_reports(
    root: Path = ROOT,
    reports_dir: Path | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    apply: bool = False,
    archive_dir: Path | None = None,
) -> dict:
    reports_dir = reports_dir or root / "reports"
    json_out = json_out or root / "reports" / "reports_cleanup_latest.json"
    markdown_out = markdown_out or root / "reports" / "reports_cleanup_latest.md"

    result = cleanup_temporary_reports(
        root=root,
        reports_dir=reports_dir,
        apply=apply,
        archive_dir=archive_dir,
    )

    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    json_out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    markdown_out.write_text(
        build_cleanup_markdown(result),
        encoding="utf-8",
    )

    result["json_out"] = _relative(json_out, root)
    result["markdown_out"] = _relative(markdown_out, root)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Limpieza segura de reportes temporales.")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--json-out", default="reports/reports_cleanup_latest.json")
    parser.add_argument("--markdown-out", default="reports/reports_cleanup_latest.md")
    parser.add_argument("--archive-dir", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    archive_dir = ROOT / args.archive_dir if args.archive_dir else None

    result = save_cleanup_reports(
        root=ROOT,
        reports_dir=ROOT / args.reports_dir,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
        apply=args.apply,
        archive_dir=archive_dir,
    )

    print("=== ANALISTA REPORTS CLEANUP ===")
    print(f"Status: {result['status']}")
    print(f"Mode: {result['mode']}")
    print(f"Candidates: {result['candidate_count']}")
    print(f"Moved: {result['moved_count']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())