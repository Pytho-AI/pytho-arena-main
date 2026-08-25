"""Extension boundary implemented by every policy-training algorithm."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from ...scenario.models import ScenarioSpec
from ..contracts import TrainingAlgorithmDescriptor, TrainingConfig, TrainingResult


@dataclass(frozen=True)
class AlgorithmContext:
    """Runtime inputs shared by built-in and third-party algorithms."""

    scenario: ScenarioSpec
    config: TrainingConfig
    parameters: BaseModel
    on_iteration: Callable[[dict[str, Any]], None] | None = None
    should_stop: Callable[[], bool] | None = None
    scenario_hash: str | None = None


class TrainingAlgorithm(ABC):
    """A discoverable algorithm that can execute one training job."""

    descriptor: TrainingAlgorithmDescriptor
    parameter_model: type[BaseModel]

    @abstractmethod
    def train(self, context: AlgorithmContext) -> TrainingResult:
        """Train policies for the supplied scenario and return checkpoint payloads."""
