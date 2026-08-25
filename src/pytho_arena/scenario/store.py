"""Filesystem registry for immutable, versioned scenarios."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .models import ScenarioRecord, ScenarioSpec, library_scenarios


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


class ScenarioRegistry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._lock = threading.Lock()

    def ensure_library(self) -> list[ScenarioRecord]:
        """Seed the registry with every curated scenario not yet saved."""
        records: list[ScenarioRecord] = []
        for scenario in library_scenarios():
            try:
                records.append(self.get(scenario.scenario_id))
            except KeyError:
                records.append(self.save(scenario))
        return records

    def save(self, scenario: ScenarioSpec) -> ScenarioRecord:
        with self._lock:
            scenario_dir = self.root / scenario.scenario_id
            existing = sorted(scenario_dir.glob("v*.json")) if scenario_dir.exists() else []
            versions = [int(path.stem[1:]) for path in existing if path.stem[1:].isdigit()]
            version = max(versions, default=0) + 1
            versioned = scenario.model_copy(update={"version": version})
            record = ScenarioRecord(
                scenario=versioned,
                content_hash=versioned.content_hash(),
            )
            write_json_atomic(
                scenario_dir / f"v{version:04d}.json",
                record.model_dump(mode="json"),
            )
            return record

    def get(self, scenario_id: str, version: int | None = None) -> ScenarioRecord:
        scenario_dir = self.root / scenario_id
        if version is None:
            paths = sorted(scenario_dir.glob("v*.json")) if scenario_dir.exists() else []
            if not paths:
                raise KeyError(scenario_id)
            path = paths[-1]
        else:
            path = scenario_dir / f"v{version:04d}.json"
            if not path.exists():
                raise KeyError(f"{scenario_id}@{version}")
        return ScenarioRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[ScenarioRecord]:
        records: list[ScenarioRecord] = []
        if not self.root.exists():
            return records
        for directory in sorted(path for path in self.root.iterdir() if path.is_dir()):
            paths = sorted(directory.glob("v*.json"))
            if paths:
                records.append(
                    ScenarioRecord.model_validate_json(paths[-1].read_text(encoding="utf-8"))
                )
        return records
