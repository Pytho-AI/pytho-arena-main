"""Versioned contracts for multi-faction Pytho Arena scenarios.

Scenario content — including reward weights — is data. Curated scenario JSON
ships in the package library (overridable with ``PYTHO_ARENA_SCENARIO_DIR``);
nothing operational is hard-coded here.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import UTC, datetime
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Annotated, Any, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

ObjectId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_-]{2,63}$"),
]
Point2 = tuple[float, float]
SceneAssetKind = Literal[
    "warehouse",
    "mixed_block",
    "office_block",
    "storage_tank",
    "marina_pier",
    "cargo_stack",
    "utility_tower",
    "fence_segment",
    "gatehouse",
    "sensor_tower",
    "response_vehicle",
    "patrol_boat",
]
MovementPolicy = Literal["transit", "direct", "probe", "coordinated"]
SensingPolicy = Literal["sweep", "track", "coverage"]
RewardEvent = Literal[
    "own_attack_success",
    "own_intercepted",
    "response_intercept",
    "opponent_attack_success",
    "survival",
    "transit_completion",
]

DEFAULT_SCENARIO_ID = "multi-faction-air-defense"


def scenario_library_dir() -> Traversable:
    override = os.getenv("PYTHO_ARENA_SCENARIO_DIR")
    if override:
        return Path(override)
    return files("pytho_arena.scenario").joinpath("library")


class WorldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: float = Field(default=100.0, gt=10.0, le=10_000.0)
    height: float = Field(default=100.0, gt=10.0, le=10_000.0)
    vertical_extent: float = Field(default=10.0, gt=0.0, le=1_000.0)
    meters_per_unit: float | None = Field(default=None, gt=0.0, le=10_000.0)


class SceneStaticAssetSpec(BaseModel):
    """Static visual prop in scene-local ENU meters."""

    model_config = ConfigDict(extra="forbid")

    id: ObjectId
    kind: SceneAssetKind
    position: Point2
    heading_degrees: float = Field(default=0.0, ge=0.0, lt=360.0)
    scale: float = Field(default=1.0, ge=0.25, le=4.0)

    @field_validator("position")
    @classmethod
    def bounded_scene_position(cls, value: Point2) -> Point2:
        if any(not math.isfinite(axis) or abs(axis) > 10_000 for axis in value):
            raise ValueError("scene asset position must be finite and within 10 km of origin")
        return value


class ScenarioVisualizationSpec(BaseModel):
    """Browser scene selection and fictional static set dressing."""

    model_config = ConfigDict(extra="forbid")

    environment: Literal["gulf_airbase", "coastal_urban"]
    static_assets: list[SceneStaticAssetSpec] = Field(default_factory=list, max_length=512)

    @field_validator("static_assets")
    @classmethod
    def unique_asset_ids(cls, value: list[SceneStaticAssetSpec]) -> list[SceneStaticAssetSpec]:
        ids = [asset.id for asset in value]
        if len(ids) != len(set(ids)):
            raise ValueError("scene asset ids must be unique")
        return value


class SimulationSpec(BaseModel):
    """Execution model and subsystem rates for one scenario.

    ``step_seconds`` remains the policy decision interval. Physics may run at a
    smaller interval while sensing and effects may run less frequently. All
    intervals are validated as integral multiples or divisors of the decision
    interval so deterministic step ordering never depends on wall-clock time.
    """

    model_config = ConfigDict(extra="forbid")

    physics_backend: str = Field(default="kinematic_2d", pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    physics_step_seconds: float | None = Field(default=None, ge=0.001, le=10.0)
    sensor_interval_seconds: float | None = Field(default=None, gt=0.0, le=60.0)
    effects_interval_seconds: float | None = Field(default=None, gt=0.0, le=60.0)


class MobilityComponentSpec(BaseModel):
    """Composable mobility capabilities attached to an actor group."""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(default="scenario_default", pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    max_speed: float | None = Field(default=None, gt=0.05, le=10_000.0)
    max_acceleration: float = Field(default=10_000.0, gt=0.0, le=100_000.0)
    initial_altitude: float = Field(default=0.0, ge=0.0, le=1_000.0)


class CommunicationsComponentSpec(BaseModel):
    """Communication limits kept as scenario data for future network systems."""

    model_config = ConfigDict(extra="forbid")

    model: Literal["perfect", "range_limited", "disconnected"] = "perfect"
    range: float | None = Field(default=None, gt=0.0, le=100_000.0)
    latency_seconds: float = Field(default=0.0, ge=0.0, le=60.0)
    packet_success_probability: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_model(self) -> CommunicationsComponentSpec:
        if self.model == "range_limited" and self.range is None:
            raise ValueError("range_limited communications require range")
        if self.model != "range_limited" and self.range is not None:
            raise ValueError("communications range is only valid for range_limited models")
        return self


class PlatformComponentsSpec(BaseModel):
    """Reusable platform components independent of domain or faction names."""

    model_config = ConfigDict(extra="forbid")

    mobility: MobilityComponentSpec = Field(default_factory=MobilityComponentSpec)
    communications: CommunicationsComponentSpec = Field(default_factory=CommunicationsComponentSpec)
    tags: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("component tags must be unique")
        return value


class ZoneSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ObjectId
    center: Point2
    radius: float = Field(gt=0.0)
    priority: float = Field(default=1.0, gt=0.0, le=10.0)
    altitude: float | None = Field(default=None, ge=0.0, le=1_000.0)


class FactionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ObjectId
    name: str = Field(min_length=1, max_length=80)
    category: Literal["strategic", "background"] = "strategic"
    color: str = Field(default="#c7d1cd", pattern=r"^#[0-9a-fA-F]{6}$")
    objectives: list[str] = Field(default_factory=list, max_length=32)


class RelationshipSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_faction_id: ObjectId
    target_faction_id: ObjectId
    disposition: Literal["ally", "opponent", "neutral", "protected", "unknown"]


class ActorGroupSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ObjectId
    faction_id: ObjectId
    count: int = Field(default=12, ge=1, le=256)
    mission: Literal["attack_objective", "transit"] = "transit"
    speed: float = Field(default=2.0, gt=0.05, le=100.0)
    start_edge: Literal["west", "east", "north", "south"] = "west"
    target_zone_id: ObjectId | None = None
    attack_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    domain: Literal["generic", "air", "ground", "maritime", "space"] = "generic"
    components: PlatformComponentsSpec = Field(default_factory=PlatformComponentsSpec)

    @model_validator(mode="after")
    def validate_mission(self) -> ActorGroupSpec:
        if self.mission == "attack_objective" and self.target_zone_id is None:
            raise ValueError("attack_objective actor groups require target_zone_id")
        if self.mission == "transit" and self.attack_probability != 0.0:
            raise ValueError("transit actor groups must have attack_probability=0")
        return self


class SensorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ObjectId
    faction_id: ObjectId
    position: Point2
    range: float = Field(default=45.0, gt=0.0)
    fov_degrees: float = Field(default=120.0, gt=1.0, le=360.0)
    heading_degrees: float = Field(default=0.0, ge=0.0, lt=360.0)
    capacity: int = Field(default=8, ge=1, le=256)
    detection_probability: float = Field(default=0.85, ge=0.0, le=1.0)
    measurement_noise: float = Field(default=0.75, ge=0.0, le=100.0)
    slew_rate_dps: float | None = Field(default=None, gt=0.0, le=3_600.0)
    altitude: float = Field(default=0.0, ge=0.0, le=1_000.0)


class TypedEffectorSpec(BaseModel):
    """Typed counter-UAS effector declared on a response.

    Declaring this block makes the response authority-gated: the engine applies
    its effect only against entities a human decision authorized for that
    effects tick. Omitting it (the default) keeps the response's legacy
    always-on behavior and, because ``content_hash`` excludes ``None`` fields,
    its existing scenario content hash.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["rf_jammer"] = "rf_jammer"
    available_uses: int = Field(default=1, ge=1, le=256)
    authority_valid_for_seconds: float | None = Field(default=None, gt=0.0, le=3_600.0)


