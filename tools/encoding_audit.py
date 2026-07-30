from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


DEFAULT_PATTERNS = [
    "*.md",
    "*.txt",
    "*.csv",
    "*.json",
]


MOJIBAKE_MARKERS = [
    "Ã¡",
    "Ã©",
    "Ã­",
    "Ã³",
    "Ãº",
    "Ã±",
    "Ã‘",
    "Â",
    "â€”",
    "â€“",
    "â€œ",
    "â€",
    "�",
]


SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "cache",
    "history",
    "posttests",
}


def _relative(path: Path, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _should_skip(path: Path, root: Path = ROOT) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        rel_parts = path.parts

    return any(part in SKIP_DIR_NAMES for part in rel_parts)


def _read_text(path: Path) -> tuple[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
        return text, ""
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="utf-8-sig")
            return text, ""
        except Exception as exc:
            return "", f"decode_error: {exc}"
    except Exception as exc:
        return "", f"read_error: {exc}"


def _find_marker_hits(text: str) -> dict:
    hits: dict[str, int] = {}

    for marker in MOJIBAKE_MARKERS:
        count = text.count(marker)
        if count:
            hits[marker] = count

    return hits


def _sample_lines(text: str, markers: list[str], max_samples: int = 8) -> list[str]:
    samples: list[str] = []

    for line in text.splitlines():
        if any(marker in line for marker in markers):
            clean = line.strip()
            if clean:
                samples.append(clean[:240])

        if len(samples) >= max_samples:
            break

    return samples


def scan_file(path: Path, root: Path = ROOT) -> dict:
    text, error = _read_text(path)

    if error:
        return {
            "path": _relative(path, root),
            "status": "ERROR",
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "marker_hits": {},
            "total_marker_hits": 0,
            "samples": [],
            "error": error,
        }

    marker_hits = _find_marker_hits(text)
    total_marker_hits = int(sum(marker_hits.values()))

    status = "WARN" if total_marker_hits > 0 else "PASS"

    return {
        "path": _relative(path, root),
        "status": status,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "marker_hits": marker_hits,
        "total_marker_hits": total_marker_hits,
        "samples": _sample_lines(text, list(marker_hits.keys())),
        "error": "",
    }


def collect_encoding_audit(
    root: Path = ROOT,
    scan_dir: Path | None = None,
    patterns: list[str] | None = None,
) -> dict:
    root = root.resolve()
    scan_dir = scan_dir or root / "reports"
    scan_dir = scan_dir.resolve()
    patterns = patterns or DEFAULT_PATTERNS

    files: list[Path] = []

    if scan_dir.exists():
        for pattern in patterns:
            for path in scan_dir.rglob(pattern):
                if path.is_file() and not _should_skip(path, root=root):
                    files.append(path)

    files = sorted(set(files), key=lambda p: _relative(p, root))

    results = [scan_file(path, root=root) for path in files]

    warn_files = [item for item in results if item["status"] == "WARN"]
    error_files = [item for item in results if item["status"] == "ERROR"]

    if error_files:
        status = "FAIL"
    elif warn_files:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": root.as_posix(),
        "scan_dir": _relative(scan_dir, root),
        "patterns": patterns,
        "summary": {
            "files_scanned": len(results),
            "warn_files": len(warn_files),
            "error_files": len(error_files),
            "total_marker_hits": int(sum(item["total_marker_hits"] for item in results)),
        },
        "results": results,
    }


def _markdown_table(items: list[dict], columns: list[str]) -> str:
    if not items:
        return "_Sin datos._"

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


def build_encoding_audit_markdown(data: dict) -> str:
    summary = data.get("summary", {})
    results = data.get("results", [])

    warn_or_error = [
        item
        for item in results
        if item.get("status") in {"WARN", "ERROR"}
    ]

    lines: list[str] = []

    lines.append("# Analista - encoding audit")
    lines.append("")
    lines.append(f"- generated_at: {data.get('generated_at')}")
    lines.append(f"- status: {data.get('status')}")
    lines.append(f"- scan_dir: `{data.get('scan_dir')}`")
    lines.append(f"- files_scanned: {summary.get('files_scanned')}")
    lines.append(f"- warn_files: {summary.get('warn_files')}")
    lines.append(f"- error_files: {summary.get('error_files')}")
    lines.append(f"- total_marker_hits: {summary.get('total_marker_hits')}")
    lines.append("")

    lines.append("## Decision gate")
    lines.append("")

    if data.get("status") == "FAIL":
        lines.append("- Estado FAIL: hay archivos que no pudieron leerse correctamente.")
    elif data.get("status") == "WARN":
        lines.append("- Estado WARN: se detectaron posibles textos mal codificados.")
    else:
        lines.append("- Estado PASS: no se detectaron marcadores típicos de mojibake.")

    lines.append("")

    lines.append("## Archivos con advertencias o errores")
    lines.append("")
    lines.append(
        _markdown_table(
            warn_or_error,
            ["path", "status", "size_bytes", "total_marker_hits", "error"],
        )
    )
    lines.append("")

    if warn_or_error:
        lines.append("## Muestras")
        lines.append("")

        for item in warn_or_error:
            samples = item.get("samples", [])
            marker_hits = item.get("marker_hits", {})

            lines.append(f"### `{item.get('path')}`")
            lines.append("")
            lines.append(f"- status: {item.get('status')}")
            lines.append(f"- marker_hits: `{marker_hits}`")
            lines.append("")

            if samples:
                lines.append("```text")
                lines.extend(samples)
                lines.append("```")
            else:
                lines.append("_Sin muestras._")

            lines.append("")

    return "\n".join(lines)


def save_encoding_audit(
    root: Path = ROOT,
    scan_dir: Path | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "encoding_audit_latest.json"
    markdown_out = markdown_out or root / "reports" / "encoding_audit_latest.md"

    data = collect_encoding_audit(
        root=root,
        scan_dir=scan_dir or root / "reports",
    )

    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    json_out.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    markdown_out.write_text(
        build_encoding_audit_markdown(data),
        encoding="utf-8",
    )

    return {
        "status": data["status"],
        "json_out": _relative(json_out, root),
        "markdown_out": _relative(markdown_out, root),
        "files_scanned": data["summary"]["files_scanned"],
        "warn_files": data["summary"]["warn_files"],
        "error_files": data["summary"]["error_files"],
        "total_marker_hits": data["summary"]["total_marker_hits"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita posibles problemas de encoding/mojibake.")
    parser.add_argument("--scan-dir", default="reports")
    parser.add_argument("--json-out", default="reports/encoding_audit_latest.json")
    parser.add_argument("--markdown-out", default="reports/encoding_audit_latest.md")
    args = parser.parse_args()

    result = save_encoding_audit(
        root=ROOT,
        scan_dir=ROOT / args.scan_dir,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA ENCODING AUDIT ===")
    print(f"Status: {result['status']}")
    print(f"Files scanned: {result['files_scanned']}")
    print(f"Warn files: {result['warn_files']}")
    print(f"Error files: {result['error_files']}")
    print(f"Total marker hits: {result['total_marker_hits']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
