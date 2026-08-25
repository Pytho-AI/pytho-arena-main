"""Multi-faction contracts, deterministic engine, policy registry, and API tests."""

from __future__ import annotations

from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

import httpx
import pytest
import torch
from pydantic import ValidationError

from pytho_arena import (
    CommunicationsDisruption,
    EffectorDisruption,
    SensorDisruption,
    __version__,
)
from pytho_arena.core.devices import mps_usable
from pytho_arena.core.env import BatchedScenarioEnv
from pytho_arena.core.rng import stateless_uniform
from pytho_arena.env.rollout import compute_actions, episode
from pytho_arena.policies import build_policies
from pytho_arena.scenario.models import (
    ActorGroupSpec,
    FactionSpec,
    PolicyBindingSpec,
    RelationshipSpec,
    ResponseSpec,
    RewardSpec,
    ScenarioSpec,
    SensorSpec,
    TypedEffectorSpec,
    WorldSpec,
    ZoneSpec,
)
from pytho_arena.scenario.store import ScenarioRegistry
from pytho_arena.server.app import create_app
from pytho_arena.server.replay import recorded_rollout


def tiny_scenario(
    scenario_id: str = "tiny-scenario", *, response_effectiveness: float = 0.7
) -> ScenarioSpec:
    return ScenarioSpec(
        scenario_id=scenario_id,
        name="Tiny multi-faction scenario",
        duration_seconds=6.0,
        step_seconds=1.0,
        seed=13,
        evaluation_faction_id="blue",
        world=WorldSpec(width=60.0, height=50.0, vertical_extent=5.0),
        factions=[
            FactionSpec(id="red", name="Red", color="#ff6b6b"),
            FactionSpec(id="blue", name="Blue", color="#68f0b1"),
            FactionSpec(
                id="neutral",
                name="Neutral",
                category="background",
                color="#c7d1cd",
            ),
        ],
        relationships=[
            RelationshipSpec(
                source_faction_id="blue", target_faction_id="red", disposition="opponent"
            ),
            RelationshipSpec(
                source_faction_id="blue",
                target_faction_id="neutral",
                disposition="protected",
            ),
            RelationshipSpec(
                source_faction_id="red", target_faction_id="blue", disposition="opponent"
            ),
        ],
        protected_zones=[ZoneSpec(id="objective", center=(48.0, 25.0), radius=6.0)],
        actor_groups=[
            ActorGroupSpec(
                id="red-group",
                faction_id="red",
                count=4,
                mission="attack_objective",
                speed=1.0,
                start_edge="west",
                target_zone_id="objective",
                attack_probability=1.0,
            ),
            ActorGroupSpec(
                id="neutral-group",
                faction_id="neutral",
                count=2,
                mission="transit",
                speed=0.5,
                start_edge="south",
            ),
        ],
        sensors=[
            SensorSpec(
                id="blue-sensor",
                faction_id="blue",
                position=(30.0, 25.0),
                range=35.0,
                fov_degrees=180.0,
                heading_degrees=180.0,
                capacity=8,
                detection_probability=0.9,
                measurement_noise=0.2,
            )
        ],
        responses=[
            ResponseSpec(
                id="blue-response",
                faction_id="blue",
                position=(40.0, 25.0),
                engagement_range=20.0,
                capacity_per_step=4,
                effectiveness=response_effectiveness,
            )
        ],
        policy_bindings=[
            PolicyBindingSpec(
                id="red-movement",
                faction_id="red",
                role="movement",
                policy_id="direct",
                trainable=True,
                actor_group_ids=["red-group"],
            ),
            PolicyBindingSpec(
                id="blue-sensing",
                faction_id="blue",
                role="sensing",
                policy_id="sweep",
                trainable=True,
                sensor_ids=["blue-sensor"],
            ),
            PolicyBindingSpec(
                id="neutral-movement",
                faction_id="neutral",
                role="movement",
                policy_id="transit",
                actor_group_ids=["neutral-group"],
            ),
        ],
    )


