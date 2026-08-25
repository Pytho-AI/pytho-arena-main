"""Pytho Arena: extensible multi-faction policy simulation environment.

Layers, by dependency direction:

- ``scenario`` — versioned data contracts, reward weights, scenario registry
- ``simulation`` — compiler, physics, clocks, events, objectives, contract hashes
- ``core``     — batched tensor kernel; ``step(actions)`` with external actions
- ``policies`` — Policy interface, scripted baselines, binding registry
- ``env``      — rollout drivers and multi-agent (parallel-API) adapters
- ``training`` — algorithm registry, RL execution, job contracts, checkpoints
- ``experiments`` — population evaluation and empirical-game manifests
- ``live``     — canonical messages and shadow-mode adapters
- ``server``   — FastAPI app, replay evidence, run/training stores (``[server]`` extra)
"""

from .core.devices import select_device
from .core.env import BatchedScenarioEnv, StepOutput
from .policies import build_policies, resolve_policy_ids
from .scenario.models import (
    ActorGroupSpec,
    CommunicationsComponentSpec,
    FactionSpec,
    MobilityComponentSpec,
    PlatformComponentsSpec,
    PolicyBindingSpec,
    RelationshipSpec,
    ResponseSpec,
    RewardSpec,
    RewardTermSpec,
    ScenarioSpec,
    ScenarioVisualizationSpec,
    SceneStaticAssetSpec,
    SensorSpec,
    SimulationSpec,
    WorldSpec,
    ZoneSpec,
    default_scenario,
    library_scenarios,
)
from .simulation import (
    PHYSICS_BACKEND_API_VERSION,
    CommunicationsDisruption,
    DisruptionSpec,
    EffectorDisruption,
    EnvironmentContract,
    MultiRateScheduler,
    PhysicsBackend,
    PhysicsState,
    SensorDisruption,
    available_physics_backends,
    environment_contract,
    register_physics_backend,
)

__version__ = "0.5.0"

__all__ = [
    "ActorGroupSpec",
    "BatchedScenarioEnv",
    "CommunicationsComponentSpec",
    "CommunicationsDisruption",
    "DisruptionSpec",
    "EffectorDisruption",
    "SensorDisruption",
    "FactionSpec",
    "EnvironmentContract",
    "MobilityComponentSpec",
    "MultiRateScheduler",
    "PHYSICS_BACKEND_API_VERSION",
    "PlatformComponentsSpec",
    "PhysicsBackend",
    "PhysicsState",
    "PolicyBindingSpec",
    "RelationshipSpec",
    "ResponseSpec",
    "RewardSpec",
    "RewardTermSpec",
    "ScenarioSpec",
    "ScenarioVisualizationSpec",
    "SceneStaticAssetSpec",
    "SensorSpec",
    "SimulationSpec",
    "StepOutput",
    "WorldSpec",
    "ZoneSpec",
    "CheckpointStore",
    "TrainingAlgorithmDescriptor",
    "TrainingConfig",
    "available_physics_backends",
    "available_training_algorithms",
    "build_policies",
    "create_app",
    "default_scenario",
    "environment_contract",
    "library_scenarios",
    "resolve_policy_ids",
    "register_physics_backend",
    "register_training_algorithm",
    "select_device",
    "train",
]


def __getattr__(name: str):
    if name == "create_app":
        from .server.app import create_app

        return create_app
    if name in {
        "CheckpointStore",
        "TrainingAlgorithmDescriptor",
        "TrainingConfig",
        "available_training_algorithms",
        "register_training_algorithm",
        "train",
    }:
        from . import training

        return getattr(training, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
