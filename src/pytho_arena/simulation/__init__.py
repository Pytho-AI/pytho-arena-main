"""Composable simulation contracts shared by every domain and fidelity level."""

from .compiler import CompiledScenario, compile_scenario
from .contracts import EnvironmentContract, environment_contract
from .disruptions import (
    CommunicationsDisruption,
    DisruptionSpec,
    EffectorDisruption,
    SensorDisruption,
)
from .events import EventKind, SimulationEvent
from .physics import (
    PHYSICS_BACKEND_API_VERSION,
    Kinematic2DBackend,
    PhysicsBackend,
    PhysicsState,
    PointMass3DBackend,
    available_physics_backends,
    physics_backend,
    register_physics_backend,
)
from .scheduler import MultiRateScheduler

__all__ = [
    "CommunicationsDisruption",
    "DisruptionSpec",
    "EffectorDisruption",
    "EnvironmentContract",
    "CompiledScenario",
    "EventKind",
    "Kinematic2DBackend",
    "MultiRateScheduler",
    "PHYSICS_BACKEND_API_VERSION",
    "PhysicsBackend",
    "PhysicsState",
    "PointMass3DBackend",
    "SensorDisruption",
    "SimulationEvent",
    "available_physics_backends",
    "environment_contract",
    "compile_scenario",
    "physics_backend",
    "register_physics_backend",
]
