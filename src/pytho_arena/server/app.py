"""Standalone FastAPI application for Pytho Arena."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path
from typing import Annotated, get_args

import torch
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..core.devices import mps_usable, select_device
from ..core.env import BatchedScenarioEnv
from ..live import LiveDataBuffer, TrackBatch
from ..policies.registry import build_policies, resolve_policy_ids
from ..scenario.models import RewardEvent, ScenarioRecord, ScenarioSpec
from ..scenario.store import ScenarioRegistry, write_json_atomic
from ..simulation.contracts import environment_contract
from ..simulation.physics import available_physics_backends
from ..training import DEFAULT_ALGORITHM_ID, available_training_algorithms
from .replay import (
    first_divergent_frame,
    recorded_cuas_rollout,
    recorded_rollout,
    scenario_has_typed_effector,
)
from .runs import BranchRequest, RunRequest, RunStore, RunSummary
from .trainings import TrainingManager, TrainingRequest, TrainingStatus

FRONTEND_DIR = Path(str(files("pytho_arena.server").joinpath("frontend")))
DEFAULT_DATA_DIR = Path.cwd() / "var" / "arena"


def create_app(data_dir: Path | str | None = None) -> FastAPI:
    storage = Path(data_dir or os.getenv("PYTHO_ARENA_DATA_DIR", DEFAULT_DATA_DIR))
    scenarios = ScenarioRegistry(storage / "scenarios")
    runs = RunStore(storage / "runs")
    trainings = TrainingManager(storage / "trainings")
    live_data = LiveDataBuffer()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        scenarios.ensure_library()
        yield

    app = FastAPI(
        title="Pytho Arena",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.scenarios = scenarios
    app.state.runs = runs
    app.state.trainings = trainings
    app.state.live_data = live_data
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="arena-static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/trainings/{training_id}", include_in_schema=False)
    def training_page(training_id: str) -> FileResponse:
        return FileResponse(FRONTEND_DIR / "training.html")

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "torch": torch.__version__,
            "cuda": torch.cuda.is_available(),
            "mps": mps_usable(),
            "defaultDevice": str(select_device("auto")),
            "trainingWorker": trainings.worker_mode,
        }

    @app.get("/api/scenarios")
    def list_scenarios() -> dict:
        records = scenarios.list()
        return {
            "scenarios": [
                {
                    "scenarioId": record.scenario.scenario_id,
                    "version": record.scenario.version,
                    "name": record.scenario.name,
                    "contentHash": record.content_hash,
                    "createdAt": record.created_at,
                }
                for record in records
            ]
        }

    @app.get("/api/capabilities")
    def capabilities() -> dict:
        return {
            "physicsBackends": available_physics_backends(),
            "rewardEvents": get_args(RewardEvent),
            "spatialDimensions": [2, 3],
            "liveMode": "shadow",
            "trainingWorker": trainings.worker_mode,
            "trainingAlgorithms": [descriptor.id for descriptor in available_training_algorithms()],
        }

    @app.get("/api/training-algorithms")
    def training_algorithms() -> dict:
        return {
            "defaultAlgorithmId": DEFAULT_ALGORITHM_ID,
            "algorithms": [
                descriptor.model_dump(mode="json") for descriptor in available_training_algorithms()
            ],
        }

    @app.get("/api/scenarios/{scenario_id}")
    def get_scenario(
        scenario_id: str,
        version: int | None = Query(default=None, ge=1),
    ) -> ScenarioRecord:
        try:
            return scenarios.get(scenario_id, version)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="scenario version not found") from exc

    @app.post("/api/scenarios/validate")
    def validate_scenario(scenario: ScenarioSpec) -> dict:
        try:
            contract = environment_contract(scenario)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "valid": True,
            "contentHash": scenario.content_hash(),
            "steps": scenario.steps,
            "entities": scenario.entity_count,
            "factions": len(scenario.factions),
            "evaluationFactionId": scenario.evaluation_faction_id,
            "sensors": len(scenario.sensors),
            "policyBindings": len(scenario.policy_bindings),
            "physicsBackend": contract.physics_backend,
            "spatialDimensions": contract.spatial_dimensions,
            "environmentContractHash": contract.content_hash(),
            "rewardTerms": len(scenario.reward_terms),
        }

    @app.post("/api/scenarios", status_code=201)
    def save_scenario(scenario: ScenarioSpec) -> ScenarioRecord:
        try:
            environment_contract(scenario)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return scenarios.save(scenario)

    @app.post("/api/scenarios/import-document", status_code=201)
    async def import_scenario_docx(file: Annotated[UploadFile, File()]) -> dict:
        from ..scenario.documents import MAX_DOCX_BYTES, import_scenario_document

        filename = file.filename or "scenario.docx"
        if not filename.lower().endswith(".docx"):
            raise HTTPException(status_code=400, detail="scenario document must be a .docx file")
        try:
            result = import_scenario_document(await file.read(MAX_DOCX_BYTES + 1), filename)
            environment_contract(result.scenario)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        record = scenarios.save(result.scenario)
        report_payload = {
            "scenarioId": record.scenario.scenario_id,
            "scenarioVersion": record.scenario.version,
            **result.report.model_dump(mode="json"),
        }
        write_json_atomic(
            storage
            / "imports"
            / record.scenario.scenario_id
            / f"v{record.scenario.version:04d}.json",
            report_payload,
        )
        return {"record": record.model_dump(mode="json"), "report": report_payload}

    @app.get("/api/scenarios/{scenario_id}/background-document")
    def scenario_background_document(
        scenario_id: str,
        version: int | None = Query(default=None, ge=1),
    ) -> FileResponse:
        from ..scenario.documents import export_scenario_document

        try:
            record = scenarios.get(scenario_id, version)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="scenario version not found") from exc
        output = (
            storage
            / "exports"
            / f"{record.scenario.scenario_id}-v{record.scenario.version:04d}-background.docx"
        )
        hero_image = None
        if (
            record.scenario.visualization is None
            or record.scenario.visualization.environment == "gulf_airbase"
        ):
            candidate = FRONTEND_DIR / "assets" / "raven_airbase_brief.png"
            hero_image = candidate if candidate.is_file() else None
        export_scenario_document(record.scenario, output, hero_image=hero_image)
        return FileResponse(
            output,
            media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            filename=output.name,
        )

    @app.post("/api/runs", status_code=201)
    def create_run(request: RunRequest) -> RunSummary:
        try:
            record = scenarios.get(request.scenario_id, request.scenario_version)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="scenario version not found") from exc
        scenario = record.scenario
        seed = scenario.seed if request.seed is None else request.seed
        try:
            env = BatchedScenarioEnv(
                scenario,
                batch_size=1,
                seed=seed,
                device=request.device,
                scenario_hash=record.content_hash,
                disruptions=request.disruptions,
            )
            policies = build_policies(
                env,
                request.policy_overrides,
                checkpoint_loader=trainings.checkpoints.loader(),
            )
            frames, run_metrics = (
                recorded_cuas_rollout(env, policies)
                if scenario_has_typed_effector(env)
                else recorded_rollout(env, policies)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        summary = RunSummary(
            run_id=str(uuid.uuid4()),
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.version,
            scenario_hash=record.content_hash,
            seed=seed,
            policies=resolve_policy_ids(scenario, request.policy_overrides),
            device=str(env.device),
            disruptions=request.disruptions,
            steps=scenario.steps,
            metrics=run_metrics,
        )
        runs.save(summary, scenario, frames)
        return summary

    @app.post("/api/runs/{parent_run_id}/branches", status_code=201)
    def create_branch(parent_run_id: str, request: BranchRequest) -> RunSummary:
        """Re-run a saved run's exact inputs with operator decisions applied.

        The parent run is never modified. The child re-runs the same scenario,
        seed, device, and policies, so every frame before the earliest decision
        must match the parent byte for byte; a mismatch is a determinism defect
        and fails the request rather than saving misleading evidence.
        """
        try:
            parent = runs.get(parent_run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc
        parent_summary = RunSummary.model_validate(parent["summary"])
        scenario = ScenarioSpec.model_validate(parent["scenario"])
        branch_step = min(decision.step for decision in request.decisions)
        if branch_step >= len(parent["frames"]):
            raise HTTPException(
                status_code=400,
                detail=f"decision step {branch_step} lies outside the parent run",
            )
        try:
            env = BatchedScenarioEnv(
                scenario,
                batch_size=1,
                seed=parent_summary.seed,
                device=parent_summary.device,
                scenario_hash=parent_summary.scenario_hash,
                disruptions=parent_summary.disruptions,
            )
            if not scenario_has_typed_effector(env):
                raise ValueError("scenario declares no typed effector to decide on")
            policies = build_policies(
                env,
                parent_summary.policies,
                checkpoint_loader=trainings.checkpoints.loader(),
            )
            frames, run_metrics = recorded_cuas_rollout(env, policies, decisions=request.decisions)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        divergence = first_divergent_frame(parent["frames"], frames, limit=branch_step)
        if divergence is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"branch diverged from its parent at frame {divergence}, "
                    f"before the decision at step {branch_step}"
                ),
            )
        summary = RunSummary(
            run_id=str(uuid.uuid4()),
            scenario_id=parent_summary.scenario_id,
            scenario_version=parent_summary.scenario_version,
            scenario_hash=parent_summary.scenario_hash,
            seed=parent_summary.seed,
            policies=parent_summary.policies,
            device=str(env.device),
            disruptions=parent_summary.disruptions,
            steps=parent_summary.steps,
            metrics=run_metrics,
            parent_run_id=parent_run_id,
            branch_decisions=list(request.decisions),
        )
        runs.save(summary, scenario, frames)
        return summary

    @app.post("/api/trainings", status_code=201)
    def create_training(request: TrainingRequest) -> TrainingStatus:
        try:
            record = scenarios.get(request.scenario_id, request.scenario_version)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="scenario version not found") from exc
        training_id = str(uuid.uuid4())
        try:
            return trainings.launch(training_id, record, request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/trainings")
    def list_trainings() -> dict:
        return {"trainings": [status.model_dump(mode="json") for status in trainings.list()]}

    @app.post("/api/live/tracks", status_code=202)
    def ingest_live_tracks(batch: TrackBatch) -> dict:
        """Accept canonical tracks in shadow mode without issuing external commands."""
        accepted = live_data.ingest(batch.updates)
        return {"accepted": accepted, "mode": "shadow"}

    @app.get("/api/live/tracks/latest")
    def latest_live_tracks() -> dict:
        return {
            "tracks": [track.model_dump(mode="json") for track in live_data.latest()],
            "mode": "shadow",
        }

    @app.get("/api/trainings/{training_id}")
    def get_training(training_id: str) -> TrainingStatus:
        try:
            return trainings.get(training_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="training not found") from exc

    @app.post("/api/trainings/{training_id}/cancel")
    def cancel_training(training_id: str) -> TrainingStatus:
        try:
            return trainings.cancel(training_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="training not found") from exc

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        try:
            return runs.get(run_id)["summary"]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.get("/api/runs/{run_id}/replay")
    def replay(run_id: str) -> dict:
        try:
            return runs.get(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    return app


app = create_app()
