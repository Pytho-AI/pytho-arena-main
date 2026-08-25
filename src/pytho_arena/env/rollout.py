"""The one loop both wargaming and training drive: observe, act, step."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

import torch

from ..core.env import BatchedScenarioEnv, StepOutput
from ..policies.base import Policy


def compute_actions(
    policies: Mapping[str, Policy],
    observations: dict[str, dict[str, torch.Tensor]],
    step: int,
) -> dict[str, torch.Tensor]:
    """Ask each binding's policy for an action given its faction's observation."""
    return {
        binding_id: policy.act(observations[policy.faction_id], step)
        for binding_id, policy in policies.items()
    }


def episode(env: BatchedScenarioEnv, policies: Mapping[str, Policy]) -> Iterator[StepOutput]:
    """Reset the environment and yield one StepOutput per step until termination."""
    observations = env.reset()
    while env.step_index < env.steps:
        output = env.step(compute_actions(policies, observations, env.step_index))
        observations = output.observations
        yield output
