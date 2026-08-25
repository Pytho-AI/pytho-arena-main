"""Generalized physics, objectives, live contracts, and population evaluation."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
import torch
from pydantic import ValidationError

from pytho_arena.core.env import BatchedScenarioEnv
from pytho_arena.env.rollout import compute_actions, episode
from pytho_arena.experiments import (
    ExperimentManifest,
    PolicyCandidate,
    empirical_regret,
    evaluate_population,
)
from pytho_arena.live import LiveDataBuffer, ReplayTrackAdapter, TrackUpdate
from pytho_arena.policies import build_policies
from pytho_arena.scenario.models import (
    RewardTermSpec,
    ScenarioRecord,
    ScenarioSpec,
    SimulationSpec,
)
from pytho_arena.server.app import create_app
from pytho_arena.server.replay import frame as replay_frame
from pytho_arena.server.replay import recorded_rollout
from pytho_arena.server.trainings import TrainingManager, TrainingRequest
from pytho_arena.simulation.contracts import environment_contract
from pytho_arena.training import CheckpointStore, TrainingConfig, train

from .test_sim import engagement_scenario, tiny_scenario


def point_mass_scenario() -> ScenarioSpec:
    payload = tiny_scenario("point-mass-scenario").model_dump(mode="json")
    payload["world"]["vertical_extent"] = 50.0
    payload["protected_zones"][0]["altitude"] = 30.0
    payload["simulation"] = {
        "physics_backend": "point_mass_3d",
        "physics_step_seconds": 0.25,
        "sensor_interval_seconds": 2.0,
        "effects_interval_seconds": 1.0,
    }
    for group in payload["actor_groups"]:
        group["domain"] = "air"
        group["components"]["mobility"].update(
            {
                "model": "point_mass_3d",
                "max_acceleration": 4.0,
                "initial_altitude": 20.0,
            }
        )
    for sensor in payload["sensors"]:
        sensor["altitude"] = 20.0
    for response in payload["responses"]:
        response["altitude"] = 20.0
    return ScenarioSpec.model_validate(payload)


def multirotor_scenario() -> ScenarioSpec:
    payload = point_mass_scenario().model_dump(mode="json")
    payload["world"]["meters_per_unit"] = 1.0
    payload["simulation"].update(
        {
            "physics_backend": "multirotor_6dof",
            "physics_step_seconds": 0.02,
        }
    )
    for group in payload["actor_groups"]:
        group["domain"] = "air"
        group["components"]["mobility"]["model"] = "multirotor_6dof"
    return ScenarioSpec.model_validate(payload)


def test_point_mass_3d_runs_through_existing_policy_contract():
    scenario = point_mass_scenario()
    env = BatchedScenarioEnv(scenario, batch_size=2, device="cpu")
    policies = build_policies(env)
    observations = env.reset()
    actions = compute_actions(policies, observations, 0)

    assert actions["red-movement"].shape == (2, 4, 3)
    before = env.positions.clone()
    output = env.step(actions)

    assert env.positions.shape == (2, 6, 3)
    red_indices = env.movement_binding_entities["red-movement"]
    assert torch.all(env.positions[:, red_indices, 2] > 20.0)
    assert torch.linalg.vector_norm(env.positions - before, dim=-1).max() <= 1.01
    assert output.observations["red"]["tracks"].shape[-1] == 3
    assert env.scheduler.physics_substeps == 4
    assert "orientationWxyz" not in replay_frame(env)["truth"][0]


def test_multirotor_6dof_runs_through_existing_policy_contract():
    env = BatchedScenarioEnv(multirotor_scenario(), batch_size=2, device="cpu")
    observations = env.reset()
    actions = compute_actions(build_policies(env), observations, 0)

    env.step(actions)
    rendered = replay_frame(env)

    assert env.positions.shape == (2, 6, 3)
    assert env.orientations.shape == (2, 6, 4)
    assert env.angular_velocities.shape == (2, 6, 3)
    quaternion_norm = torch.linalg.vector_norm(env.orientations, dim=-1)
    torch.testing.assert_close(
        quaternion_norm, torch.ones_like(quaternion_norm), atol=1e-5, rtol=0.0
    )
    assert torch.isfinite(env.positions).all()
    assert env.scheduler.physics_substeps == 50
    assert len(rendered["truth"][0]["position"]) == 3
    assert len(rendered["truth"][0]["orientationWxyz"]) == 4


def test_multi_rate_scheduler_skips_sensing_between_due_steps():
    env = BatchedScenarioEnv(point_mass_scenario(), device="cpu")
    policies = build_policies(env)
    observations = env.reset()
    first = env.step(compute_actions(policies, observations, 0))
    second = env.step(compute_actions(policies, first.observations, 1))
    assert not second.info["detected_count"].any()


def test_legacy_defense_penalty_is_per_faction_not_per_response_asset():
    one = engagement_scenario(response_effectiveness=0.0)
    two = one.model_copy(
        update={
            "responses": [
                one.responses[0],
                one.responses[0].model_copy(update={"id": "blue-response-two"}),
            ]
        }
    )
    zero = one.model_copy(update={"responses": []})

    def blue_return(scenario: ScenarioSpec) -> float:
        env = BatchedScenarioEnv(scenario, device="cpu")
        return sum(float(step.rewards["blue"].item()) for step in episode(env, build_policies(env)))

    assert blue_return(zero) == -16.0
    assert blue_return(one) == -16.0
    assert blue_return(two) == -16.0


def test_faction_scoped_transit_objective_rewards_neutral_agents():
    scenario = tiny_scenario()
    neutral_group = scenario.actor_groups[1].model_copy(update={"speed": 100.0})
    scenario = scenario.model_copy(
        update={
            "actor_groups": [scenario.actor_groups[0], neutral_group],
            "reward_terms": [
                RewardTermSpec(
                    id="neutral-transit",
                    faction_id="neutral",
                    event="transit_completion",
                    weight=2.0,
                )
            ],
        }
    )
    env = BatchedScenarioEnv(scenario, device="cpu")
    first = next(iter(episode(env, build_policies(env))))
    assert first.rewards["neutral"].item() == 4.0
    assert first.rewards["red"].item() == 0.0


def test_single_sample_training_remains_finite():
    payload = tiny_scenario().model_dump(mode="json")
    payload["duration_seconds"] = 5.0
    payload["step_seconds"] = 5.0
    scenario = ScenarioSpec.model_validate(payload)
    result = train(
        scenario,
        TrainingConfig(iterations=1, batch_size=1, device="cpu", seed=11),
    )
    assert all(torch.isfinite(torch.tensor(value)) for value in result.history[0]["loss"].values())
    assert all(
        torch.isfinite(tensor).all()
        for policy in result.policies.values()
        for tensor in policy["state_dict"].values()
    )


def test_training_binding_selection_is_unique_and_declared_trainable():
    with pytest.raises(ValidationError, match="must be unique"):
        TrainingConfig(binding_ids=["red-movement", "red-movement"])
    with pytest.raises(ValueError, match="not marked trainable"):
        train(
            tiny_scenario(),
            TrainingConfig(
                binding_ids=["neutral-movement"], iterations=1, batch_size=2, device="cpu"
            ),
        )


def test_checkpoint_rejects_changed_scenario_hash(tmp_path: Path):
    scenario = tiny_scenario()
    result = train(scenario, TrainingConfig(iterations=1, batch_size=2, device="cpu"))
    contract = environment_contract(scenario)
    store = CheckpointStore(tmp_path)
    store.save(
        "checkpoint",
        {
            "training_id": "checkpoint",
            "scenario_id": scenario.scenario_id,
            "scenario_hash": scenario.content_hash(),
            "environment_contract_hash": contract.content_hash(),
        },
        result.policies,
    )
    changed = scenario.model_copy(update={"name": "Changed scenario"})
    env = BatchedScenarioEnv(changed, device="cpu")
    with pytest.raises(ValueError, match="scenario hash"):
        build_policies(
            env,
            {"red-movement": "checkpoint:checkpoint"},
            checkpoint_loader=store.loader(),
        )


def test_live_buffer_and_replay_adapter_share_track_contract():
    scenario = tiny_scenario()
    env = BatchedScenarioEnv(scenario, device="cpu")
    frames, _ = recorded_rollout(env, build_policies(env))
    updates = list(ReplayTrackAdapter(frames[:1]))
    buffer = LiveDataBuffer(capacity=100)
    assert buffer.ingest(updates) == scenario.entity_count
    assert len(buffer.latest()) == scenario.entity_count

    newer = TrackUpdate(
        source="test", track_id=updates[0].track_id, sequence=999, position=(1.0, 2.0)
    )
    stale = newer.model_copy(update={"sequence": 1, "position": (9.0, 9.0)})
    assert buffer.ingest([newer, stale]) == 1
    assert next(item for item in buffer.latest() if item.track_id == newer.track_id).position == (
        1.0,
        2.0,
    )


@pytest.mark.asyncio
async def test_live_track_api_is_shadow_mode_and_bounded_by_contract(tmp_path: Path):
    app = create_app(tmp_path / "live-data")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {
                "updates": [
                    {
                        "source": "recorded-feed",
                        "track_id": "track-1",
                        "sequence": 1,
                        "position": [10.0, 12.0, 3.0],
                        "confidence": 0.8,
                    }
                ]
            }
            accepted = await client.post("/api/live/tracks", json=payload)
            assert accepted.status_code == 202
            assert accepted.json() == {"accepted": 1, "mode": "shadow"}
            latest = await client.get("/api/live/tracks/latest")
            assert latest.status_code == 200
            assert latest.json()["tracks"][0]["track_id"] == "track-1"
            capabilities = await client.get("/api/capabilities")
            assert capabilities.status_code == 200
            assert capabilities.json()["physicsBackends"] == [
                "kinematic_2d",
                "multirotor_6dof",
                "point_mass_3d",
            ]
            assert capabilities.json()["trainingAlgorithms"] == ["reinforce"]
            assert "transit_completion" in capabilities.json()["rewardEvents"]
            invalid_scenario = tiny_scenario("unknown-backend").model_dump(mode="json")
            invalid_scenario["simulation"]["physics_backend"] = "missing_backend"
            validation = await client.post("/api/scenarios/validate", json=invalid_scenario)
            assert validation.status_code == 400
            assert "unknown physics backend" in validation.json()["detail"]


def test_population_manifest_evaluates_policy_combinations():
    scenario = tiny_scenario()
    populations = {
        "red": [
            PolicyCandidate(
                id="red-direct",
                faction_id="red",
                policy_overrides={"red-movement": "direct"},
            ),
            PolicyCandidate(
                id="red-probe",
                faction_id="red",
                policy_overrides={"red-movement": "probe"},
            ),
        ],
        "blue": [
            PolicyCandidate(
                id="blue-sweep",
                faction_id="blue",
                policy_overrides={"blue-sensing": "sweep"},
            )
        ],
    }
    manifest = ExperimentManifest.for_scenario(
        scenario, name="baseline population", seeds=[3, 7], populations=populations
    )
    results = evaluate_population(scenario, manifest)
    assert len(results) == 4
    assert set(empirical_regret(results, "red")) == {"red-direct", "red-probe"}
    assert len(manifest.content_hash()) == 64


def test_invalid_rate_and_mobility_combinations_are_rejected():
    scenario = tiny_scenario()
    with pytest.raises(ValidationError, match="physics_step_seconds"):
        ScenarioSpec.model_validate(
            {
                **scenario.model_dump(mode="json"),
                "simulation": SimulationSpec(
                    physics_backend="kinematic_2d", physics_step_seconds=0.3
                ).model_dump(mode="json"),
            }
        )


def test_optional_world_scale_preserves_legacy_hashes_and_versions_metric_worlds():
    base = tiny_scenario("world-scale-hash")
    legacy_payload = base.model_dump(mode="json")
    legacy_payload["world"].pop("meters_per_unit")
    legacy = ScenarioSpec.model_validate(legacy_payload)
    metric = base.model_copy(
        update={"world": base.world.model_copy(update={"meters_per_unit": 1.0})}
    )

    assert legacy.world.meters_per_unit is None
    assert legacy.content_hash() == base.content_hash()
    assert metric.content_hash() != base.content_hash()


def test_multirotor_scenarios_require_metric_scale_fast_ticks_and_air_domain():
    payload = multirotor_scenario().model_dump(mode="json")
    payload["world"]["meters_per_unit"] = None
    with pytest.raises(ValidationError, match="meters_per_unit"):
        ScenarioSpec.model_validate(payload)

    payload = multirotor_scenario().model_dump(mode="json")
    payload["simulation"]["physics_step_seconds"] = 0.05
    with pytest.raises(ValidationError, match="0.02 or less"):
        ScenarioSpec.model_validate(payload)

    payload = multirotor_scenario().model_dump(mode="json")
    payload["actor_groups"][0]["domain"] = "ground"
    with pytest.raises(ValidationError, match="air domain"):
        ScenarioSpec.model_validate(payload)


def test_training_can_run_in_an_isolated_worker_process(tmp_path: Path):
    scenario = tiny_scenario().model_copy(update={"version": 1})
    record = ScenarioRecord(scenario=scenario, content_hash=scenario.content_hash())
    manager = TrainingManager(tmp_path / "process-checkpoints", worker_mode="process")
    status = manager.launch(
        "process-training",
        record,
        TrainingRequest(
            scenario_id=scenario.scenario_id,
            scenario_version=1,
            config=TrainingConfig(iterations=1, batch_size=2, device="cpu"),
        ),
    )
    assert status.status == "running"
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        status = manager.get("process-training")
        if status.status != "running":
            break
        time.sleep(0.1)
    assert status.status == "completed", status.error
    assert manager.checkpoints.meta("process-training")["status"] == "completed"
