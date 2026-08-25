"""Training job contracts and the background job manager.

A training job runs in an isolated worker so the API stays responsive; clients
poll ``GET /api/trainings/{id}`` for live per-iteration reward history. On
completion the actors land in the :class:`CheckpointStore`, and the job's
metadata JSON doubles as the durable record, so completed trainings survive a
server restart while running state is process-local.
"""

from __future__ import annotations

import multiprocessing
import os
import queue
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..core.devices import select_device
from ..scenario.models import ObjectId, ScenarioRecord
from ..simulation.contracts import environment_contract
from ..training.algorithms import TrainingAlgorithm
from ..training.checkpoints import CheckpointStore
from ..training.registry import (
    get_training_algorithm,
    normalize_training_config,
    register_training_algorithm,
)
from ..training.trainer import TrainingConfig, train

TrainingState = Literal["running", "completed", "failed", "cancelled"]


class TrainingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: ObjectId
    scenario_version: int | None = Field(default=None, ge=1)
    config: TrainingConfig = Field(default_factory=TrainingConfig)


class TrainingStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_id: str
    scenario_id: str
    scenario_version: int
    scenario_hash: str
    environment_contract_hash: str | None = None
    physics_backend: str | None = None
    binding_ids: list[str]
    status: TrainingState
    config: TrainingConfig
    device: str | None = None
    iterations_done: int = 0
    history: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None


class _Job:
    def __init__(self, status: TrainingStatus, stop_event: Any | None = None) -> None:
        self.status = status
        self.stop_event = stop_event or threading.Event()
        self.lock = threading.Lock()


def _process_training_entry(
    status_payload: dict[str, Any],
    record_payload: dict[str, Any],
    config_payload: dict[str, Any],
    checkpoint_root: str,
    messages: Any,
    stop_event: Any,
    algorithm: TrainingAlgorithm,
) -> None:
    """Spawn-safe worker entry point; no FastAPI or manager state crosses the boundary."""
    # Runtime-registered algorithms must cross the spawn boundary explicitly;
    # built-ins simply replace the equivalent instance registered on import.
    register_training_algorithm(algorithm, replace=True)
    status = TrainingStatus.model_validate(status_payload)
    record = ScenarioRecord.model_validate(record_payload)
    config = TrainingConfig.model_validate(config_payload)

    def on_iteration(metrics: dict[str, Any]) -> None:
        status.history.append(metrics)
        status.iterations_done = metrics["iteration"] + 1
        messages.put(("iteration", metrics))

    try:
        result = train(
            record.scenario,
            config,
            on_iteration=on_iteration,
            should_stop=stop_event.is_set,
            scenario_hash=record.content_hash,
        )
        status.device = result.device
        status.status = "cancelled" if stop_event.is_set() else "completed"
        status.finished_at = datetime.now(UTC).isoformat()
        if status.status == "completed":
            CheckpointStore(checkpoint_root).save(
                status.training_id,
                status.model_dump(mode="json"),
                result.policies,
            )
    except Exception as exc:  # noqa: BLE001 - terminal failures must cross the process boundary
        status.status = "failed"
        status.error = str(exc)
        status.finished_at = datetime.now(UTC).isoformat()
    messages.put(("terminal", status.model_dump(mode="json")))


