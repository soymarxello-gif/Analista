from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class ShadowLock:
    configuration_hash: str
    model_version: str
    locked_at: datetime


class ShadowRegistry:
    VERSION = "shadow-registry-1"

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.directory / "shadow-lock.json"
        self.runs_path = self.directory / "shadow-runs.jsonl"

    @staticmethod
    def configuration_hash(configuration: dict[str, object]) -> str:
        return sha256(json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def lock(self, configuration: dict[str, object], model_version: str) -> ShadowLock:
        current = ShadowLock(self.configuration_hash(configuration), model_version, datetime.now(timezone.utc))
        if self.lock_path.exists():
            existing = self.read_lock()
            if existing.configuration_hash != current.configuration_hash or existing.model_version != model_version:
                raise RuntimeError("shadow configuration is locked; create a new experiment instead of tuning in place")
            return existing
        self.lock_path.write_text(
            json.dumps(
                {
                    "configuration_hash": current.configuration_hash,
                    "model_version": current.model_version,
                    "locked_at": current.locked_at.isoformat(),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return current

    def read_lock(self) -> ShadowLock:
        payload = json.loads(self.lock_path.read_text(encoding="utf-8"))
        return ShadowLock(
            configuration_hash=payload["configuration_hash"],
            model_version=payload["model_version"],
            locked_at=datetime.fromisoformat(payload["locked_at"]),
        )

    def append_run(self, run: dict[str, object], configuration: dict[str, object], model_version: str) -> None:
        lock = self.lock(configuration, model_version)
        if self.configuration_hash(configuration) != lock.configuration_hash:
            raise RuntimeError("configuration drift detected")
        payload = {
            **run,
            "configuration_hash": lock.configuration_hash,
            "model_version": lock.model_version,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        with self.runs_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