def engagement_scenario(response_effectiveness: float) -> ScenarioSpec:
    scenario = tiny_scenario(response_effectiveness=response_effectiveness)
    groups = [
        scenario.actor_groups[0].model_copy(
            update={"speed": 5.0, "target_zone_id": "objective-close"}
        ),
        scenario.actor_groups[1],
    ]
    return scenario.model_copy(
        update={
            "protected_zones": [ZoneSpec(id="objective-close", center=(10.0, 25.0), radius=5.0)],
            "actor_groups": groups,
            "sensors": [
                scenario.sensors[0].model_copy(
                    update={
                        "range": 100.0,
                        "fov_degrees": 360.0,
                        "heading_degrees": 0.0,
                        "detection_probability": 1.0,
                        "measurement_noise": 0.0,
                    }
                )
            ],
            "responses": [
                scenario.responses[0].model_copy(
                    update={
                        "position": (10.0, 25.0),
                        "engagement_range": 100.0,
                        "capacity_per_step": 8,
                    }
                )
            ],
            "duration_seconds": 8.0,
        }
    )


def scripted_rollout(
    scenario: ScenarioSpec,
    *,
    overrides: dict[str, str] | None = None,
    seed: int | None = None,
    device: str = "cpu",
    record_frames: bool = True,
):
    env = BatchedScenarioEnv(scenario, seed=seed, device=device)
    return recorded_rollout(env, build_policies(env, overrides), record_frames=record_frames)


@pytest.mark.asyncio
async def test_distribution_and_api_versions_match(tmp_path: Path):
    assert __version__ == version("pytho-arena")
    scenario_asset = files("pytho_arena.scenario").joinpath(
        "library", "multi-faction-air-defense.json"
    )
    strait_sentinel_asset = files("pytho_arena.scenario").joinpath(
        "library", "strait-sentinel-airbase.json"
    )
    frontend_assets = files("pytho_arena.server").joinpath("frontend")
    assert scenario_asset.is_file()
    assert strait_sentinel_asset.is_file()
    assert frontend_assets.joinpath("index.html").is_file()
    assert frontend_assets.joinpath("app.js").is_file()
    assert frontend_assets.joinpath("styles.css").is_file()
    assert frontend_assets.joinpath("assets", "orion_ucav.obj").is_file()
    assert frontend_assets.joinpath("assets", "f_16c_block_50_lod2.obj").is_file()
    assert frontend_assets.joinpath("assets", "explosion_vfx.png").is_file()
    assert frontend_assets.joinpath("training.html").is_file()
    assert frontend_assets.joinpath("training.js").is_file()

    app = create_app(tmp_path / "version-data")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            index = await client.get("/")
            assert index.status_code == 200
            assert "Pytho Arena" in index.text
            frontend_script = await client.get("/static/app.js")
            assert frontend_script.status_code == 200
            frontend_model = await client.get("/static/assets/orion_ucav.obj")
            assert frontend_model.status_code == 200
            airbase_fighter = await client.get("/static/assets/f_16c_block_50_lod2.obj")
            assert airbase_fighter.status_code == 200

            health = await client.get("/api/health")
            assert health.status_code == 200
            assert health.json()["version"] == __version__

            scenarios = await client.get("/api/scenarios")
            assert scenarios.status_code == 200
            scenario_ids = {item["scenarioId"] for item in scenarios.json()["scenarios"]}
            assert "strait-sentinel-airbase" in scenario_ids


def test_scenario_rejects_geometry_outside_world():
    scenario = tiny_scenario()
    bad_sensor = scenario.sensors[0].model_copy(update={"position": (61.0, 10.0)})
    with pytest.raises(ValidationError, match="outside the world"):
        scenario.model_copy(update={"sensors": [bad_sensor]}).model_validate(
            {**scenario.model_dump(), "sensors": [bad_sensor.model_dump()]}
        )


def test_scenario_rejects_unknown_faction_reference():
    payload = tiny_scenario().model_dump(mode="json")
    payload["actor_groups"][0]["faction_id"] = "missing"
    with pytest.raises(ValidationError, match="unknown faction"):
        ScenarioSpec.model_validate(payload)


def test_scenario_rejects_unknown_evaluation_faction():
    payload = tiny_scenario().model_dump(mode="json")
    payload["evaluation_faction_id"] = "missing"
    with pytest.raises(ValidationError, match="evaluation_faction_id"):
        ScenarioSpec.model_validate(payload)


