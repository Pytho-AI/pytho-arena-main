"""Shared environment and binding setup for all training algorithms."""

from __future__ import annotations

from dataclasses import dataclass

from ..env.adapters import ParallelArenaEnv
from ..policies.base import Policy
from ..policies.registry import build_policies
from ..scenario.models import PolicyBindingSpec, ScenarioSpec
from .contracts import TrainingConfig


@dataclass(frozen=True)
class TrainingSession:
    """Validated simulator resources supplied to an algorithm backend."""

    arena: ParallelArenaEnv
    trainable_ids: list[str]
    bindings: dict[str, PolicyBindingSpec]
    scripted_policies: dict[str, Policy]

    @classmethod
    def create(
        cls,
        scenario: ScenarioSpec,
        config: TrainingConfig,
        *,
        scenario_hash: str | None = None,
    ) -> TrainingSession:
        arena = ParallelArenaEnv(
            scenario,
            batch_size=config.batch_size,
            seed=config.seed,
            device=config.device,
            scenario_hash=scenario_hash,
            disruptions=config.disruptions,
        )
        trainable = arena.trainable_agents if config.binding_ids is None else config.binding_ids
        if not trainable:
            raise ValueError("scenario has no trainable policy bindings")
        unknown = sorted(set(trainable) - set(arena.agents))
        if unknown:
            raise ValueError(f"unknown trainable binding ids: {unknown}")
        fixed = sorted(set(trainable) - set(arena.trainable_agents))
        if fixed:
            raise ValueError(f"bindings are not marked trainable: {fixed}")
        return cls(
            arena=arena,
            trainable_ids=list(trainable),
            bindings={binding.id: binding for binding in scenario.policy_bindings},
            scripted_policies=build_policies(arena.env),
        )
