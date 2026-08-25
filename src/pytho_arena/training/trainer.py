"""Backward-compatible facade for the generalized training registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..scenario.models import ScenarioSpec
from .contracts import TrainingConfig, TrainingResult
from .registry import train_with_algorithm


def train(
    scenario: ScenarioSpec,
    config: TrainingConfig | None = None,
    *,
    on_iteration: Callable[[dict[str, Any]], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    scenario_hash: str | None = None,
) -> TrainingResult:
    """Train with the algorithm selected by ``config.algorithm_id``.

    ``reinforce`` remains the default, preserving the behavior of the original
    trainer while allowing additional algorithms to register behind this API.
    """
    return train_with_algorithm(
        scenario,
        config,
        on_iteration=on_iteration,
        should_stop=should_stop,
        scenario_hash=scenario_hash,
    )