def test_every_actor_group_requires_one_policy_binding():
    payload = tiny_scenario().model_dump(mode="json")
    payload["policy_bindings"] = payload["policy_bindings"][1:]
    with pytest.raises(ValidationError, match="every actor group"):
        ScenarioSpec.model_validate(payload)


def test_registry_assigns_immutable_versions(tmp_path: Path):
    registry = ScenarioRegistry(tmp_path / "scenarios")
    first = registry.save(tiny_scenario())
    modified = tiny_scenario().model_copy(update={"name": "Second version"})
    second = registry.save(modified)
    assert first.scenario.version == 1
    assert second.scenario.version == 2
    assert registry.get("tiny-scenario", 1).scenario.name == "Tiny multi-faction scenario"
    assert registry.get("tiny-scenario").scenario.name == "Second version"


def test_batched_state_and_observations_are_partitioned_by_faction():
    env = BatchedScenarioEnv(tiny_scenario(), batch_size=3, device="cpu")
    policies = build_policies(env)
    observations = env.reset()
    output = env.step(compute_actions(policies, observations, env.step_index))
    assert env.positions.shape == (3, 6, 2)
    assert set(output.observations) == {"red", "blue", "neutral"}
    assert output.observations["blue"]["tracks"].shape == (3, 6, 2)
    assert output.observations["red"]["own_positions"].shape == (3, 4, 2)
    assert output.observations["neutral"]["own_positions"].shape == (3, 2, 2)
    assert "truth" not in output.observations["blue"]
    assert set(output.rewards) == {"red", "blue", "neutral"}
    assert all(reward.shape == (3,) for reward in output.rewards.values())


def test_step_requires_actions_for_every_binding():
    env = BatchedScenarioEnv(tiny_scenario(), device="cpu")
    policies = build_policies(env)
    observations = env.reset()
    actions = compute_actions(policies, observations, 0)
    del actions["blue-sensing"]
    with pytest.raises(ValueError, match="missing"):
        env.step(actions)


def test_replay_is_byte_for_byte_deterministic_on_same_device():
    scenario = tiny_scenario()
    overrides = {"red-movement": "probe", "blue-sensing": "sweep"}
    frames_a, metrics_a = scripted_rollout(scenario, overrides=overrides, seed=44)
    frames_b, metrics_b = scripted_rollout(scenario, overrides=overrides, seed=44)
    assert frames_a == frames_b
    assert metrics_a == metrics_b


def test_communication_disruption_validates_and_drops_delivered_reports_only():
    with pytest.raises(ValidationError):
        CommunicationsDisruption(drop_probability=1.01)

    connected = BatchedScenarioEnv(tiny_scenario(), device="cpu")
    connected.current_detections.fill_(True)
    connected._apply_communication_disruption()
    assert connected.delivered_detections.all()

    disrupted = BatchedScenarioEnv(
        tiny_scenario(),
        device="cpu",
        disruptions=[CommunicationsDisruption(drop_probability=1.0)],
    )
    disrupted.current_detections.fill_(True)
    disrupted._apply_communication_disruption()
    defending_sensors = disrupted.sensor_faction_indices == disrupted.evaluation_faction_index
    assert not disrupted.delivered_detections[:, defending_sensors, :].any()
    # Sensor truth is never masked: the analyst record keeps what sensors saw.
    assert disrupted.current_detections.all()


def test_communication_disruption_without_evaluator_hits_declaring_factions_only():
    base = tiny_scenario()
    neutral_sensor = SensorSpec(
        id="neutral-sensor",
        faction_id="neutral",
        position=(10.0, 10.0),
        range=20.0,
        fov_degrees=180.0,
        heading_degrees=0.0,
        capacity=4,
        detection_probability=0.9,
        measurement_noise=0.2,
    )
    neutral_sensing = PolicyBindingSpec(
        id="neutral-sensing",
        faction_id="neutral",
        role="sensing",
        policy_id="sweep",
        sensor_ids=["neutral-sensor"],
    )
    scenario = base.model_copy(
        update={
            "evaluation_faction_id": None,
            "sensors": [*base.sensors, neutral_sensor],
            "policy_bindings": [*base.policy_bindings, neutral_sensing],
        }
    )
    env = BatchedScenarioEnv(
        scenario,
        device="cpu",
        disruptions=[CommunicationsDisruption(drop_probability=1.0)],
    )
    env.current_detections.fill_(True)
    env._apply_communication_disruption()
    # blue declares opponent/protected relationships and is disrupted; the
    # neutral background faction declares none and keeps its reports.
    blue_sensors = env.sensor_faction_indices == env.faction_index["blue"]
    neutral_sensors = env.sensor_faction_indices == env.faction_index["neutral"]
    assert not env.delivered_detections[:, blue_sensors, :].any()
    assert env.delivered_detections[:, neutral_sensors, :].all()
    assert env.current_detections.all()


