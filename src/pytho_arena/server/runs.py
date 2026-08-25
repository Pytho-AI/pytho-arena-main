"""Run contracts and the filesystem evidence store."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..scenario.models import ObjectId, ScenarioSpec
from ..scenario.store import write_json_atomic
from ..simulation.cuas_lane import ScheduledDecision
from ..simulation.disruptions import DisruptionSpec


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: ObjectId
    scenario_version: int | None = Field(default=None, ge=1)
    policy_overrides: dict[ObjectId, str] = Field(default_factory=dict)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    disruptions: list[DisruptionSpec] = Field(default_factory=list, max_length=32)


class BranchRequest(BaseModel):
    """Operator decisions to replay against an existing run's exact inputs."""

    model_config = ConfigDict(extra="forbid")

    decisions: list[ScheduledDecision] = Field(min_length=1, max_length=32)


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    scenario_id: str
    scenario_version: int
    scenario_hash: str
    seed: int
    policies: dict[str, str]
    device: str
    disruptions: list[DisruptionSpec] = Field(default_factory=list)
    steps: int
    metrics: dict[str, Any]
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    # Branch provenance. Runs saved before branching existed omit both keys and
    # still validate, and a parent run is never rewritten when a child is made.
    parent_run_id: str | None = None
    branch_decisions: list[ScheduledDecision] = Field(default_factory=list)


class RunStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def exists(self, run_id: str) -> bool:
        return (self.root / f"{run_id}.json").exists()

    def save(
        self,
        summary: RunSummary,
        scenario: ScenarioSpec,
        frames: list[dict[str, Any]],
    ) -> None:
        if self.exists(summary.run_id):
            raise ValueError(f"run {summary.run_id!r} already exists and is immutable")
        write_json_atomic(
            self.root / f"{summary.run_id}.json",
            {
                "summary": summary.model_dump(mode="json"),
                "scenario": scenario.model_dump(mode="json"),
                "frames": frames,
            },
        )

    def get(self, run_id: str) -> dict[str, Any]:
        path = self.root / f"{run_id}.json"
        if not path.exists():
            raise KeyError(run_id)
        return json.loads(path.read_text(encoding="utf-8"))
