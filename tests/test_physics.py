"""Physics-state and legacy-backend compatibility tests."""

from __future__ import annotations

import pytest
import torch

from pytho_arena import PhysicsState, register_physics_backend
from pytho_arena.core.env import BatchedScenarioEnv
from pytho_arena.env.rollout import compute_actions
from pytho_arena.policies import build_policies
from pytho_arena.simulation.physics import (
    Kinematic2DBackend,
    Multirotor6DOFBackend,
    PointMass3DBackend,
)

from .test_sim import tiny_scenario


def multirotor_state(
    positions: torch.Tensor | None = None,
    velocities: torch.Tensor | None = None,
) -> PhysicsState:
    positions = torch.tensor([[[50.0, 50.0, 20.0]]]) if positions is None else positions
    velocities = torch.zeros_like(positions) if velocities is None else velocities
    return PhysicsState.from_translation(positions, velocities)


def multirotor_inputs(entity_count: int = 1) -> dict[str, torch.Tensor | float | int]:
    return {
        "commands": torch.zeros((1, entity_count, 3)),
        "active": torch.ones((1, entity_count), dtype=torch.bool),
        "max_speeds": torch.full((1, entity_count, 1), 5.0),
        "max_accelerations": torch.full((1, entity_count, 1), 3.0),
        "bounds": torch.tensor([[[100.0, 100.0, 100.0]]]),
        "dt": 1.0,
        "substeps": 100,
        "meters_per_unit": 1.0,
    }


def test_physics_state_starts_with_identity_attitude_and_zero_angular_rate():
    positions = torch.zeros((2, 3, 2), dtype=torch.float32)
    state = PhysicsState.from_translation(positions, torch.zeros_like(positions))

    assert state.orientations.shape == (2, 3, 4)
    assert state.angular_velocities.shape == (2, 3, 3)
    assert torch.equal(state.orientations[..., 0], torch.ones((2, 3)))
    assert not state.orientations[..., 1:].any()
    assert not state.angular_velocities.any()


def test_physics_state_rejects_mismatched_translation_shapes():
    with pytest.raises(ValueError):
        PhysicsState.from_translation(torch.zeros((1, 2, 3)), torch.zeros((1, 2, 2)))


def test_physics_state_rejects_malformed_rotation_shape_and_dtype():
    with pytest.raises(ValueError, match="orientations"):
        PhysicsState(
            positions=torch.zeros((1, 2, 3)),
            velocities=torch.zeros((1, 2, 3)),
            orientations=torch.zeros((1, 2, 3)),
            angular_velocities=torch.zeros((1, 2, 3)),
        )
    with pytest.raises(ValueError, match="floating-point"):
        PhysicsState.from_translation(
            torch.zeros((1, 2, 3), dtype=torch.int64),
            torch.zeros((1, 2, 3), dtype=torch.int64),
        )


def test_registration_rejects_legacy_backend_before_first_step():
    class LegacyBackend:
        name = "legacy_without_state_api"
        spatial_dimensions = 3

    with pytest.raises(ValueError, match="API version 2"):
        register_physics_backend(LegacyBackend.name, LegacyBackend)


def test_kinematic_backend_preserves_rotation_and_legacy_translation():
    positions = torch.tensor([[[1.0, 1.0], [9.0, 9.0]]])
    state = PhysicsState.from_translation(positions, torch.zeros_like(positions))
    backend = Kinematic2DBackend()

    result = backend.advance(
        state,
        commands=torch.tensor([[[1.0, 0.0], [1.0, 1.0]]]),
        active=torch.tensor([[True, False]]),
        max_speeds=torch.tensor([[[2.0], [4.0]]]),
        max_accelerations=torch.ones((1, 2, 1)),
        bounds=torch.tensor([[[10.0, 10.0]]]),
        dt=2.0,
        substeps=4,
    )

    torch.testing.assert_close(result.positions, torch.tensor([[[5.0, 1.0], [9.0, 9.0]]]))
    torch.testing.assert_close(result.velocities, torch.tensor([[[2.0, 0.0], [0.0, 0.0]]]))
    assert torch.equal(result.orientations, state.orientations)
    assert torch.equal(result.angular_velocities, state.angular_velocities)


def test_point_mass_backend_is_repeatable_and_keeps_inactive_bodies_still():
    positions = torch.tensor([[[0.0, 0.0, 2.0], [4.0, 5.0, 6.0]]])
    state = PhysicsState.from_translation(positions, torch.zeros_like(positions))
    backend = PointMass3DBackend()
    inputs = {
        "commands": torch.tensor([[[1.0, 0.0, 0.0], [1.0, 1.0, 1.0]]]),
        "active": torch.tensor([[True, False]]),
        "max_speeds": torch.tensor([[[2.0], [2.0]]]),
        "max_accelerations": torch.tensor([[[1.0], [1.0]]]),
        "bounds": torch.tensor([[[10.0, 10.0, 10.0]]]),
        "dt": 1.0,
        "substeps": 2,
    }

    first = backend.advance(state, **inputs)
    second = backend.advance(state, **inputs)

    assert torch.equal(first.positions, second.positions)
    assert torch.equal(first.velocities, second.velocities)
    torch.testing.assert_close(first.positions[0, 0], torch.tensor([0.75, 0.0, 2.0]))
    assert torch.equal(first.positions[0, 1], positions[0, 1])
    assert not first.velocities[0, 1].any()
    assert torch.equal(first.orientations, state.orientations)
    assert torch.equal(first.angular_velocities, state.angular_velocities)