def test_disrupted_run_records_sensor_truth_while_the_network_stays_blind():
    env = BatchedScenarioEnv(
        tiny_scenario(),
        device="cpu",
        disruptions=[CommunicationsDisruption(drop_probability=1.0)],
    )
    frames, run_metrics = recorded_rollout(env, build_policies(env))
    truth_detected = any(entity["detected"] for f in frames for entity in f["truth"])
    delivered_reports = [report for f in frames for report in f["detections"]]
    assert truth_detected
    assert not delivered_reports
    assert run_metrics["detection_rate"] == 0.0
    assert run_metrics["defense_intercepts"] == 0


def test_disruption_info_counters_report_drops_and_launch_failures():
    dropped = BatchedScenarioEnv(
        tiny_scenario(),
        device="cpu",
        disruptions=[CommunicationsDisruption(drop_probability=1.0)],
    )
    dropped_total = 0
    for output in episode(dropped, build_policies(dropped)):
        dropped_total += int(output.info["dropped_report_count"].sum().item())
        assert int(output.info["launch_failure_count"].sum().item()) == 0
    assert dropped_total > 0

    unreliable = BatchedScenarioEnv(
        engagement_scenario(response_effectiveness=1.0),
        device="cpu",
        disruptions=[EffectorDisruption(reliability=0.0)],
    )
    failures = 0
    for output in episode(unreliable, build_policies(unreliable)):
        failures += int(output.info["launch_failure_count"].sum().item())
    assert failures > 0


def test_sensor_disruption_dims_truth_itself():
    baseline = BatchedScenarioEnv(tiny_scenario(), device="cpu")
    blinded = BatchedScenarioEnv(
        tiny_scenario(),
        device="cpu",
        disruptions=[SensorDisruption(detection_probability_multiplier=0.0)],
    )
    assert torch.equal(blinded.sensor_pd, torch.zeros_like(baseline.sensor_pd))
    frames, run_metrics = recorded_rollout(blinded, build_policies(blinded))
    # Unlike communications disruption, a blinded sensor records no truth.
    assert not any(entity["detected"] for f in frames for entity in f["truth"])
    assert run_metrics["detection_rate"] == 0.0

    halved = BatchedScenarioEnv(
        tiny_scenario(),
        device="cpu",
        disruptions=[SensorDisruption(range_multiplier=0.5, noise_multiplier=2.0)],
    )
    assert torch.allclose(halved.sensor_ranges, baseline.sensor_ranges * 0.5)
    assert torch.allclose(halved.sensor_noise, baseline.sensor_noise * 2.0)


def test_effector_disruption_stops_intercepts_and_inert_specs_change_nothing():
    scenario = engagement_scenario(response_effectiveness=1.0)

    baseline = BatchedScenarioEnv(scenario, device="cpu")
    baseline_frames, baseline_metrics = recorded_rollout(baseline, build_policies(baseline))
    assert baseline_metrics["defense_intercepts"] == 4

    for spec in (
        EffectorDisruption(effectiveness_multiplier=0.0),
        EffectorDisruption(reliability=0.0),
    ):
        env = BatchedScenarioEnv(scenario, device="cpu", disruptions=[spec])
        _, run_metrics = recorded_rollout(env, build_policies(env))
        assert run_metrics["defense_intercepts"] == 0, spec

    inert = BatchedScenarioEnv(
        scenario,
        device="cpu",
        disruptions=[EffectorDisruption(effectiveness_multiplier=1.0, reliability=1.0)],
    )
    inert_frames, inert_metrics = recorded_rollout(inert, build_policies(inert))
    assert inert_frames == baseline_frames
    assert inert_metrics == baseline_metrics


