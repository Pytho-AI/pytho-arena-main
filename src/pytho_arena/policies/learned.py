"""Learned policies: shared feature encoders, actor networks, and inference.

A learned policy sees exactly what a scripted policy sees — its faction's
observation dict — and emits the same normalized commands, so the engine's
actuator stage applies identical capability limits to both. The trainer
optimizes the networks defined here; at inference the wrappers act
deterministically (distribution mean) under ``torch.no_grad()``.
"""

from __future__ import annotations

import math

import torch
from torch import nn

from ..core.env import BatchedScenarioEnv
from ..scenario.models import PolicyBindingSpec

MOVEMENT_FEATURES = 8  # 2D default; generalized encoders derive dimensions at runtime.
SENSING_FEATURES = 9
HIDDEN_UNITS = 64
LEARNED_POLICY_ID = "learned"


class FeatureContext:
    """Static per-binding context needed to turn observations into features."""

    def __init__(
        self,
        *,
        world_width: float,
        world_height: float,
        vertical_extent: float,
        spatial_dimensions: int,
        steps: int,
        own_slots: torch.Tensor | None = None,
    ) -> None:
        self.world_width = world_width
        self.world_height = world_height
        self.vertical_extent = vertical_extent
        self.spatial_dimensions = spatial_dimensions
        self.extents = (world_width, world_height, vertical_extent)[:spatial_dimensions]
        self.scale = max(self.extents)
        self.steps = max(steps, 1)
        self.own_slots = own_slots

    @classmethod
    def for_binding(cls, env: BatchedScenarioEnv, binding: PolicyBindingSpec) -> FeatureContext:
        faction_number = env.faction_index[binding.faction_id]
        if binding.role == "movement":
            indices = env.movement_binding_entities[binding.id]
            owned = env.faction_entity_indices[faction_number]
        else:
            indices = env.sensing_binding_sensors[binding.id]
            owned = torch.nonzero(
                env.sensor_faction_indices == faction_number, as_tuple=False
            ).flatten()
        return cls(
            world_width=env.scenario.world.width,
            world_height=env.scenario.world.height,
            vertical_extent=env.scenario.world.vertical_extent,
            spatial_dimensions=env.spatial_dimensions,
            steps=env.steps,
            own_slots=torch.searchsorted(owned, indices),
        )


def _shared_features(
    observation: dict[str, torch.Tensor],
    positions: torch.Tensor,
    context: FeatureContext,
    step: int,
) -> list[torch.Tensor]:
    """Features every controlled unit sees: detection picture and time."""
    batch, units = positions.shape[0], positions.shape[1]
    centroid = observation["last_detection_centroid"][:, None, :].expand(batch, units, 2)
    has_detection = observation["has_last_detection"].to(positions.dtype)
    detected_fraction = observation["track_mask"].to(positions.dtype).mean(dim=1)
    return [
        (centroid - positions) / context.scale,
        has_detection[:, None, None].expand(batch, units, 1),
        detected_fraction[:, None, None].expand(batch, units, 1),
        torch.full_like(positions[..., :1], step / context.steps),
    ]


def movement_features(
    observation: dict[str, torch.Tensor], context: FeatureContext, step: int
) -> torch.Tensor:
    """Per-entity features ``[batch, k, MOVEMENT_FEATURES]`` for one movement binding."""
    positions = observation["own_positions"][:, context.own_slots, :]
    active = observation["own_active"][:, context.own_slots].to(positions.dtype)
    normalized = positions / torch.tensor(
        context.extents,
        device=positions.device,
        dtype=positions.dtype,
    )
    parts = [normalized * 2.0 - 1.0, active[..., None]]
    parts.extend(_shared_features(observation, positions, context, step))
    return torch.cat(parts, dim=-1)