class TrainingManager:
    """Launches, tracks, cancels, and persists training jobs."""

    def __init__(self, root: Path, *, worker_mode: str | None = None) -> None:
        self.checkpoints = CheckpointStore(root)
        self.worker_mode = worker_mode or os.getenv("PYTHO_ARENA_TRAINING_WORKER", "process")
        if self.worker_mode not in {"thread", "process"}:
            raise ValueError("training worker mode must be 'thread' or 'process'")
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()

    def launch(
        self, training_id: str, record: ScenarioRecord, request: TrainingRequest
    ) -> TrainingStatus:
        scenario = record.scenario
        config = normalize_training_config(request.config)
        algorithm = get_training_algorithm(config.algorithm_id)
        binding_ids = (
            [binding.id for binding in scenario.policy_bindings if binding.trainable]
            if config.binding_ids is None
            else config.binding_ids
        )
        known = {binding.id for binding in scenario.policy_bindings}
        unknown = sorted(set(binding_ids) - known)
        if unknown:
            raise ValueError(f"unknown trainable binding ids: {unknown}")
        if not binding_ids:
            raise ValueError("scenario has no trainable policy bindings")
        declared_trainable = {
            binding.id for binding in scenario.policy_bindings if binding.trainable
        }
        fixed = sorted(set(binding_ids) - declared_trainable)
        if fixed:
            raise ValueError(f"bindings are not marked trainable: {fixed}")
        select_device(config.device)  # fail fast on an unusable device
        contract = environment_contract(scenario, scenario_hash=record.content_hash)
        config = config.model_copy(update={"binding_ids": binding_ids})

        status = TrainingStatus(
            training_id=training_id,
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.version,
            scenario_hash=record.content_hash,
            environment_contract_hash=contract.content_hash(),
            physics_backend=contract.physics_backend,
            binding_ids=binding_ids,
            status="running",
            config=config,
        )
        if self.worker_mode == "process":
            context = multiprocessing.get_context("spawn")
            stop_event = context.Event()
            messages = context.Queue()
            job = _Job(status, stop_event)
        else:
            context = None
            messages = None
            job = _Job(status)
        with self._lock:
            self._jobs[training_id] = job
        if self.worker_mode == "process":
            assert context is not None and messages is not None
            process = context.Process(
                target=_process_training_entry,
                args=(
                    status.model_dump(mode="json"),
                    record.model_dump(mode="json"),
                    config.model_dump(mode="json"),
                    str(self.checkpoints.root),
                    messages,
                    job.stop_event,
                    algorithm,
                ),
                name=f"pytho-arena-training-{training_id}",
                daemon=True,
            )
            process.start()
            threading.Thread(
                target=self._monitor_process,
                args=(job, process, messages),
                name=f"pytho-arena-training-monitor-{training_id}",
                daemon=True,
            ).start()
        else:
            threading.Thread(
                target=self._run,
                args=(job, record, config),
                name=f"pytho-arena-training-{training_id}",
                daemon=True,
            ).start()
        return status.model_copy()

    @staticmethod
    def _monitor_process(job: _Job, process: Any, messages: Any) -> None:
        terminal_received = False

        def apply_message(kind: str, payload: dict[str, Any]) -> None:
            nonlocal terminal_received
            with job.lock:
                if kind == "iteration":
                    job.status.history.append(payload)
                    job.status.iterations_done = payload["iteration"] + 1
                else:
                    job.status = TrainingStatus.model_validate(payload)
                    terminal_received = True

        while process.is_alive():
            try:
                kind, payload = messages.get(timeout=0.2)
            except queue.Empty:
                continue
            apply_message(kind, payload)
        process.join()
        while True:
            try:
                kind, payload = messages.get(timeout=0.5)
            except queue.Empty:
                break
            apply_message(kind, payload)
        if not terminal_received:
            with job.lock:
                job.status.status = "failed"
                job.status.error = f"training worker exited with code {process.exitcode}"
                job.status.finished_at = datetime.now(UTC).isoformat()

    def _run(self, job: _Job, record: ScenarioRecord, config: TrainingConfig) -> None:
        def on_iteration(metrics: dict[str, Any]) -> None:
            with job.lock:
                job.status.history.append(metrics)
                job.status.iterations_done = metrics["iteration"] + 1

        try:
            result = train(
                record.scenario,
                config,
                on_iteration=on_iteration,
                should_stop=job.stop_event.is_set,
                scenario_hash=record.content_hash,
            )
            with job.lock:
                job.status.device = result.device
                job.status.status = "cancelled" if job.stop_event.is_set() else "completed"
                job.status.finished_at = datetime.now(UTC).isoformat()
                snapshot = job.status.model_copy(deep=True)
            if snapshot.status == "completed":
                self.checkpoints.save(
                    snapshot.training_id,
                    snapshot.model_dump(mode="json"),
                    result.policies,
                )
        except Exception as exc:  # noqa: BLE001 - the job must record any failure
            with job.lock:
                job.status.status = "failed"
                job.status.error = str(exc)
                job.status.finished_at = datetime.now(UTC).isoformat()

    def get(self, training_id: str) -> TrainingStatus:
        with self._lock:
            job = self._jobs.get(training_id)
        if job is not None:
            with job.lock:
                return job.status.model_copy(deep=True)
        return TrainingStatus.model_validate(self.checkpoints.meta(training_id))

    def list(self) -> list[TrainingStatus]:
        statuses: dict[str, TrainingStatus] = {
            meta["training_id"]: TrainingStatus.model_validate(meta)
            for meta in self.checkpoints.list_meta()
        }
        with self._lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            with job.lock:
                statuses[job.status.training_id] = job.status.model_copy(deep=True)
        return sorted(statuses.values(), key=lambda status: status.created_at)

    def cancel(self, training_id: str) -> TrainingStatus:
        with self._lock:
            job = self._jobs.get(training_id)
        if job is None:
            raise KeyError(training_id)
        job.stop_event.set()
        with job.lock:
            return job.status.model_copy(deep=True)
