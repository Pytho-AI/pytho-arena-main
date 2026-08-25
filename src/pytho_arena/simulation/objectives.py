"""Faction-scoped objective evaluation independent of policy implementations."""

from __future__ import annotations

from typing import Protocol

import torch

from ..scenario.models import ScenarioSpec


class ObjectiveState(Protocol):
    batch_size: int
    device: torch.device
    dtype: torch.dtype
    faction_ids: list[str]
    faction_index: dict[str, int]
    faction_entity_mask: torch.Tensor
    faction_opponent_entity_mask: torch.Tensor
    entity_count: int
    current_attack_successes: torch.Tensor
    current_intercepts: torch.Tensor
    current_intercepts_by_faction: torch.Tensor
    current_transit_completions: torch.Tensor
    active: torch.Tensor
    step_index: int
    steps: int


def evaluate_rewards(scenario: ScenarioSpec, state: ObjectiveState) -> dict[str, torch.Tensor]:
    rewards = {
        faction_id: torch.zeros((state.batch_size,), device=state.device, dtype=state.dtype)
        for faction_id in state.faction_ids
    }
    if scenario.reward_terms:
        for term in scenario.reward_terms:
            faction_number = state.faction_index[term.faction_id]
            own_entities = state.faction_entity_mask[faction_number][None, :]
            target_mask = _target_mask(term.target_faction_ids, faction_number, state)
            if term.event == "own_attack_success":
                count = (state.current_attack_successes & own_entities).sum(dim=1)
            elif term.event == "own_intercepted":
                count = (state.current_intercepts & own_entities).sum(dim=1)
            elif term.event == "response_intercept":
                count = state.current_intercepts_by_faction[:, faction_number, :].sum(dim=1)
            elif term.event == "opponent_attack_success":
                count = (state.current_attack_successes & target_mask[None, :]).sum(dim=1)
            elif term.event == "survival":
                count = (
                    (state.active & own_entities).sum(dim=1)
                    if state.step_index + 1 >= state.steps
                    else torch.zeros((state.batch_size,), device=state.device, dtype=torch.long)
                )
            else:
                count = (state.current_transit_completions & own_entities).sum(dim=1)
            rewards[term.faction_id] += count.to(state.dtype) * term.weight
        return rewards

    weights = scenario.rewards
    for faction_number, faction_id in enumerate(state.faction_ids):
        own_entities = state.faction_entity_mask[faction_number][None, :]
        rewards[faction_id] += (state.current_attack_successes & own_entities).sum(dim=1).to(
            state.dtype
        ) * weights.attack_success
        rewards[faction_id] += (state.current_intercepts & own_entities).sum(dim=1).to(
            state.dtype
        ) * weights.intercepted
        rewards[faction_id] += (
            state.current_intercepts_by_faction[:, faction_number, :].sum(dim=1).to(state.dtype)
            * weights.response_intercept
        )
        opponent_attacks = (
            state.current_attack_successes
            & state.faction_opponent_entity_mask[faction_number][None, :]
        )
        rewards[faction_id] += (
            opponent_attacks.sum(dim=1).to(state.dtype) * weights.opponent_attack_success
        )
    return rewards


def _target_mask(
    target_faction_ids: list[str], faction_number: int, state: ObjectiveState
) -> torch.Tensor:
    if not target_faction_ids:
        return state.faction_opponent_entity_mask[faction_number]
    target_mask = torch.zeros((state.entity_count,), device=state.device, dtype=torch.bool)
    for target_id in target_faction_ids:
        target_mask |= state.faction_entity_mask[state.faction_index[target_id]]
    return target_mask