def test_multirotor_hover_holds_pose_and_unit_quaternion():
    state = multirotor_state()
    inputs = multirotor_inputs()
    inputs.update({"dt": 5.0, "substeps": 500})

    result = Multirotor6DOFBackend().advance(state, **inputs)

    torch.testing.assert_close(result.positions, state.positions, atol=0.02, rtol=0.0)
    assert torch.linalg.vector_norm(result.velocities, dim=-1).max().item() <= 0.02
    quaternion_norm = torch.linalg.vector_norm(result.orientations, dim=-1)
    torch.testing.assert_close(
        quaternion_norm, torch.ones_like(quaternion_norm), atol=1e-5, rtol=0.0
    )


def test_multirotor_tracks_horizontal_velocity_by_tilting():
    backend = Multirotor6DOFBackend()
    state = multirotor_state()
    inputs = multirotor_inputs()
    inputs["commands"][..., 0] = 1.0
    inputs.update({"dt": 0.1, "substeps": 10})

    initial_response = backend.advance(state, **inputs)
    assert not torch.equal(initial_response.orientations, state.orientations)
    assert initial_response.angular_velocities.abs().max().item() > 0.0

    inputs.update({"dt": 5.9, "substeps": 590})
    result = backend.advance(initial_response, **inputs)
    assert result.velocities[0, 0, 0].item() == pytest.approx(5.0, abs=0.25)
    assert abs(result.velocities[0, 0, 1].item()) < 0.15
    assert abs(result.positions[0, 0, 2].item() - 20.0) < 0.75
    assert torch.linalg.vector_norm(result.velocities, dim=-1).max().item() <= 5.0001
    assert torch.linalg.vector_norm(result.orientations, dim=-1).item() == pytest.approx(
        1.0, abs=1e-5
    )


def test_multirotor_fixed_ticks_are_repeatable_and_partition_invariant():
    backend = Multirotor6DOFBackend()
    state = multirotor_state()
    inputs = multirotor_inputs()
    inputs["commands"][..., :2] = torch.tensor((0.6, 0.8))

    first = backend.advance(state, **inputs)
    torch.manual_seed(923)
    second = backend.advance(state, **inputs)
    partitioned = state
    partition_inputs = {**inputs, "dt": 0.1, "substeps": 10}
    for _ in range(10):
        partitioned = backend.advance(partitioned, **partition_inputs)

    for field in ("positions", "velocities", "orientations", "angular_velocities"):
        assert torch.equal(getattr(first, field), getattr(second, field))
        torch.testing.assert_close(
            getattr(first, field), getattr(partitioned, field), atol=2e-6, rtol=0.0
        )


def test_multirotor_freezes_inactive_body_and_clears_outward_bound_velocity():
    positions = torch.tensor([[[20.0, 20.0, 20.0], [99.9, 50.0, 20.0]]])
    velocities = torch.tensor([[[2.0, 1.0, -1.0], [4.0, 0.0, 0.0]]])
    state = multirotor_state(positions, velocities)
    state.angular_velocities[0, 0] = torch.tensor((1.0, 2.0, 3.0))
    inputs = multirotor_inputs(entity_count=2)
    inputs["commands"][..., 0] = 1.0
    inputs["active"][0, 0] = False

    result = Multirotor6DOFBackend().advance(state, **inputs)

    assert torch.equal(result.positions[0, 0], state.positions[0, 0])
    assert torch.equal(result.orientations[0, 0], state.orientations[0, 0])
    assert not result.velocities[0, 0].any()
    assert not result.angular_velocities[0, 0].any()
    assert result.positions[0, 1, 0].item() == pytest.approx(100.0)
    assert result.velocities[0, 1, 0].item() == pytest.approx(0.0)


def test_multirotor_rejects_nonfinite_commands_before_advancing():
    inputs = multirotor_inputs()
    inputs["commands"][..., 0] = float("nan")

    with pytest.raises(ValueError, match="finite"):
        Multirotor6DOFBackend().advance(multirotor_state(), **inputs)


def test_environment_exposes_state_and_legacy_translation_aliases():
    env = BatchedScenarioEnv(tiny_scenario(), device="cpu")
    observations = env.reset()
    orientations_before = env.orientations.clone()

    env.step(compute_actions(build_policies(env), observations, 0))

    assert env.positions is env.physics_state.positions
    assert env.velocities is env.physics_state.velocities
    assert env.orientations is env.physics_state.orientations
    assert env.angular_velocities is env.physics_state.angular_velocities
    assert torch.equal(env.orientations, orientations_before)
    assert not env.angular_velocities.any()
