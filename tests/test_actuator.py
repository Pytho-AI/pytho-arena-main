"""Physics invariants: no action, however adversarial, exceeds declared capabilities.

The golden fixture guards determinism ("same inputs, same world"); these tests
guard the actuator contract ("no inputs break the world").
"""

from __future__ import annotations

import math

import pytest
import torch

from pytho_arena.core.env import BatchedScenarioEnv
from pytho_arena.env.rollout import compute_actions
from pytho_arena.policies import build_policies
from tests.test_sim import tiny_scenario


def make_env(scenario=None, **kwargs):
    env = BatchedScenarioEnv(scenario or tiny_scenario(), device="cpu", **kwargs)
    env.reset()
    return env


def scripted_actions(env):
    return compute_actions(build_policies(env), env._observations(), env.step_index)


def test_oversized_movement_command_is_projected_to_declared_speed():
    env = make_env()
    red_idx = env.movement_binding_entities["red-movement"]
    positions_before = env.positions[:, red_idx, :].clone()
    speed = env.scenario.actor_groups[0].speed

    actions = scripted_actions(env)
    actions["red-movement"] = actions["red-movement"] * 1_000.0
    output = env.step(actions)

    moved = (env.positions[:, red_idx, :] - positions_before).norm(dim=-1)
    assert moved.max().item() <= speed * env.dt * (1.0 + 1e-6)
    assert output.info["movement_saturation_count"].item() == red_idx.numel()


def test_slightly_oversized_movement_command_is_projected_and_counted():
    env = make_env()
    red_idx = env.movement_binding_entities["red-movement"]
    positions_before = env.positions[:, red_idx, :].clone()
    speed = env.scenario.actor_groups[0].speed

    actions = scripted_actions(env)
    actions["red-movement"] = torch.zeros_like(actions["red-movement"])
    actions["red-movement"][..., 0] = 1.00005
    output = env.step(actions)

    moved = (env.positions[:, red_idx, :] - positions_before).norm(dim=-1)
    assert moved.max().item() <= speed * env.dt * (1.0 + 1e-6)
    assert output.info["movement_saturation_count"].item() == red_idx.numel()


def test_in_bounds_commands_do_not_count_as_saturated():
    env = make_env()
    output = env.step(scripted_actions(env))
    assert output.info["movement_saturation_count"].item() == 0
    assert output.info["sensing_saturation_count"].item() == 0


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_actions_are_rejected(bad_value):
    env = make_env()
    actions = scripted_actions(env)
    headings_before = env.sensor_headings.clone()
    actions["blue-sensing"] = headings_before + 1.0
    actions["red-movement"] = torch.full_like(actions["red-movement"], bad_value)
    with pytest.raises(ValueError, match="non-finite"):
        env.step(actions)
    assert torch.isfinite(env.positions).all()
    assert torch.equal(env.sensor_headings, headings_before)
    assert env.step_index == 0


def test_mis_shaped_action_is_rejected():
    env = make_env()
    actions = scripted_actions(env)
    actions["blue-sensing"] = actions["blue-sensing"][..., None]
    with pytest.raises(ValueError, match="shape"):
        env.step(actions)


def test_sensor_slew_rate_limits_heading_change():
    scenario = tiny_scenario()
    slew_dps = 10.0
    scenario = scenario.model_copy(
        update={
            "sensors": [scenario.sensors[0].model_copy(update={"slew_rate_dps": slew_dps})],
        }
    )
    env = make_env(scenario)
    heading_before = env.sensor_headings.clone()
    limit = math.radians(slew_dps) * env.dt

    actions = scripted_actions(env)
    actions["blue-sensing"] = heading_before + math.pi  # demand an instant 180° slew
    output = env.step(actions)

    turned = (env.sensor_headings - heading_before).abs()
    assert turned.max().item() <= limit * (1.0 + 1e-5)
    assert output.info["sensing_saturation_count"].item() == 1


def test_unlimited_slew_assigns_heading_exactly():
    env = make_env()
    desired = torch.full_like(env.sensor_headings, 12.34)
    actions = scripted_actions(env)
    actions["blue-sensing"] = desired
    env.step(actions)
    assert torch.equal(env.sensor_headings, desired)


def test_random_adversarial_rollout_never_exceeds_capabilities():
    env = make_env()
    speeds = env.entity_speeds.squeeze(-1)
    generator = torch.Generator().manual_seed(0)
    while env.step_index < env.steps:
        positions_before = env.positions.clone()
        actions = {}
        for binding_id, idx in env.movement_binding_entities.items():
            actions[binding_id] = (
                torch.randn((env.batch_size, idx.numel(), 2), generator=generator) * 50.0
            )
        for binding_id, idx in env.sensing_binding_sensors.items():
            actions[binding_id] = (
                torch.randn((env.batch_size, idx.numel()), generator=generator) * 100.0
            )
        env.step(actions)
        moved = (env.positions - positions_before).norm(dim=-1)
        assert (moved <= speeds * env.dt * (1.0 + 1e-3)).all()
        assert torch.isfinite(env.positions).all()
