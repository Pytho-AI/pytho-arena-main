"""Framework-neutral contracts for policy training jobs and algorithms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..simulation.disruptions import DisruptionSpec

ParameterValue = bool | int | float | str


class AlgorithmParameterSpec(BaseModel):
    """One UI-renderable, API-visible algorithm hyperparameter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=240)
    kind: Literal["number", "integer", "boolean"]
    default: ParameterValue
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = Field(default=None, gt=0.0)


class TrainingAlgorithmDescriptor(BaseModel):
    """Stable discovery metadata for a registered training algorithm."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    name: str = Field(min_length=1, max_length=80)
    family: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=320)
    on_policy: bool
    supports_multi_agent: bool
    supports_continuous_actions: bool
    supports_discrete_actions: bool
    supports_recurrent: bool = False
    supports_centralized_critic: bool = False
    loss_description: str = Field(min_length=1, max_length=200)
    parameters: list[AlgorithmParameterSpec] = Field(default_factory=list)


class TrainingConfig(BaseModel):
    """Common job controls plus a registered algorithm and its parameters.

    Algorithm-specific validation is intentionally owned by the algorithm
    registry. The pre-validator migrates the original REINFORCE-only request
    shape, so persisted 0.4.x jobs and older API clients remain readable.
    """

    model_config = ConfigDict(extra="forbid")

    binding_ids: list[str] | None = Field(
        default=None,
        description="Bindings to train; defaults to every binding marked trainable.",
    )
    algorithm_id: str = Field(
        default="reinforce",
        pattern=r"^[a-z][a-z0-9_-]{2,63}$",
    )
    algorithm_parameters: dict[str, ParameterValue] = Field(default_factory=dict)
    iterations: int = Field(default=40, ge=1, le=5_000)
    batch_size: int = Field(default=64, ge=1, le=4_096)
    learning_rate: float = Field(default=3e-3, gt=0.0, le=1.0)
    seed: int = Field(default=7, ge=0, le=2_147_483_647)
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    disruptions: list[DisruptionSpec] = Field(
        default_factory=list,
        max_length=32,
        description=(
            "Typed ability degradations (communications, sensor, effector) "
            "applied to every training rollout, matching the run-time knob."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_reinforce_parameters(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        raw_parameters = payload.get("algorithm_parameters")
        if raw_parameters is not None and not isinstance(raw_parameters, dict):
            return payload
        parameters = dict(raw_parameters or {})
        for legacy_name in ("gamma", "entropy_coef"):
            if legacy_name in payload:
                parameters.setdefault(legacy_name, payload.pop(legacy_name))
        payload["algorithm_parameters"] = parameters
        return payload

    @field_validator("binding_ids")
    @classmethod
    def unique_binding_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and not value:
            raise ValueError("binding_ids must contain at least one binding when provided")
        if value is not None and len(value) != len(set(value)):
            raise ValueError("binding_ids must be unique")
        return value


@dataclass
class TrainingResult:
    scenario_id: str
    scenario_version: int
    binding_ids: list[str]
    algorithm_id: str
    algorithm_parameters: dict[str, ParameterValue]
    device: str
    iterations_done: int
    history: list[dict[str, Any]]
    policies: dict[str, dict[str, Any]] = field(repr=False)
