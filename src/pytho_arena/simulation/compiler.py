"""Compile declarative scenario data into executable subsystem contracts."""

from __future__ import annotations

from dataclasses import dataclass

from ..scenario.models import ScenarioSpec
from .contracts import EnvironmentContract, environment_contract
from .physics import PhysicsBackend, physics_backend
from .scheduler import MultiRateScheduler


@dataclass(frozen=True)
class CompiledScenario:
    source: ScenarioSpec
    scenario_hash: str
    contract: EnvironmentContract
    scheduler: MultiRateScheduler
    physics: PhysicsBackend


def compile_scenario(
    scenario: ScenarioSpec, *, scenario_hash: str | None = None
) -> CompiledScenario:
    immutable_hash = scenario_hash or scenario.content_hash()
    backend = physics_backend(scenario.simulation.physics_backend)
    contract = environment_contract(scenario, scenario_hash=immutable_hash)
    if backend.spatial_dimensions != contract.spatial_dimensions:
        raise ValueError("physics backend and environment contract dimensions disagree")
    return CompiledScenario(
        source=scenario,
        scenario_hash=immutable_hash,
        contract=contract,
        scheduler=MultiRateScheduler.from_scenario(scenario),
        physics=backend,
    )
