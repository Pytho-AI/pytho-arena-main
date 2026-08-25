"""Resolve scenario policy bindings to executable Policy objects.

The registry is the single mechanism both the wargaming server and the trainer
use: a binding id maps to a scripted baseline, or to a trained checkpoint via
a ``checkpoint:<checkpoint_id>`` policy id, without changing scenario identity
or run evidence. Checkpoint loading itself lives in the training layer; the
registry only accepts a loader callable so the dependency direction holds.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import get_args

import torch

from ..core.env import BatchedScenarioEnv
from ..scenario.models import MovementPolicy, PolicyBindingSpec, ScenarioSpec, SensingPolicy
from .base import Policy
from .scripted import ScriptedMovementPolicy, ScriptedSensingPolicy

SCRIPTED_MOVEMENT_POLICIES = get_args(MovementPolicy)
SCRIPTED_SENSING_POLICIES = get_args(SensingPolicy)
CHECKPOINT_PREFIX = "checkpoint:"

CheckpointLoader = Callable[[BatchedScenarioEnv, PolicyBindingSpec, str], Policy]


def resolve_policy_ids(
    scenario: ScenarioSpec, overrides: dict[str, str] | None = None
) -> dict[str, str]:
    """Apply overrides to the scenario's bindings and validate every policy id."""
    overrides = overrides or {}
    bindings = {binding.id: binding for binding in scenario.policy_bindings}
    unknown = set(overrides) - set(bindings)
    if unknown:
        raise ValueError(f"unknown policy binding overrides: {sorted(unknown)}")

    resolved: dict[str, str] = {}
    for binding_id, binding in bindings.items():
        policy_id = overrides.get(binding_id, binding.policy_id)
        allowed = (
            SCRIPTED_MOVEMENT_POLICIES if binding.role == "movement" else SCRIPTED_SENSING_POLICIES
        )
        if policy_id not in allowed and not policy_id.startswith(CHECKPOINT_PREFIX):
            raise ValueError(
                f"policy {policy_id!r} cannot execute binding {binding_id!r} "
                "in the baseline runtime"
            )
        resolved[binding_id] = policy_id
    return resolved


def build_policies(
    env: BatchedScenarioEnv,
    overrides: dict[str, str] | None = None,
    *,
    checkpoint_loader: CheckpointLoader | None = None,
) -> dict[str, Policy]:
    """Build one Policy per binding for a compiled environment."""
    resolved = resolve_policy_ids(env.scenario, overrides)
    policies: dict[str, Policy] = {}
    for binding in env.scenario.policy_bindings:
        policy_id = resolved[binding.id]
        if policy_id.startswith(CHECKPOINT_PREFIX):
            if checkpoint_loader is None:
                raise ValueError(
                    f"binding {binding.id!r} requests {policy_id!r} but no "
                    "checkpoint loader is available in this runtime"
                )
            policies[binding.id] = checkpoint_loader(
                env, binding, policy_id[len(CHECKPOINT_PREFIX) :]
            )
            continue
        if binding.role == "movement":
            indices = env.movement_binding_entities[binding.id]
            faction_entities = env.faction_entity_indices[env.faction_index[binding.faction_id]]
            policies[binding.id] = ScriptedMovementPolicy(
                binding.id,
                binding.faction_id,
                policy_id,
                own_slots=torch.searchsorted(faction_entities, indices),
                entity_phase=indices.to(env.dtype)[None, :, None],
                targets=env.entity_targets[:, indices, :],
                transit_directions=env.transit_directions[:, indices, :],
            )
        else:
            indices = env.sensing_binding_sensors[binding.id]
            spread = indices.to(env.dtype) * (2.0 * math.pi / max(env.sensor_count, 1))
            policies[binding.id] = ScriptedSensingPolicy(
                binding.id,
                binding.faction_id,
                policy_id,
                initial_headings=env.initial_headings[:, indices],
                sensor_positions=env.sensor_positions[:, indices, :],
                coverage_spread=spread[None, :],
            )
    return policies