class ResponseSpec(BaseModel):
    """Abstract response capability owned by a faction."""

    model_config = ConfigDict(extra="forbid")

    id: ObjectId
    faction_id: ObjectId
    position: Point2
    engagement_range: float = Field(default=32.0, gt=0.0)
    capacity_per_step: int = Field(default=2, ge=1, le=256)
    effectiveness: float = Field(default=0.68, ge=0.0, le=1.0)
    altitude: float = Field(default=0.0, ge=0.0, le=1_000.0)
    effector: TypedEffectorSpec | None = None


class RewardSpec(BaseModel):
    """Per-event reward weights; the training objective is scenario data."""

    model_config = ConfigDict(extra="forbid")

    attack_success: float = Field(default=3.0, ge=-100.0, le=100.0)
    intercepted: float = Field(default=-1.5, ge=-100.0, le=100.0)
    response_intercept: float = Field(default=1.5, ge=-100.0, le=100.0)
    opponent_attack_success: float = Field(default=-4.0, ge=-100.0, le=100.0)


class RewardTermSpec(BaseModel):
    """A faction-scoped event objective used by the generic reward system."""

    model_config = ConfigDict(extra="forbid")

    id: ObjectId
    faction_id: ObjectId
    event: RewardEvent
    weight: float = Field(ge=-100.0, le=100.0)
    target_faction_ids: list[ObjectId] = Field(default_factory=list, max_length=32)