def test_disruption_faction_scoping_and_unknown_faction_rejection():
    # Scoping a comms outage to the non-defending red faction leaves the
    # defending blue sensor untouched.
    env = BatchedScenarioEnv(
        tiny_scenario(),
        device="cpu",
        disruptions=[CommunicationsDisruption(drop_probability=1.0, faction_ids=["red"])],
    )
    assert not env._communication_disruption_active

    with pytest.raises(ValueError, match="unknown factions"):
        BatchedScenarioEnv(
            tiny_scenario(),
            device="cpu",
            disruptions=[EffectorDisruption(reliability=0.5, faction_ids=["ghosts"])],
        )


def test_stacked_comms_specs_compound_per_sensor():
    env = BatchedScenarioEnv(
        tiny_scenario(),
        device="cpu",
        disruptions=[
            CommunicationsDisruption(drop_probability=0.5),
            CommunicationsDisruption(drop_probability=0.5),
        ],
    )
    blue_sensor = env.sensor_faction_indices == env.evaluation_faction_index
    assert torch.allclose(
        env.communication_drop_probability[blue_sensor],
        torch.tensor([0.75], device=env.device),
    )


def test_relationships_prevent_protected_neutral_interception():
    frames, metrics = scripted_rollout(engagement_scenario(response_effectiveness=1.0))
    assert metrics["defense_intercepts"] == 4
    assert metrics["attack_attempts"] == 0
    assert metrics["protected_intercepts"] == 0
    assert metrics["factions"]["neutral"]["intercepted"] == 0
    assert metrics["factions"]["neutral"]["active_at_end"] == 2
    assert any(entity["factionId"] == "neutral" for entity in frames[-1]["truth"])


def test_evaluation_opponents_do_not_depend_on_response_presence():
    scenario = tiny_scenario()
    blue_group = ActorGroupSpec(
        id="blue-group",
        faction_id="blue",
        count=1,
        mission="transit",
        speed=0.5,
        start_edge="east",
    )
    blue_binding = PolicyBindingSpec(
        id="blue-movement",
        faction_id="blue",
        role="movement",
        policy_id="transit",
        actor_group_ids=["blue-group"],
    )
    scenario = ScenarioSpec.model_validate(
        {
            **scenario.model_dump(mode="json"),
            "actor_groups": [
                *scenario.model_dump(mode="json")["actor_groups"],
                blue_group.model_dump(mode="json"),
            ],
            "policy_bindings": [
                *scenario.model_dump(mode="json")["policy_bindings"],
                blue_binding.model_dump(mode="json"),
            ],
        }
    )

    with_response = BatchedScenarioEnv(scenario, device="cpu")
    without_response = BatchedScenarioEnv(
        scenario.model_copy(update={"responses": []}), device="cpu"
    )
    assert torch.equal(with_response.opponent_entity_mask, without_response.opponent_entity_mask)
    opponent_factions = {
        faction_id
        for faction_id, is_opponent in zip(
            with_response.entity_faction_ids,
            with_response.opponent_entity_mask.tolist(),
            strict=True,
        )
        if is_opponent
    }
    assert opponent_factions == {"red"}


def test_entities_that_survive_response_attempt_objective_attack():
    frames, metrics = scripted_rollout(engagement_scenario(response_effectiveness=0.0))
    assert metrics["defense_intercepts"] == 0
    assert metrics["attack_attempts"] == 4
    assert metrics["attack_successes"] == 4
    assert metrics["factions"]["neutral"]["attack_attempts"] == 0
    assert any(frame["events"]["attacks"] for frame in frames)


def test_response_cannot_use_tracks_from_unrelated_faction():
    payload = engagement_scenario(response_effectiveness=1.0).model_dump(mode="json")
    payload["sensors"][0]["faction_id"] = "neutral"
    sensing_binding = next(
        binding for binding in payload["policy_bindings"] if binding["role"] == "sensing"
    )
    sensing_binding["id"] = "neutral-sensing"
    sensing_binding["faction_id"] = "neutral"
    scenario = ScenarioSpec.model_validate(payload)

    _, metrics = scripted_rollout(scenario)

    assert metrics["ever_detected"] == 0
    assert metrics["defense_intercepts"] == 0
    assert metrics["attack_attempts"] == 4


