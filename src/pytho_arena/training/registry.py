"""Discovery, validation, and execution registry for training algorithms."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from ..scenario.models import ScenarioSpec
from .algorithms.base import AlgorithmContext, TrainingAlgorithm
from .algorithms.reinforce import ReinforceAlgorithm
from .contracts import TrainingAlgorithmDescriptor, TrainingConfig, TrainingResult

DEFAULT_ALGORITHM_ID = "reinforce"
_ALGORITHMS: dict[str, TrainingAlgorithm] = {}


def register_training_algorithm(algorithm: TrainingAlgorithm, *, replace: bool = False) -> None:
    """Register an algorithm implementation under its descriptor id."""
    if not isinstance(algorithm, TrainingAlgorithm):
        raise TypeError("training algorithms must implement TrainingAlgorithm")
    algorithm_id = algorithm.descriptor.id
    if algorithm_id in _ALGORITHMS and not replace:
        raise ValueError(f"training algorithm {algorithm_id!r} is already registered")
    declared_parameters = [parameter.id for parameter in algorithm.descriptor.parameters]
    if len(declared_parameters) != len(set(declared_parameters)):
        raise ValueError(f"training algorithm {algorithm_id!r} declares duplicate parameters")
    model_parameters = set(algorithm.parameter_model.model_fields)
    if set(declared_parameters) != model_parameters:
        raise ValueError(
            f"training algorithm {algorithm_id!r} descriptor parameters do not match "
            "its parameter model"
        )
    algorithm.parameter_model.model_validate(
        {parameter.id: parameter.default for parameter in algorithm.descriptor.parameters}
    )
    _ALGORITHMS[algorithm_id] = algorithm


def get_training_algorithm(algorithm_id: str) -> TrainingAlgorithm:
    try:
        return _ALGORITHMS[algorithm_id]
    except KeyError as exc:
        available = ", ".join(sorted(_ALGORITHMS)) or "none"
        raise ValueError(
            f"unknown training algorithm {algorithm_id!r}; available: {available}"
        ) from exc


def available_training_algorithms() -> list[TrainingAlgorithmDescriptor]:
    return [_ALGORITHMS[key].descriptor for key in sorted(_ALGORITHMS)]


def normalize_training_config(config: TrainingConfig) -> TrainingConfig:
    """Resolve defaults and validate parameters with the selected backend."""
    algorithm = get_training_algorithm(config.algorithm_id)
    try:
        parameters = algorithm.parameter_model.model_validate(config.algorithm_parameters)
    except ValidationError as exc:
        issue = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in issue["loc"])
        detail = f"{location}: {issue['msg']}" if location else issue["msg"]
        raise ValueError(
            f"invalid parameters for training algorithm {config.algorithm_id!r}: {detail}"
        ) from exc
    return config.model_copy(update={"algorithm_parameters": parameters.model_dump(mode="json")})


def train_with_algorithm(
    scenario: ScenarioSpec,
    config: TrainingConfig | None = None,
    *,
    on_iteration: Callable[[dict[str, Any]], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    scenario_hash: str | None = None,
) -> TrainingResult:
    """Validate a job and dispatch it to its registered algorithm."""
    normalized = normalize_training_config(config or TrainingConfig())
    algorithm = get_training_algorithm(normalized.algorithm_id)
    parameters = algorithm.parameter_model.model_validate(normalized.algorithm_parameters)
    return algorithm.train(
        AlgorithmContext(
            scenario=scenario,
            config=normalized,
            parameters=parameters,
            on_iteration=on_iteration,
            should_stop=should_stop,
            scenario_hash=scenario_hash,
        )
    )


register_training_algorithm(ReinforceAlgorithm())