class PolicyBindingSpec(BaseModel):
    """Binds one policy controller to scenario resources without naming a side."""

    model_config = ConfigDict(extra="forbid")

    id: ObjectId
    name: str | None = Field(default=None, min_length=1, max_length=80)
    faction_id: ObjectId
    role: Literal["movement", "sensing"]
    policy_id: str = Field(min_length=1, max_length=120)
    implementation: Literal["scripted", "learned", "human", "remote"] = "scripted"
    trainable: bool = False
    actor_group_ids: list[ObjectId] = Field(default_factory=list)
    sensor_ids: list[ObjectId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_resources(self) -> PolicyBindingSpec:
        if self.role == "movement" and (not self.actor_group_ids or self.sensor_ids):
            raise ValueError("movement bindings require actor_group_ids only")
        if self.role == "sensing" and (not self.sensor_ids or self.actor_group_ids):
            raise ValueError("sensing bindings require sensor_ids only")
        if self.implementation == "scripted":
            allowed = (
                get_args(MovementPolicy) if self.role == "movement" else get_args(SensingPolicy)
            )
            if self.policy_id not in allowed:
                raise ValueError(f"unknown scripted {self.role} policy: {self.policy_id}")
        return self


class ScenarioSpec(BaseModel):
    """Immutable scenario content; the registry assigns ``version`` on save."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.0"] = "2.0"
    scenario_id: ObjectId = "scenario-demo"
    version: int = Field(default=0, ge=0)
    name: str = Field(default="Scenario Simulation", min_length=3, max_length=120)
    description: str = Field(default="", max_length=1_000)
    duration_seconds: float = Field(default=120.0, ge=5.0, le=3_600.0)
    step_seconds: float = Field(default=1.0, ge=0.1, le=10.0)
    seed: int = Field(default=7, ge=0, le=2_147_483_647)
    evaluation_faction_id: ObjectId | None = None
    world: WorldSpec = Field(default_factory=WorldSpec)
    visualization: ScenarioVisualizationSpec | None = None
    simulation: SimulationSpec = Field(default_factory=SimulationSpec)
    factions: list[FactionSpec] = Field(min_length=2, max_length=32)
    relationships: list[RelationshipSpec] = Field(default_factory=list, max_length=256)
    protected_zones: list[ZoneSpec] = Field(min_length=1, max_length=32)
    actor_groups: list[ActorGroupSpec] = Field(min_length=1, max_length=64)
    sensors: list[SensorSpec] = Field(min_length=1, max_length=64)
    responses: list[ResponseSpec] = Field(default_factory=list, max_length=32)
    rewards: RewardSpec = Field(default_factory=RewardSpec)
    reward_terms: list[RewardTermSpec] = Field(default_factory=list, max_length=256)
    policy_bindings: list[PolicyBindingSpec] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_references(self) -> ScenarioSpec:
        step_count = self.duration_seconds / self.step_seconds
        if step_count > 5_000:
            raise ValueError("duration/step_seconds may not exceed 5,000 ticks")
        if not math.isclose(step_count, round(step_count), abs_tol=1e-9):
            raise ValueError("duration_seconds must be divisible by step_seconds")

        physics_step = self.simulation.physics_step_seconds or self.step_seconds
        physics_substeps = self.step_seconds / physics_step
        if physics_step > self.step_seconds or not math.isclose(
            physics_substeps, round(physics_substeps), abs_tol=1e-9
        ):
            raise ValueError("physics_step_seconds must divide step_seconds into integral substeps")
        if physics_substeps > 1_000:
            raise ValueError("physics_step_seconds may not create more than 1,000 substeps")
        if self.simulation.physics_backend == "multirotor_6dof":
            if self.world.meters_per_unit is None:
                raise ValueError("multirotor_6dof requires world.meters_per_unit")
            if physics_step > 0.02:
                raise ValueError("multirotor_6dof requires physics_step_seconds of 0.02 or less")
        for label, interval in (
            ("sensor_interval_seconds", self.simulation.sensor_interval_seconds),
            ("effects_interval_seconds", self.simulation.effects_interval_seconds),
        ):
            interval = interval or self.step_seconds
            interval_steps = interval / self.step_seconds
            if interval < self.step_seconds or not math.isclose(
                interval_steps, round(interval_steps), abs_tol=1e-9
            ):
                raise ValueError(f"{label} must be an integral multiple of step_seconds")

        def unique_ids(items: list[Any], label: str) -> dict[str, Any]:
            indexed: dict[str, Any] = {}
            for item in items:
                if item.id in indexed:
                    raise ValueError(f"duplicate {label} id: {item.id}")
                indexed[item.id] = item
            return indexed

        def inside(point: Point2) -> bool:
            return 0.0 <= point[0] <= self.world.width and 0.0 <= point[1] <= self.world.height

        factions = unique_ids(self.factions, "faction")
        zones = unique_ids(self.protected_zones, "zone")
        groups = unique_ids(self.actor_groups, "actor group")
        sensors = unique_ids(self.sensors, "sensor")
        responses = unique_ids(self.responses, "response")
        bindings = unique_ids(self.policy_bindings, "policy binding")
        reward_terms = unique_ids(self.reward_terms, "reward term")

        if self.evaluation_faction_id is not None and self.evaluation_faction_id not in factions:
            raise ValueError("evaluation_faction_id references unknown faction")

        for zone in zones.values():
            if not inside(zone.center):
                raise ValueError(f"protected zone {zone.id} lies outside the world")
            if zone.radius > max(self.world.width, self.world.height):
                raise ValueError(f"protected zone {zone.id} radius exceeds the world")
            if zone.altitude is not None and zone.altitude > self.world.vertical_extent:
                raise ValueError(f"protected zone {zone.id} altitude exceeds the world")

        for group in groups.values():
            if group.faction_id not in factions:
                raise ValueError(f"actor group {group.id} references unknown faction")
            if group.target_zone_id is not None and group.target_zone_id not in zones:
                raise ValueError(f"actor group {group.id} references unknown target zone")
            mobility_model = group.components.mobility.model
            expected_model = self.simulation.physics_backend
            if mobility_model not in {"scenario_default", expected_model}:
                raise ValueError(
                    f"actor group {group.id} mobility model {mobility_model!r} does not "
                    f"match scenario physics backend {expected_model!r}"
                )
            if expected_model == "multirotor_6dof" and group.domain != "air":
                raise ValueError(
                    f"actor group {group.id} must use the air domain for multirotor_6dof"
                )
            if group.components.mobility.initial_altitude > self.world.vertical_extent:
                raise ValueError(f"actor group {group.id} initial altitude exceeds the world")

        for sensor in sensors.values():
            if sensor.faction_id not in factions:
                raise ValueError(f"sensor {sensor.id} references unknown faction")
            if not inside(sensor.position):
                raise ValueError(f"sensor {sensor.id} lies outside the world")
            if sensor.altitude > self.world.vertical_extent:
                raise ValueError(f"sensor {sensor.id} altitude exceeds the world")

        for response in responses.values():
            if response.faction_id not in factions:
                raise ValueError(f"response {response.id} references unknown faction")
            if not inside(response.position):
                raise ValueError(f"response {response.id} lies outside the world")
            if response.altitude > self.world.vertical_extent:
                raise ValueError(f"response {response.id} altitude exceeds the world")

        for term in reward_terms.values():
            if term.faction_id not in factions:
                raise ValueError(f"reward term {term.id} references unknown faction")
            unknown_targets = set(term.target_faction_ids) - set(factions)
            if unknown_targets:
                raise ValueError(
                    f"reward term {term.id} references unknown target factions: "
                    f"{sorted(unknown_targets)}"
                )

        relationship_pairs: set[tuple[str, str]] = set()
        for relationship in self.relationships:
            pair = (relationship.source_faction_id, relationship.target_faction_id)
            if pair in relationship_pairs:
                raise ValueError(f"duplicate relationship: {pair[0]} -> {pair[1]}")
            relationship_pairs.add(pair)
            if pair[0] not in factions or pair[1] not in factions:
                raise ValueError(f"relationship {pair[0]} -> {pair[1]} references unknown faction")

        bound_groups: set[str] = set()
        bound_sensors: set[str] = set()
        for binding in bindings.values():
            if binding.faction_id not in factions:
                raise ValueError(f"policy binding {binding.id} references unknown faction")
            for group_id in binding.actor_group_ids:
                group = groups.get(group_id)
                if group is None or group.faction_id != binding.faction_id:
                    raise ValueError(f"policy binding {binding.id} has invalid actor group")
                if group_id in bound_groups:
                    raise ValueError(f"actor group {group_id} has multiple movement bindings")
                bound_groups.add(group_id)
            for sensor_id in binding.sensor_ids:
                sensor = sensors.get(sensor_id)
                if sensor is None or sensor.faction_id != binding.faction_id:
                    raise ValueError(f"policy binding {binding.id} has invalid sensor")
                if sensor_id in bound_sensors:
                    raise ValueError(f"sensor {sensor_id} has multiple sensing bindings")
                bound_sensors.add(sensor_id)

        if bound_groups != set(groups):
            raise ValueError("every actor group must have exactly one movement policy binding")
        if bound_sensors != set(sensors):
            raise ValueError("every sensor must have exactly one sensing policy binding")
        return self

    @property
    def steps(self) -> int:
        return int(round(self.duration_seconds / self.step_seconds))

    @property
    def entity_count(self) -> int:
        return sum(group.count for group in self.actor_groups)

    def content_hash(self) -> str:
        # None-valued fields are excluded so that newly added optional fields
        # (which must default to None) never change the hash of existing content.
        payload = self.model_dump(mode="json", exclude={"version"}, exclude_none=True)
        # Generalization fields use structured defaults rather than None. Elide
        # those defaults as well so additive schema evolution preserves hashes
        # for existing immutable scenario versions.
        if payload["simulation"] == SimulationSpec().model_dump(mode="json", exclude_none=True):
            payload.pop("simulation")
        if not payload["reward_terms"]:
            payload.pop("reward_terms")
        default_components = PlatformComponentsSpec().model_dump(mode="json", exclude_none=True)
        for group in payload["actor_groups"]:
            if group["domain"] == "generic":
                group.pop("domain")
            if group["components"] == default_components:
                group.pop("components")
        for sensor in payload["sensors"]:
            if sensor["altitude"] == 0.0:
                sensor.pop("altitude")
        for response in payload["responses"]:
            if response["altitude"] == 0.0:
                response.pop("altitude")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


class ScenarioRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: ScenarioSpec
    content_hash: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


def load_scenario_file(path: Traversable) -> ScenarioSpec:
    return ScenarioSpec.model_validate_json(path.read_text(encoding="utf-8"))


def library_scenarios() -> list[ScenarioSpec]:
    """Load every curated scenario JSON from the library directory."""
    library = scenario_library_dir()
    if not library.is_dir():
        return []
    paths = sorted(
        (path for path in library.iterdir() if path.is_file() and path.name.endswith(".json")),
        key=lambda path: path.name,
    )
    return [load_scenario_file(path) for path in paths]


def default_scenario() -> ScenarioSpec:
    return load_scenario_file(scenario_library_dir().joinpath(f"{DEFAULT_SCENARIO_ID}.json"))