def slow_engagement_scenario() -> ScenarioSpec:
    """Engagement geometry where nothing reaches the objective within a few steps."""
    scenario = engagement_scenario(response_effectiveness=1.0)
    return scenario.model_copy(
        update={
            "actor_groups": [
                scenario.actor_groups[0].model_copy(update={"speed": 1.0}),
                scenario.actor_groups[1],
            ]
        }
    )


def authority_gated(scenario: ScenarioSpec, **effector: object) -> ScenarioSpec:
    return scenario.model_copy(
        update={
            "responses": [
                scenario.responses[0].model_copy(update={"effector": TypedEffectorSpec(**effector)})
            ]
        }
    )


def test_typed_effector_applies_no_effect_until_a_decision_authorizes_it():
    open_scenario = slow_engagement_scenario()
    _, open_metrics = scripted_rollout(open_scenario)
    _, gated_metrics = scripted_rollout(authority_gated(open_scenario, available_uses=4))

    assert open_metrics["defense_intercepts"] == 4
    assert gated_metrics["defense_intercepts"] == 0
    assert gated_metrics["ever_detected"] == open_metrics["ever_detected"]


def test_authorization_admits_only_the_named_entity_for_one_effects_tick():
    env = BatchedScenarioEnv(authority_gated(slow_engagement_scenario()), device="cpu")
    policies = build_policies(env, None)
    observations = env.reset()
    output = env.step(compute_actions(policies, observations, env.step_index))
    assert not env.intercepted.any()

    index = env.entity_indices_by_id
    red = [entity_id for entity_id in env.entity_ids if entity_id.startswith("red-group")]
    env.authorize_effect("blue-response", red[0])
    env.step(compute_actions(policies, output.observations, env.step_index))

    assert bool(env.intercepted[0, index[red[0]]])
    assert not any(bool(env.intercepted[0, index[entity_id]]) for entity_id in red[1:])
    assert not env.response_authorizations.any()


def test_absent_typed_effector_preserves_the_scenario_content_hash():
    base = slow_engagement_scenario()
    legacy_payload = base.model_dump(mode="json")
    for response in legacy_payload["responses"]:
        response.pop("effector")

    assert ScenarioSpec.model_validate(legacy_payload).content_hash() == base.content_hash()
    assert authority_gated(base).content_hash() != base.content_hash()


def test_authorize_effect_rejects_unknown_and_untyped_targets():
    untyped = BatchedScenarioEnv(slow_engagement_scenario(), device="cpu")
    with pytest.raises(ValueError, match="no typed effector"):
        untyped.authorize_effect("blue-response", "red-group-01")

    gated = BatchedScenarioEnv(authority_gated(slow_engagement_scenario()), device="cpu")
    with pytest.raises(ValueError, match="unknown response"):
        gated.authorize_effect("missing-response", "red-group-01")
    with pytest.raises(ValueError, match="unknown entity"):
        gated.authorize_effect("blue-response", "missing-entity")


def test_policy_registry_applies_overrides_keyed_by_binding_id():
    env = BatchedScenarioEnv(tiny_scenario(), device="cpu")
    policies = build_policies(
        env,
        {
            "red-movement": "coordinated",
            "blue-sensing": "track",
            "neutral-movement": "transit",
        },
    )
    assert policies["red-movement"].policy_id == "coordinated"
    assert policies["blue-sensing"].policy_id == "track"
    assert policies["red-movement"].faction_id == "red"


def test_unknown_policy_binding_override_is_rejected():
    env = BatchedScenarioEnv(tiny_scenario(), device="cpu")
    with pytest.raises(ValueError, match="unknown policy binding"):
        build_policies(env, {"missing-binding": "probe"})


def test_rewards_are_scenario_data():
    zeroed = tiny_scenario().model_copy(
        update={
            "rewards": RewardSpec(
                attack_success=0.0,
                intercepted=0.0,
                response_intercept=0.0,
                opponent_attack_success=0.0,
            )
        }
    )
    env = BatchedScenarioEnv(zeroed, device="cpu")
    policies = build_policies(env)
    for output in episode(env, policies):
        assert all(torch.all(reward == 0.0) for reward in output.rewards.values())


