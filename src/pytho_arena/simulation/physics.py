"""Tensor physics backends behind one normalized-command interface."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import torch

PHYSICS_BACKEND_API_VERSION = 2


@dataclass
class PhysicsState:
    """Environment-owned batched pose and twist in scenario-local coordinates.

    Orientations are scalar-first ``[w, x, y, z]`` quaternions that rotate body
    vectors into the right-handed world frame. Angular velocities are body-frame
    radians per second. A force-based backend converts scenario units using the
    world's declared ``meters_per_unit`` value.
    """

    positions: torch.Tensor
    velocities: torch.Tensor
    orientations: torch.Tensor
    angular_velocities: torch.Tensor

    def __post_init__(self) -> None:
        if self.positions.ndim != 3 or self.positions.shape[-1] not in {2, 3}:
            raise ValueError("positions must have shape [batch, entity, 2|3]")
        if self.velocities.shape != self.positions.shape:
            raise ValueError("velocity shape must match positions")
        prefix = self.positions.shape[:-1]
        if self.orientations.shape != (*prefix, 4):
            raise ValueError("orientations must have shape [batch, entity, 4]")
        if self.angular_velocities.shape != (*prefix, 3):
            raise ValueError("angular velocities must have shape [batch, entity, 3]")
        tensors = (
            self.positions,
            self.velocities,
            self.orientations,
            self.angular_velocities,
        )
        if not all(value.is_floating_point() for value in tensors):
            raise ValueError("physics state tensors must use floating-point dtypes")
        if any(value.dtype != self.positions.dtype for value in tensors):
            raise ValueError("physics state tensors must use one dtype")
        if any(value.device != self.positions.device for value in tensors):
            raise ValueError("physics state tensors must use one device")

    @classmethod
    def from_translation(cls, positions: torch.Tensor, velocities: torch.Tensor) -> PhysicsState:
        if positions.shape != velocities.shape:
            raise ValueError("position and velocity shapes must match")
        orientations = positions.new_zeros((*positions.shape[:-1], 4))
        orientations[..., 0] = 1.0
        return cls(
            positions=positions,
            velocities=velocities,
            orientations=orientations,
            angular_velocities=positions.new_zeros((*positions.shape[:-1], 3)),
        )


class PhysicsBackend(Protocol):
    api_version: int
    name: str
    spatial_dimensions: int

    def advance(
        self,
        state: PhysicsState,
        commands: torch.Tensor,
        active: torch.Tensor,
        max_speeds: torch.Tensor,
        max_accelerations: torch.Tensor,
        bounds: torch.Tensor,
        *,
        dt: float,
        substeps: int,
        meters_per_unit: float = 1.0,
    ) -> PhysicsState: ...


def _clamp_norm(value: torch.Tensor, maximum: torch.Tensor) -> torch.Tensor:
    norm = torch.linalg.vector_norm(value, dim=-1, keepdim=True)
    return torch.where(norm > maximum, value * maximum / norm.clamp_min(1e-12), value)


def _quaternion_multiply(left: torch.Tensor, right: torch.Tensor) -> torch.Tensor:
    lw, lx, ly, lz = left.unbind(dim=-1)
    rw, rx, ry, rz = right.unbind(dim=-1)
    return torch.stack(
        (
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ),
        dim=-1,
    )


def _quaternion_rotate(quaternion: torch.Tensor, vector: torch.Tensor) -> torch.Tensor:
    scalar = quaternion[..., :1]
    xyz = quaternion[..., 1:]
    vector = vector.expand_as(xyz)
    cross = torch.cross(xyz, vector, dim=-1)
    return vector + 2.0 * (scalar * cross + torch.cross(xyz, cross, dim=-1))


@dataclass(frozen=True)
class Kinematic2DBackend:
    api_version: int = PHYSICS_BACKEND_API_VERSION
    name: str = "kinematic_2d"
    spatial_dimensions: int = 2

    def advance(
        self,
        state: PhysicsState,
        commands: torch.Tensor,
        active: torch.Tensor,
        max_speeds: torch.Tensor,
        max_accelerations: torch.Tensor,
        bounds: torch.Tensor,
        *,
        dt: float,
        substeps: int,
        meters_per_unit: float = 1.0,
    ) -> PhysicsState:
        del max_accelerations, meters_per_unit
        velocity = commands * max_speeds * active[..., None]
        next_positions = state.positions
        substep_dt = dt / substeps
        for _ in range(substeps):
            next_positions = next_positions + velocity * substep_dt
            next_positions = torch.minimum(
                torch.maximum(next_positions, torch.zeros_like(bounds)), bounds
            )
        return PhysicsState(
            positions=next_positions,
            velocities=velocity,
            orientations=state.orientations,
            angular_velocities=state.angular_velocities,
        )


@dataclass(frozen=True)
class PointMass3DBackend:
    """A bounded 3D point mass driven by desired normalized velocity commands."""

    api_version: int = PHYSICS_BACKEND_API_VERSION
    name: str = "point_mass_3d"
    spatial_dimensions: int = 3

    def advance(
        self,
        state: PhysicsState,
        commands: torch.Tensor,
        active: torch.Tensor,
        max_speeds: torch.Tensor,
        max_accelerations: torch.Tensor,
        bounds: torch.Tensor,
        *,
        dt: float,
        substeps: int,
        meters_per_unit: float = 1.0,
    ) -> PhysicsState:
        del meters_per_unit
        next_positions = state.positions
        velocity = state.velocities
        substep_dt = dt / substeps
        desired_velocity = commands * max_speeds
        for _ in range(substeps):
            delta = desired_velocity - velocity
            delta = _clamp_norm(delta, max_accelerations * substep_dt)
            velocity = _clamp_norm(velocity + delta, max_speeds)
            velocity = velocity * active[..., None]
            next_positions = next_positions + velocity * substep_dt
            next_positions = torch.minimum(
                torch.maximum(next_positions, torch.zeros_like(bounds)), bounds
            )
        return PhysicsState(
            positions=next_positions,
            velocities=velocity,
            orientations=state.orientations,
            angular_velocities=state.angular_velocities,
        )


@dataclass(frozen=True)
class Multirotor6DOFBackend:
    """Synthetic thrust-vectored rigid body with a desired-velocity autopilot."""

    api_version: int = PHYSICS_BACKEND_API_VERSION
    name: str = "multirotor_6dof"
    spatial_dimensions: int = 3
    mass_kg: float = 1.2
    inertia_kg_m2: tuple[float, float, float] = (0.02, 0.02, 0.04)
    gravity_mps2: float = 9.80665
    max_tilt_radians: float = math.radians(35.0)
    velocity_time_constant_seconds: float = 0.75
    attitude_natural_frequency: float = 6.0
    attitude_damping_ratio: float = 0.9
    max_linear_acceleration_mps2: float = 8.0
    max_thrust_acceleration_mps2: float = 21.57463
    max_torque_nm: float = 0.35
    max_angular_speed_rad_s: float = 8.0

    def advance(
        self,
        state: PhysicsState,
        commands: torch.Tensor,
        active: torch.Tensor,
        max_speeds: torch.Tensor,
        max_accelerations: torch.Tensor,
        bounds: torch.Tensor,
        *,
        dt: float,
        substeps: int,
        meters_per_unit: float = 1.0,
    ) -> PhysicsState:
        if state.positions.shape[-1] != 3:
            raise ValueError("multirotor_6dof requires three-dimensional state")
        if dt <= 0.0 or substeps < 1:
            raise ValueError("dt and substeps must be positive")
        if not math.isfinite(meters_per_unit) or meters_per_unit <= 0.0:
            raise ValueError("meters_per_unit must be positive and finite")
        prefix = state.positions.shape[:-1]
        if commands.shape != state.positions.shape or active.shape != prefix:
            raise ValueError("multirotor commands or active mask have invalid shapes")
        limit_tail = (prefix[1], 1)
        valid_speed_shape = (
            max_speeds.ndim == 3
            and max_speeds.shape[0] in {1, prefix[0]}
            and max_speeds.shape[1:] == limit_tail
        )
        valid_acceleration_shape = (
            max_accelerations.ndim == 3
            and max_accelerations.shape[0] in {1, prefix[0]}
            and max_accelerations.shape[1:] == limit_tail
        )
        limits_are_valid = valid_speed_shape and valid_acceleration_shape
        if not limits_are_valid:
            raise ValueError("multirotor limits have invalid shapes")
        if bounds.shape[-1] != 3:
            raise ValueError("multirotor bounds must have three dimensions")
        orientation_norm = torch.linalg.vector_norm(state.orientations, dim=-1, keepdim=True)
        finite = (
            torch.isfinite(state.positions).all()
            & torch.isfinite(state.velocities).all()
            & torch.isfinite(state.orientations).all()
            & torch.isfinite(state.angular_velocities).all()
            & torch.isfinite(commands).all()
            & (orientation_norm > 1e-9).all()
        )
        if not finite.item():
            raise ValueError("multirotor state and commands must be finite and valid")

        step_seconds = dt / substeps
        scale = meters_per_unit
        position = state.positions
        velocity = state.velocities
        orientation = state.orientations / orientation_norm
        angular_velocity = state.angular_velocities
        active_mask = active[..., None]
        desired_velocity_mps = commands * max_speeds * scale
        declared_acceleration_mps2 = max_accelerations * scale
        physical_acceleration_limit = state.positions.new_tensor(self.max_linear_acceleration_mps2)
        acceleration_limit = torch.minimum(declared_acceleration_mps2, physical_acceleration_limit)
        inertia = state.positions.new_tensor(self.inertia_kg_m2)
        max_torque = state.positions.new_tensor(self.max_torque_nm)
        max_thrust_acceleration = state.positions.new_tensor(self.max_thrust_acceleration_mps2)
        max_angular_speed = state.positions.new_tensor(self.max_angular_speed_rad_s)
        body_forward = state.positions.new_tensor((1.0, 0.0, 0.0))
        body_up = state.positions.new_tensor((0.0, 0.0, 1.0))

        for _ in range(substeps):
            velocity_mps = velocity * scale
            commanded_acceleration = _clamp_norm(
                (desired_velocity_mps - velocity_mps) / self.velocity_time_constant_seconds,
                acceleration_limit,
            )
            desired_thrust_acceleration = commanded_acceleration.clone()
            desired_thrust_acceleration[..., 2] += self.gravity_mps2
            vertical = desired_thrust_acceleration[..., 2:3].clamp_min(0.0)
            horizontal = desired_thrust_acceleration[..., :2]
            horizontal = _clamp_norm(
                horizontal,
                vertical * math.tan(self.max_tilt_radians),
            )
            desired_thrust_acceleration = torch.cat((horizontal, vertical), dim=-1)
            desired_thrust_acceleration = _clamp_norm(
                desired_thrust_acceleration, max_thrust_acceleration
            )
            thrust_acceleration = torch.linalg.vector_norm(
                desired_thrust_acceleration, dim=-1, keepdim=True
            )

            current_up = _quaternion_rotate(orientation, body_up)
            desired_up = torch.where(
                thrust_acceleration > 1e-9,
                desired_thrust_acceleration / thrust_acceleration.clamp_min(1e-9),
                current_up,
            )
            tilt_error_world = torch.cross(current_up, desired_up, dim=-1)
            conjugate = torch.cat((orientation[..., :1], -orientation[..., 1:]), dim=-1)
            attitude_error = _quaternion_rotate(conjugate, tilt_error_world)

            current_forward = _quaternion_rotate(orientation, body_forward)
            current_heading = current_forward[..., :2]
            current_heading = current_heading / torch.linalg.vector_norm(
                current_heading, dim=-1, keepdim=True
            ).clamp_min(1e-9)
            desired_heading = desired_velocity_mps[..., :2]
            desired_heading_norm = torch.linalg.vector_norm(desired_heading, dim=-1, keepdim=True)
            desired_heading = desired_heading / desired_heading_norm.clamp_min(1e-9)
            yaw_cross = (
                current_heading[..., :1] * desired_heading[..., 1:2]
                - current_heading[..., 1:2] * desired_heading[..., :1]
            )
            yaw_dot = (current_heading * desired_heading).sum(dim=-1, keepdim=True)
            yaw_error = torch.where(
                desired_heading_norm > 0.25,
                torch.atan2(yaw_cross, yaw_dot.clamp(-1.0, 1.0)),
                torch.zeros_like(yaw_cross),
            )
            attitude_error = attitude_error.clone()
            attitude_error[..., 2:3] += yaw_error

            angular_acceleration_command = (
                self.attitude_natural_frequency**2 * attitude_error
                - 2.0
                * self.attitude_damping_ratio
                * self.attitude_natural_frequency
                * angular_velocity
            )
            gyroscopic_torque = torch.cross(angular_velocity, inertia * angular_velocity, dim=-1)
            torque = inertia * angular_acceleration_command + gyroscopic_torque
            torque = _clamp_norm(torque, max_torque)
            angular_acceleration = (torque - gyroscopic_torque) / inertia
            next_angular_velocity = angular_velocity + angular_acceleration * step_seconds
            next_angular_velocity = _clamp_norm(next_angular_velocity, max_angular_speed)

            angular_quaternion = torch.cat(
                (torch.zeros_like(next_angular_velocity[..., :1]), next_angular_velocity),
                dim=-1,
            )
            next_orientation = orientation + (
                0.5 * _quaternion_multiply(orientation, angular_quaternion) * step_seconds
            )
            next_orientation = next_orientation / torch.linalg.vector_norm(
                next_orientation, dim=-1, keepdim=True
            ).clamp_min(1e-12)

            thrust_force_newtons = self.mass_kg * thrust_acceleration
            acceleration_mps2 = current_up * (thrust_force_newtons / self.mass_kg)
            acceleration_mps2[..., 2] -= self.gravity_mps2
            next_velocity = velocity + acceleration_mps2 * (step_seconds / scale)
            next_velocity = _clamp_norm(next_velocity, max_speeds)
            unclamped_position = position + next_velocity * step_seconds
            outward = ((unclamped_position < 0.0) & (next_velocity < 0.0)) | (
                (unclamped_position > bounds) & (next_velocity > 0.0)
            )
            next_velocity = torch.where(outward, torch.zeros_like(next_velocity), next_velocity)
            next_position = torch.minimum(
                torch.maximum(unclamped_position, torch.zeros_like(bounds)), bounds
            )

            position = torch.where(active_mask, next_position, position)
            orientation = torch.where(active_mask, next_orientation, orientation)
            velocity = torch.where(active_mask, next_velocity, torch.zeros_like(velocity))
            angular_velocity = torch.where(
                active_mask,
                next_angular_velocity,
                torch.zeros_like(angular_velocity),
            )

        return PhysicsState(
            positions=position,
            velocities=velocity,
            orientations=orientation,
            angular_velocities=angular_velocity,
        )


PhysicsFactory = Callable[[], PhysicsBackend]
_PHYSICS_BACKENDS: dict[str, PhysicsFactory] = {
    "kinematic_2d": Kinematic2DBackend,
    "multirotor_6dof": Multirotor6DOFBackend,
    "point_mass_3d": PointMass3DBackend,
}


def register_physics_backend(name: str, factory: PhysicsFactory) -> None:
    """Register an external or domain-specific backend before scenario compilation."""
    if not name or name in _PHYSICS_BACKENDS:
        raise ValueError(f"physics backend {name!r} is already registered or invalid")
    backend = factory()
    if getattr(backend, "api_version", None) != PHYSICS_BACKEND_API_VERSION:
        raise ValueError(
            f"physics backend {name!r} must implement API version {PHYSICS_BACKEND_API_VERSION}"
        )
    if backend.name != name or backend.spatial_dimensions not in {2, 3}:
        raise ValueError("physics backend factory does not match its registration")
    _PHYSICS_BACKENDS[name] = factory


def available_physics_backends() -> tuple[str, ...]:
    return tuple(sorted(_PHYSICS_BACKENDS))


def physics_backend(name: str) -> PhysicsBackend:
    try:
        return _PHYSICS_BACKENDS[name]()
    except KeyError as exc:
        raise ValueError(f"unknown physics backend: {name}") from exc