def sensing_features(
    observation: dict[str, torch.Tensor], context: FeatureContext, step: int
) -> torch.Tensor:
    """Per-sensor features ``[batch, m, SENSING_FEATURES]`` for one sensing binding."""
    positions = observation["sensor_positions"][:, context.own_slots, :]
    headings = observation["sensor_headings"][:, context.own_slots]
    normalized = positions / torch.tensor(
        context.extents,
        device=positions.device,
        dtype=positions.dtype,
    )
    parts = [
        normalized * 2.0 - 1.0,
        torch.sin(headings)[..., None],
        torch.cos(headings)[..., None],
    ]
    parts.extend(_shared_features(observation, positions, context, step))
    return torch.cat(parts, dim=-1)


def _mlp(input_dim: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Linear(input_dim, HIDDEN_UNITS),
        nn.Tanh(),
        nn.Linear(HIDDEN_UNITS, HIDDEN_UNITS),
        nn.Tanh(),
        nn.Linear(HIDDEN_UNITS, 2),
    )


class MovementActor(nn.Module):
    """Maps per-entity features to a Gaussian over unit-ball direction commands."""

    def __init__(self, spatial_dimensions: int = 2) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(2 * spatial_dimensions + 4, HIDDEN_UNITS),
            nn.Tanh(),
            nn.Linear(HIDDEN_UNITS, HIDDEN_UNITS),
            nn.Tanh(),
            nn.Linear(HIDDEN_UNITS, spatial_dimensions),
        )
        self.log_std = nn.Parameter(torch.full((spatial_dimensions,), math.log(0.35)))

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return torch.tanh(self.body(features))

    def distribution(self, features: torch.Tensor) -> torch.distributions.Normal:
        mean = self(features)
        return torch.distributions.Normal(mean, self.log_std.exp().expand_as(mean))

    def deterministic(self, features: torch.Tensor) -> torch.Tensor:
        mean = self(features)
        norm = torch.linalg.vector_norm(mean, dim=-1, keepdim=True)
        return mean / norm.clamp_min(1.0)


class SensingActor(nn.Module):
    """Maps per-sensor features to a Gaussian over desired absolute headings."""

    def __init__(self, spatial_dimensions: int = 2) -> None:
        super().__init__()
        self.body = _mlp(2 * spatial_dimensions + 5)
        self.log_std = nn.Parameter(torch.tensor(math.log(0.4)))

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        vector = self.body(features)
        return torch.atan2(vector[..., 1], vector[..., 0])

    def distribution(self, features: torch.Tensor) -> torch.distributions.Normal:
        mean = self(features)
        return torch.distributions.Normal(mean, self.log_std.exp().expand_as(mean))

    def deterministic(self, features: torch.Tensor) -> torch.Tensor:
        return self(features)


def build_actor(role: str, spatial_dimensions: int = 2) -> nn.Module:
    return (
        MovementActor(spatial_dimensions)
        if role == "movement"
        else SensingActor(spatial_dimensions)
    )


class LearnedPolicy:
    """Inference-time Policy for one binding: deterministic actor mean, no grads."""

    def __init__(
        self,
        binding_id: str,
        faction_id: str,
        role: str,
        actor: nn.Module,
        context: FeatureContext,
        *,
        policy_id: str = LEARNED_POLICY_ID,
    ) -> None:
        self.binding_id = binding_id
        self.faction_id = faction_id
        self.role = role
        self.policy_id = policy_id
        self.actor = actor
        self.context = context
        self.actor.eval()

    def act(self, observation: dict[str, torch.Tensor], step: int) -> torch.Tensor:
        encode = movement_features if self.role == "movement" else sensing_features
        with torch.no_grad():
            return self.actor.deterministic(encode(observation, self.context, step))


def learned_policy_from_state(
    env: BatchedScenarioEnv,
    binding: PolicyBindingSpec,
    state_dict: dict[str, torch.Tensor],
    *,
    policy_id: str = LEARNED_POLICY_ID,
) -> LearnedPolicy:
    """Rebuild an inference policy for one binding from a checkpoint state dict."""
    actor = build_actor(binding.role, env.spatial_dimensions)
    actor.load_state_dict(state_dict)
    actor.to(env.device)
    return LearnedPolicy(
        binding.id,
        binding.faction_id,
        binding.role,
        actor,
        FeatureContext.for_binding(env, binding),
        policy_id=policy_id,
    )
