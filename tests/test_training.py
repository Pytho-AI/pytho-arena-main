"""Trainer, checkpoint store/registry integration, and training API tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import torch

from pytho_arena.core.env import BatchedScenarioEnv
from pytho_arena.env.rollout import episode
from pytho_arena.policies import build_policies, resolve_policy_ids
from pytho_arena.server.app import create_app
from pytho_arena.simulation.contracts import environment_contract
from pytho_arena.training import (
    CheckpointStore,
    TrainingConfig,
    available_training_algorithms,
    normalize_training_config,
    train,
)

from .test_sim import tiny_scenario

FAST_CONFIG = TrainingConfig(iterations=2, batch_size=4, device="cpu", seed=11)


def test_train_returns_history_and_payloads():
    result = train(tiny_scenario(), FAST_CONFIG)
    assert result.algorithm_id == "reinforce"
    assert result.algorithm_parameters == {"gamma": 0.99, "entropy_coef": 0.01}
    assert result.binding_ids == ["red-movement", "blue-sensing"]
    assert result.iterations_done == 2
    assert [entry["iteration"] for entry in result.history] == [0, 1]
    for entry in result.history:
        for agent in result.binding_ids:
            assert isinstance(entry["returns"][agent], float)
            assert isinstance(entry["loss"][agent], float)
    for binding_id, payload in result.policies.items():
        assert payload["role"] in {"movement", "sensing"}
        assert payload["algorithm_id"] == "reinforce"
        assert all(torch.isfinite(value).all() for value in payload["state_dict"].values())
        assert binding_id in result.binding_ids


def test_reinforce_is_registered_and_legacy_parameters_are_migrated():
    descriptors = available_training_algorithms()
    assert [descriptor.id for descriptor in descriptors] == ["reinforce"]
    assert [parameter.id for parameter in descriptors[0].parameters] == [
        "gamma",
        "entropy_coef",
    ]

    legacy = TrainingConfig.model_validate({"gamma": 0.8, "entropy_coef": 0.02})
    normalized = normalize_training_config(legacy)
    assert normalized.algorithm_id == "reinforce"
    assert normalized.algorithm_parameters == {"gamma": 0.8, "entropy_coef": 0.02}


def test_training_registry_rejects_unknown_algorithm_and_parameters():
    with pytest.raises(ValueError, match="unknown training algorithm"):
        train(
            tiny_scenario(),
            FAST_CONFIG.model_copy(update={"algorithm_id": "missing"}),
        )
    with pytest.raises(ValueError, match="invalid parameters.*gamma"):
        train(
            tiny_scenario(),
            FAST_CONFIG.model_copy(update={"algorithm_parameters": {"gamma": 2.0}}),
        )


def test_train_is_deterministic_for_a_seed():
    first = train(tiny_scenario(), FAST_CONFIG)
    second = train(tiny_scenario(), FAST_CONFIG)
    assert first.history == second.history
    for binding_id, payload in first.policies.items():
        for key, value in payload["state_dict"].items():
            assert torch.equal(value, second.policies[binding_id]["state_dict"][key])


def test_training_session_carries_disruptions_into_the_arena():
    from pytho_arena import CommunicationsDisruption, SensorDisruption
    from pytho_arena.training.session import TrainingSession

    # Persisted configs without the field still validate and default off.
    migrated = TrainingConfig.model_validate({"iterations": 2, "batch_size": 4})
    assert migrated.disruptions == []

    # Typed disruption specs reach the arena's compiled tensors.
    disrupted = TrainingSession.create(
        tiny_scenario(),
        FAST_CONFIG.model_copy(
            update={"disruptions": [SensorDisruption(detection_probability_multiplier=0.0)]}
        ),
    )
    assert not disrupted.arena.env.sensor_pd.any()

    # A fully blind defender trains against zero delivered reports but the
    # job still runs end to end and records history.
    blind = train(
        tiny_scenario(),
        FAST_CONFIG.model_copy(
            update={"disruptions": [CommunicationsDisruption(drop_probability=1.0)]}
        ),
    )
    assert blind.iterations_done == 2


def test_train_rejects_unknown_and_untrainable_selection():
    with pytest.raises(ValueError, match="unknown trainable binding ids"):
        train(tiny_scenario(), FAST_CONFIG.model_copy(update={"binding_ids": ["nope"]}))
    scenario = tiny_scenario().model_copy(
        update={
            "policy_bindings": [
                binding.model_copy(update={"trainable": False})
                for binding in tiny_scenario().policy_bindings
            ]
        }
    )
    with pytest.raises(ValueError, match="no trainable policy bindings"):
        train(scenario, FAST_CONFIG.model_copy(update={"binding_ids": None}))


def test_checkpoint_policies_drive_a_run(tmp_path: Path):
    scenario = tiny_scenario()
    result = train(scenario, FAST_CONFIG)
    store = CheckpointStore(tmp_path / "checkpoints")
    store.save(
        "ckpt-1",
        {
            "training_id": "ckpt-1",
            "scenario_id": scenario.scenario_id,
            "scenario_hash": scenario.content_hash(),
            "environment_contract_hash": environment_contract(scenario).content_hash(),
        },
        result.policies,
    )

    overrides = {"red-movement": "checkpoint:ckpt-1", "blue-sensing": "checkpoint:ckpt-1"}
    resolved = resolve_policy_ids(scenario, overrides)
    assert resolved["red-movement"] == "checkpoint:ckpt-1"

    env = BatchedScenarioEnv(scenario, batch_size=2, seed=3, device="cpu")
    policies = build_policies(env, overrides, checkpoint_loader=store.loader())
    assert policies["red-movement"].policy_id == "checkpoint:ckpt-1"
    outputs = list(episode(env, policies))
    assert len(outputs) == scenario.steps

    # Deterministic inference: the same checkpoint replays bit-for-bit.
    env_repeat = BatchedScenarioEnv(scenario, batch_size=2, seed=3, device="cpu")
    policies_repeat = build_policies(env_repeat, overrides, checkpoint_loader=store.loader())
    repeat_outputs = list(episode(env_repeat, policies_repeat))
    assert torch.equal(
        outputs[-1].observations["blue"]["own_positions"],
        repeat_outputs[-1].observations["blue"]["own_positions"],
    )


def test_checkpoint_loader_guards(tmp_path: Path):
    scenario = tiny_scenario()
    result = train(scenario, FAST_CONFIG)
    store = CheckpointStore(tmp_path / "checkpoints")
    store.save(
        "ckpt-1", {"training_id": "ckpt-1", "scenario_id": "other-scenario"}, result.policies
    )
    store.save(
        "ckpt-2",
        {"training_id": "ckpt-2", "scenario_id": scenario.scenario_id, "scenario_version": 99},
        result.policies,
    )

    env = BatchedScenarioEnv(scenario, batch_size=1, seed=3, device="cpu")
    with pytest.raises(ValueError, match="no checkpoint loader"):
        build_policies(env, {"red-movement": "checkpoint:ckpt-1"})
    with pytest.raises(ValueError, match="trained on scenario"):
        build_policies(env, {"red-movement": "checkpoint:ckpt-1"}, checkpoint_loader=store.loader())
    with pytest.raises(ValueError, match="scenario version"):
        build_policies(env, {"red-movement": "checkpoint:ckpt-2"}, checkpoint_loader=store.loader())
    with pytest.raises(ValueError, match="unknown checkpoint"):
        build_policies(
            env, {"red-movement": "checkpoint:missing"}, checkpoint_loader=store.loader()
        )
    with pytest.raises(ValueError, match="cannot execute binding"):
        resolve_policy_ids(scenario, {"red-movement": "not-a-policy"})


@pytest.mark.asyncio
async def test_api_training_lifecycle(tmp_path: Path):
    app = create_app(tmp_path / "training-data")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            saved = await client.post(
                "/api/scenarios", json=tiny_scenario().model_dump(mode="json")
            )
            assert saved.status_code == 201
            scenario = saved.json()["scenario"]

            missing = await client.post(
                "/api/trainings",
                json={"scenario_id": "does-not-exist", "config": {}},
            )
            assert missing.status_code == 404

            bad_binding = await client.post(
                "/api/trainings",
                json={
                    "scenario_id": scenario["scenario_id"],
                    "config": {"binding_ids": ["nope"]},
                },
            )
            assert bad_binding.status_code == 400

            algorithms = await client.get("/api/training-algorithms")
            assert algorithms.status_code == 200
            assert algorithms.json()["defaultAlgorithmId"] == "reinforce"
            assert algorithms.json()["algorithms"][0]["id"] == "reinforce"

            bad_algorithm = await client.post(
                "/api/trainings",
                json={
                    "scenario_id": scenario["scenario_id"],
                    "config": {"algorithm_id": "missing"},
                },
            )
            assert bad_algorithm.status_code == 400

            bad_parameters = await client.post(
                "/api/trainings",
                json={
                    "scenario_id": scenario["scenario_id"],
                    "config": {
                        "algorithm_id": "reinforce",
                        "algorithm_parameters": {"gamma": 1.5},
                    },
                },
            )
            assert bad_parameters.status_code == 400

            created = await client.post(
                "/api/trainings",
                json={
                    "scenario_id": scenario["scenario_id"],
                    "scenario_version": scenario["version"],
                    "config": {"iterations": 2, "batch_size": 2, "device": "cpu"},
                },
            )
            assert created.status_code == 201
            status = created.json()
            training_id = status["training_id"]
            assert status["status"] == "running"
            assert status["binding_ids"] == ["red-movement", "blue-sensing"]
            assert status["config"]["algorithm_id"] == "reinforce"
            assert status["config"]["algorithm_parameters"] == {
                "gamma": 0.99,
                "entropy_coef": 0.01,
            }

            for _ in range(300):
                poll = await client.get(f"/api/trainings/{training_id}")
                assert poll.status_code == 200
                status = poll.json()
                if status["status"] != "running":
                    break
                await asyncio.sleep(0.2)
            assert status["status"] == "completed"
            assert status["iterations_done"] == 2
            assert len(status["history"]) == 2

            listing = await client.get("/api/trainings")
            assert training_id in [item["training_id"] for item in listing.json()["trainings"]]

            run = await client.post(
                "/api/runs",
                json={
                    "scenario_id": scenario["scenario_id"],
                    "scenario_version": scenario["version"],
                    "policy_overrides": {
                        "red-movement": f"checkpoint:{training_id}",
                        "blue-sensing": f"checkpoint:{training_id}",
                    },
                    "seed": 5,
                    "device": "cpu",
                },
            )
            assert run.status_code == 201
            summary = run.json()
            assert summary["policies"]["red-movement"] == f"checkpoint:{training_id}"
            assert summary["policies"]["neutral-movement"] == "transit"

            details_page = await client.get(f"/trainings/{training_id}")
            assert details_page.status_code == 200
            assert "Training details" in details_page.text
            details_script = await client.get("/static/training.js")
            assert details_script.status_code == 200

            not_found = await client.get("/api/trainings/nope")
            assert not_found.status_code == 404
            cancel_missing = await client.post("/api/trainings/nope/cancel")
            assert cancel_missing.status_code == 404
