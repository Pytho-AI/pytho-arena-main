"""REINFORCE backend for the generalized policy-training framework."""

from __future__ import annotations

from typing import Any

import torch
from pydantic import BaseModel, ConfigDict, Field

from ...policies.learned import (
    FeatureContext,
    build_actor,
    movement_features,
    sensing_features,
)
from ..contracts import (
    AlgorithmParameterSpec,
    TrainingAlgorithmDescriptor,
    TrainingResult,
)
from ..session import TrainingSession
from .base import AlgorithmContext, TrainingAlgorithm


class ReinforceParameters(BaseModel):
    """Hyperparameters owned specifically by REINFORCE."""

    model_config = ConfigDict(extra="forbid")

    gamma: float = Field(default=0.99, ge=0.0, le=1.0)
    entropy_coef: float = Field(default=0.01, ge=0.0, le=1.0)


def _discounted_returns(rewards: torch.Tensor, gamma: float) -> torch.Tensor:
    """Return-to-go per step for a ``[steps, batch]`` reward tensor."""
    returns = torch.zeros_like(rewards)
    running = torch.zeros_like(rewards[0])
    for step in range(rewards.shape[0] - 1, -1, -1):
        running = rewards[step] + gamma * running
        returns[step] = running
    return returns


class ReinforceAlgorithm(TrainingAlgorithm):
    """Independent per-binding Monte Carlo policy-gradient training."""

    descriptor = TrainingAlgorithmDescriptor(
        id="reinforce",
        name="REINFORCE",
        family="Policy gradient",
        description=(
            "Monte Carlo policy gradient with a normalized batch baseline and entropy "
            "exploration. A lightweight deterministic baseline for the training stack."
        ),
        on_policy=True,
        supports_multi_agent=True,
        supports_continuous_actions=True,
        supports_discrete_actions=False,
        loss_description="Monte Carlo policy-gradient objective with entropy bonus",
        parameters=[
            AlgorithmParameterSpec(
                id="gamma",
                label="Discount factor",
                description="Weight assigned to rewards farther into the episode.",
                kind="number",
                default=0.99,
                minimum=0.0,
                maximum=1.0,
                step=0.01,
            ),
            AlgorithmParameterSpec(
                id="entropy_coef",
                label="Entropy coefficient",
                description="Exploration bonus applied to the sampled action distribution.",
                kind="number",
                default=0.01,
                minimum=0.0,
                maximum=1.0,
                step=0.005,
            ),
        ],
    )
    parameter_model = ReinforceParameters

    def train(self, context: AlgorithmContext) -> TrainingResult:
        config = context.config
        parameters = ReinforceParameters.model_validate(context.parameters)
        torch.manual_seed(config.seed)

        session = TrainingSession.create(
            context.scenario,
            config,
            scenario_hash=context.scenario_hash,
        )
        arena = session.arena
        env = arena.env
        trainable = session.trainable_ids
        bindings = session.bindings
        scripted = session.scripted_policies
        actors: dict[str, torch.nn.Module] = {}
        feature_contexts: dict[str, FeatureContext] = {}
        optimizers: dict[str, torch.optim.Optimizer] = {}
        for binding_id in trainable:
            binding = bindings[binding_id]
            actors[binding_id] = build_actor(binding.role, env.spatial_dimensions).to(env.device)
            feature_contexts[binding_id] = FeatureContext.for_binding(env, binding)
            optimizers[binding_id] = torch.optim.Adam(
                actors[binding_id].parameters(), lr=config.learning_rate
            )

        history: list[dict[str, Any]] = []
        for iteration in range(config.iterations):
            if context.should_stop is not None and context.should_stop():
                break
            # Fresh worlds per iteration, while the complete job remains reproducible.
            env.seed = config.seed + (iteration + 1) * 40_503
            observations, _ = arena.reset()

            log_probs: dict[str, list[torch.Tensor]] = {agent: [] for agent in trainable}
            entropies: dict[str, list[torch.Tensor]] = {agent: [] for agent in trainable}
            rewards: dict[str, list[torch.Tensor]] = {agent: [] for agent in trainable}
            stopped = False
            for step in range(env.steps):
                if context.should_stop is not None and context.should_stop():
                    stopped = True
                    break
                actions: dict[str, torch.Tensor] = {}
                for agent in arena.agents:
                    if agent not in actors:
                        actions[agent] = scripted[agent].act(observations[agent], step)
                        continue
                    encode = (
                        movement_features
                        if bindings[agent].role == "movement"
                        else sensing_features
                    )
                    features = encode(observations[agent], feature_contexts[agent], step)
                    distribution = actors[agent].distribution(features)
                    sample = distribution.sample()
                    joint = distribution.log_prob(sample)
                    entropy = distribution.entropy()
                    while joint.dim() > 1:
                        joint = joint.sum(dim=-1)
                        entropy = entropy.sum(dim=-1)
                    log_probs[agent].append(joint)
                    entropies[agent].append(entropy)
                    actions[agent] = sample
                observations, step_rewards, _, _, _ = arena.step(actions)
                for agent in trainable:
                    rewards[agent].append(step_rewards[agent])

            if stopped:
                break

            metrics: dict[str, Any] = {"iteration": iteration, "returns": {}, "loss": {}}
            for agent in trainable:
                reward_tensor = torch.stack(rewards[agent])
                returns = _discounted_returns(reward_tensor, parameters.gamma)
                advantage = (returns - returns.mean()) / returns.std(correction=0).clamp_min(1e-6)
                log_prob = torch.stack(log_probs[agent])
                entropy = torch.stack(entropies[agent]).mean()
                loss = -(log_prob * advantage.detach()).mean() - parameters.entropy_coef * entropy
                if not torch.isfinite(loss):
                    raise RuntimeError(f"non-finite training loss for binding {agent!r}")
                optimizers[agent].zero_grad()
                loss.backward()
                optimizers[agent].step()
                if not all(
                    torch.isfinite(parameter).all() for parameter in actors[agent].parameters()
                ):
                    raise RuntimeError(f"non-finite policy parameters for binding {agent!r}")
                metrics["returns"][agent] = float(reward_tensor.sum(dim=0).mean())
                metrics["loss"][agent] = float(loss.detach())
            history.append(metrics)
            if context.on_iteration is not None:
                context.on_iteration(metrics)

        parameter_payload = parameters.model_dump(mode="json")
        payloads = {
            binding_id: {
                "role": bindings[binding_id].role,
                "faction_id": bindings[binding_id].faction_id,
                "spatial_dimensions": env.spatial_dimensions,
                "algorithm_id": self.descriptor.id,
                "algorithm_parameters": parameter_payload,
                "state_dict": {
                    key: value.detach().cpu() for key, value in actor.state_dict().items()
                },
            }
            for binding_id, actor in actors.items()
        }
        return TrainingResult(
            scenario_id=context.scenario.scenario_id,
            scenario_version=context.scenario.version,
            binding_ids=list(trainable),
            algorithm_id=self.descriptor.id,
            algorithm_parameters=parameter_payload,
            device=str(env.device),
            iterations_done=len(history),
            history=history,
            policies=payloads,
        )
