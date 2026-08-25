"""Multi-agent environment adapter in the PettingZoo parallel-API style.

Agents are policy bindings. Each agent observes its faction's observation dict
and receives its faction's reward. No PettingZoo dependency is required; the
adapter duck-types the parallel contract so trainers can wrap it directly.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import torch

from ..core.env import BatchedScenarioEnv
from ..scenario.models import ScenarioSpec


class ParallelArenaEnv:
    """PettingZoo-parallel-style view over :class:`BatchedScenarioEnv`.

    ``reset()`` returns ``(observations, infos)`` and ``step(actions)`` returns
    ``(observations, rewards, terminations, truncations, infos)``, all keyed by
    agent (binding) id. Action tensors follow the engine's command contract:
    unit-ball direction vectors ``[batch, k, D]`` for movement agents, desired
    headings ``[batch, k]`` for sensing agents; the engine projects commands
    onto declared capabilities (speed, slew rate).
    """

    def __init__(
        self,
        scenario: ScenarioSpec,
        *,
        batch_size: int = 1,
        seed: int | None = None,
        device: str = "auto",
        scenario_hash: str | None = None,
        disruptions: Iterable[object] | None = None,
    ) -> None:
        self.env = BatchedScenarioEnv(
            scenario,
            batch_size=batch_size,
            seed=seed,
            device=device,
            scenario_hash=scenario_hash,
            disruptions=disruptions,
        )
        self.agents = [binding.id for binding in scenario.policy_bindings]
        self.agent_factions = {
            binding.id: binding.faction_id for binding in scenario.policy_bindings
        }
        self.trainable_agents = [
            binding.id for binding in scenario.policy_bindings if binding.trainable
        ]

    def _agent_view(
        self, faction_values: dict[str, dict[str, torch.Tensor] | torch.Tensor]
    ) -> dict[str, dict[str, torch.Tensor] | torch.Tensor]:
        return {agent: faction_values[faction] for agent, faction in self.agent_factions.items()}

    def reset(self) -> tuple[dict, dict]:
        observations = self.env.reset()
        return self._agent_view(observations), {agent: {} for agent in self.agents}

    def step(self, actions: Mapping[str, torch.Tensor]) -> tuple[dict, dict, dict, dict, dict]:
        output = self.env.step(actions)
        observations = self._agent_view(output.observations)
        rewards = self._agent_view(output.rewards)
        terminations = {agent: output.terminated for agent in self.agents}
        truncations = {agent: torch.zeros_like(output.terminated) for agent in self.agents}
        infos = {agent: output.info for agent in self.agents}
        return observations, rewards, terminations, truncations, infos