@pytest.mark.parametrize("movement_policy", ["transit", "direct", "probe", "coordinated"])
@pytest.mark.parametrize("sensing_policy", ["sweep", "track", "coverage"])
def test_policy_matrix_preserves_faction_and_outcome_invariants(movement_policy, sensing_policy):
    scenario = tiny_scenario()
    _, metrics = scripted_rollout(
        scenario,
        overrides={
            "red-movement": movement_policy,
            "blue-sensing": sensing_policy,
        },
        seed=31,
        record_frames=False,
    )

    for faction in scenario.factions:
        outcomes = metrics["factions"][faction.id]
        resolved_or_active = (
            outcomes["intercepted"] + outcomes["attack_attempts"] + outcomes["active_at_end"]
        )
        assert resolved_or_active == outcomes["entities"]
        assert outcomes["attack_successes"] <= outcomes["attack_attempts"]
        assert outcomes["ever_detected"] <= outcomes["entities"]
    assert metrics["protected_intercepts"] == 0
    assert 0.0 <= metrics["detection_rate"] <= 1.0
    assert 0.0 <= metrics["defense_rate"] <= 1.0


def test_content_hash_stable_under_absent_optional_fields():
    base = tiny_scenario()
    hashed_payload = base.model_dump(mode="json", exclude={"version"}, exclude_none=True)
    assert "name" not in hashed_payload["policy_bindings"][0]

    named = base.model_copy(
        update={
            "policy_bindings": [
                base.policy_bindings[0].model_copy(update={"name": "Red drone swarm"}),
                *base.policy_bindings[1:],
            ]
        }
    )
    assert named.content_hash() != base.content_hash()


def test_accelerator_selection_auto_returns_supported_device():
    env = BatchedScenarioEnv(tiny_scenario(), device="auto")
    expected = "cuda" if torch.cuda.is_available() else "mps" if mps_usable() else "cpu"
    assert env.device.type == expected


def test_stateless_rng_distinguishes_maximum_seeds_and_adjacent_steps():
    device = torch.device("cpu")
    highest = stateless_uniform((64,), 2_147_483_647, 0, 1, device=device)
    adjacent_seed = stateless_uniform((64,), 2_147_483_646, 0, 1, device=device)
    adjacent_step = stateless_uniform((64,), 2_147_483_647, 1, 1, device=device)
    repeated = stateless_uniform((64,), 2_147_483_647, 0, 1, device=device)

    assert not torch.equal(highest, adjacent_seed)
    assert not torch.equal(highest, adjacent_step)
    assert torch.equal(highest, repeated)
    assert ((0.0 <= highest) & (highest < 1.0)).all()


@pytest.mark.asyncio
async def test_api_save_run_and_replay(tmp_path: Path):
    app = create_app(tmp_path / "data")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            saved = await client.post(
                "/api/scenarios",
                json=tiny_scenario("api-scenario").model_dump(mode="json"),
            )
            assert saved.status_code == 201, saved.text
            record = saved.json()
            assert record["scenario"]["schema_version"] == "2.0"
            assert record["scenario"]["version"] == 1

            validation = await client.post("/api/scenarios/validate", json=record["scenario"])
            assert validation.status_code == 200
            assert validation.json()["factions"] == 3

            run = await client.post(
                "/api/runs",
                json={
                    "scenario_id": "api-scenario",
                    "scenario_version": 1,
                    "policy_overrides": {
                        "red-movement": "coordinated",
                        "blue-sensing": "track",
                    },
                    "seed": 99,
                    "device": "cpu",
                    "disruptions": [
                        {"kind": "sensor", "detection_probability_multiplier": 0.5},
                        {"kind": "effector", "reliability": 0.8},
                    ],
                },
            )
            assert run.status_code == 201, run.text
            summary = run.json()
            assert summary["steps"] == 6
            assert summary["scenario_version"] == 1
            assert summary["policies"]["red-movement"] == "coordinated"
            assert [spec["kind"] for spec in summary["disruptions"]] == ["sensor", "effector"]

            replay = await client.get(f"/api/runs/{summary['run_id']}/replay")
            assert replay.status_code == 200
            payload = replay.json()
            assert len(payload["frames"]) == 7
            assert payload["summary"]["seed"] == 99
            assert payload["summary"]["disruptions"][0]["kind"] == "sensor"
            assert any(entity["factionId"] == "neutral" for entity in payload["frames"][0]["truth"])
