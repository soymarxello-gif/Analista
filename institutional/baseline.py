from __future__ import annotations

import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_baseline_bundle(
    database_path: str | Path,
    configuration_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Create an immutable baseline bundle without reading a live DB inconsistently."""
    database_path = Path(database_path)
    configuration_path = Path(configuration_path)
    output_path = Path(output_path)
    if not database_path.is_file() or not configuration_path.is_file():
        raise FileNotFoundError("database and configuration are required")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = output_path.with_suffix(".sqlite.tmp")
    source = sqlite3.connect(database_path)
    destination = sqlite3.connect(snapshot)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database_file": "institutional.sqlite",
        "database_sha256": _hash(snapshot),
        "configuration_file": configuration_path.name,
        "configuration_sha256": _hash(configuration_path),
        "bundle_schema": "baseline-bundle-1",
    }
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(snapshot, "institutional.sqlite")
        archive.write(configuration_path, configuration_path.name)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    snapshot.unlink()
    return output_path
