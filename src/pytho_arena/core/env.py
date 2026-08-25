"""Deterministic batched tensor engine driven by externally supplied actions.

The engine compiles a scenario into dense tensors and advances the world with
``step(actions)``, where actions come from outside — scripted baselines, trained
policies, humans, or remote controllers. It never computes policy decisions
itself, so wargaming and training drive the exact same dynamics.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import torch

from ..scenario.models import ScenarioSpec
from ..simulation.beliefs import (
    age_beliefs,
    evaluation_detections,
    update_detection_attribution,
    update_detection_centroids,
)
from ..simulation.compiler import compile_scenario
from ..simulation.disruptions import (
    CommunicationsDisruption,
    EffectorDisruption,
    SensorDisruption,
    validate_disruptions,
)
from ..simulation.objectives import evaluate_rewards
from ..simulation.physics import PhysicsState
from .devices import select_device
from .rng import (
    ATTACK_SUCCESS_CHANNEL,
    COMMS_DELIVERY_CHANNEL,
    EFFECTOR_RELIABILITY_CHANNEL,
    MEASUREMENT_NOISE_CHANNEL,
    RESPONSE_SUCCESS_CHANNEL,
    SENSING_DETECTION_CHANNEL,
    SPAWN_ALONG_CHANNEL,
    SPAWN_INSET_CHANNEL,
    stateless_normal,
    stateless_uniform,
    wrap_angle,
)

EDGE_CODES = {"west": 0, "east": 1, "north": 2, "south": 3}


@dataclass
class StepOutput:
    observations: dict[str, dict[str, torch.Tensor]]
    rewards: dict[str, torch.Tensor]
    terminated: torch.Tensor
    info: dict[str, torch.Tensor]


class BatchedScenarioEnv:
    """A batch of independent copies of one compiled multi-faction scenario.

    Actions are normalized *commands* keyed by policy-binding id, and the engine
    owns the actuator stage that turns commands into state (validate -> project
    onto the feasible set -> integrate), so no controller can exceed declared
    scenario capabilities:

    - movement bindings supply command vectors in the unit ball, shaped
      ``[batch, k, D]`` (``D`` is the compiled spatial dimension and
      ``movement_binding_entities[binding_id]`` gives global
      indices); the engine multiplies by each entity's declared speed
    - sensing bindings supply desired absolute headings in radians, shaped
      ``[batch, k]`` (``sensing_binding_sensors[binding_id]``); the engine
      applies the sensor's slew-rate limit when one is declared

    Non-finite or mis-shaped actions are rejected; out-of-bounds commands are
    projected (clipped) and counted in ``StepOutput.info`` saturation counters.
    """

    def __init__(
        self,
        scenario: ScenarioSpec,
        *,
        batch_size: int = 1,
        seed: int | None = None,
        device: str = "auto",
        scenario_hash: str | None = None,
        disruptions: Iterable[object] | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.scenario = scenario
        self.compiled = compile_scenario(scenario, scenario_hash=scenario_hash)
        self.scenario_hash = self.compiled.scenario_hash
        self.batch_size = batch_size
        self.seed = scenario.seed if seed is None else seed
        self.disruptions = validate_disruptions(disruptions)
        self.device = select_device(device)
        self.dtype = torch.float32
        self.scheduler = self.compiled.scheduler
        self.physics = self.compiled.physics
        self.spatial_dimensions = self.physics.spatial_dimensions
        self.faction_ids = [faction.id for faction in scenario.factions]
        self.faction_index = {faction_id: i for i, faction_id in enumerate(self.faction_ids)}
        self.faction_count = len(self.faction_ids)
        self.entity_count = scenario.entity_count
        self.sensor_count = len(scenario.sensors)
        self.response_count = len(scenario.responses)
        self.steps = scenario.steps
        self.dt = scenario.step_seconds
        self._compile()
        self.reset()

    def _compile(self) -> None:
        b = self.batch_size
        device = self.device

        group_binding: dict[str, str] = {}
        for binding in self.scenario.policy_bindings:
            for group_id in binding.actor_group_ids:
                group_binding[group_id] = binding.id

        zone_by_id = {zone.id: zone for zone in self.scenario.protected_zones}
        entity_ids: list[str] = []
        entity_factions: list[str] = []
        entity_groups: list[str] = []
        faction_indices: list[int] = []
        speeds: list[float] = []
        start_edges: list[int] = []
        missions_attack: list[bool] = []
        attack_probabilities: list[float] = []
        max_accelerations: list[float] = []
        initial_altitudes: list[float] = []
        target_positions: list[tuple[float, ...]] = []
        target_radii: list[float] = []
        binding_entities: dict[str, list[int]] = {
            binding.id: []
            for binding in self.scenario.policy_bindings
            if binding.role == "movement"
        }

        for group in self.scenario.actor_groups:
            binding_id = group_binding[group.id]
            mobility = group.components.mobility
            speed = mobility.max_speed or group.speed
            altitude = mobility.initial_altitude
            if group.target_zone_id:
                target_zone = zone_by_id[group.target_zone_id]
                target_altitude = (
                    target_zone.altitude if target_zone.altitude is not None else altitude
                )
                target = (
                    (*target_zone.center, target_altitude)
                    if self.spatial_dimensions == 3
                    else target_zone.center
                )
                target_radius = target_zone.radius
            else:
                target = self._transit_target(group.start_edge, altitude)
                target_radius = 0.0
            for number in range(group.count):
                binding_entities[binding_id].append(len(entity_ids))
                entity_ids.append(f"{group.id}-{number + 1:02d}")
                entity_factions.append(group.faction_id)
                entity_groups.append(group.id)
                faction_indices.append(self.faction_index[group.faction_id])
                speeds.append(speed)
                max_accelerations.append(mobility.max_acceleration)
                initial_altitudes.append(altitude)
                start_edges.append(EDGE_CODES[group.start_edge])
                missions_attack.append(group.mission == "attack_objective")
                attack_probabilities.append(group.attack_probability)
                target_positions.append(target)
                target_radii.append(target_radius)

        self.entity_ids = entity_ids
        self.entity_indices_by_id = {entity_id: i for i, entity_id in enumerate(entity_ids)}
        self.entity_faction_ids = entity_factions
        self.entity_group_ids = entity_groups
        self.entity_faction_indices = torch.tensor(faction_indices, device=device, dtype=torch.long)
        self.entity_speeds = torch.tensor(speeds, device=device, dtype=self.dtype)[None, :, None]
        self.entity_max_accelerations = torch.tensor(
            max_accelerations, device=device, dtype=self.dtype
        )[None, :, None]
        self.entity_initial_altitudes = torch.tensor(
            initial_altitudes, device=device, dtype=self.dtype
        )[None, :]
        self.start_edge_codes = torch.tensor(start_edges, device=device, dtype=torch.long)
        self.attack_mission = torch.tensor(missions_attack, device=device, dtype=torch.bool)
        self.transit_mission = ~self.attack_mission
        self.attack_probability = torch.tensor(
            attack_probabilities, device=device, dtype=self.dtype
        )[None, :]
        targets = torch.tensor(target_positions, device=device, dtype=self.dtype)
        self.entity_targets = targets[None, :, :].expand(b, -1, -1).clone()
        self.entity_target_radii = torch.tensor(target_radii, device=device, dtype=self.dtype)[
            None, :
        ]
        self.transit_directions = self._transit_directions()[None, :, :].expand(b, -1, -1)
        bounds = [self.scenario.world.width, self.scenario.world.height]
        if self.spatial_dimensions == 3:
            bounds.append(self.scenario.world.vertical_extent)
        self.world_bounds = torch.tensor(bounds, device=device, dtype=self.dtype)[None, None, :]

        self.movement_binding_entities = {
            binding_id: torch.tensor(indices, device=device, dtype=torch.long)
            for binding_id, indices in binding_entities.items()
        }
        self.sensing_binding_sensors = {
            binding.id: torch.tensor(
                [
                    index
                    for index, sensor in enumerate(self.scenario.sensors)
                    if sensor.id in set(binding.sensor_ids)
                ],
                device=device,
                dtype=torch.long,
            )
            for binding in self.scenario.policy_bindings
            if binding.role == "sensing"
        }

        self.faction_entity_mask = torch.stack(
            [self.entity_faction_indices == i for i in range(self.faction_count)]
        )
        self.faction_entity_indices = [
            torch.nonzero(mask, as_tuple=False).flatten() for mask in self.faction_entity_mask
        ]

        self._compile_relationships()
        self._compile_sensors()
        self._compile_responses()
        self._compile_disruptions()

    def _transit_target(self, start_edge: str, altitude: float) -> tuple[float, ...]:
        width, height = self.scenario.world.width, self.scenario.world.height
        if start_edge == "west":
            target = (width, height * 0.5)
        elif start_edge == "east":
            target = (0.0, height * 0.5)
        elif start_edge == "north":
            target = (width * 0.5, 0.0)
        else:
            target = (width * 0.5, height)
        return (*target, altitude) if self.spatial_dimensions == 3 else target

    def _transit_directions(self) -> torch.Tensor:
        directions = torch.zeros(
            (self.entity_count, self.spatial_dimensions),
            device=self.device,
            dtype=self.dtype,
        )
        directions[self.start_edge_codes == EDGE_CODES["west"], 0] = 1.0
        directions[self.start_edge_codes == EDGE_CODES["east"], 0] = -1.0
        directions[self.start_edge_codes == EDGE_CODES["north"], 1] = -1.0
        directions[self.start_edge_codes == EDGE_CODES["south"], 1] = 1.0
        return directions

    def _compile_relationships(self) -> None:
        relationship_codes = {
            "unknown": 0,
            "ally": 1,
            "opponent": 2,
            "neutral": 3,
            "protected": 4,
        }
        matrix = torch.zeros(
            (self.faction_count, self.faction_count), device=self.device, dtype=torch.long
        )
        for relationship in self.scenario.relationships:
            source = self.faction_index[relationship.source_faction_id]
            target = self.faction_index[relationship.target_faction_id]
            matrix[source, target] = relationship_codes[relationship.disposition]
        self.relationship_matrix = matrix
        self.ally_matrix = matrix == relationship_codes["ally"]
        self.opponent_matrix = matrix == relationship_codes["opponent"]
        self.protected_matrix = matrix == relationship_codes["protected"]
        self.faction_opponent_entity_mask = self.opponent_matrix[:, self.entity_faction_indices]

        if self.scenario.evaluation_faction_id is None:
            self.evaluation_faction_index = None
            evaluator_opponents = self.opponent_matrix.any(dim=0)
            evaluator_protected = self.protected_matrix.any(dim=0)
        else:
            evaluator = self.faction_index[self.scenario.evaluation_faction_id]
            self.evaluation_faction_index = evaluator
            evaluator_opponents = self.opponent_matrix[evaluator]
            evaluator_protected = self.protected_matrix[evaluator]
        self.opponent_entity_mask = evaluator_opponents[self.entity_faction_indices]
        self.protected_entity_mask = evaluator_protected[self.entity_faction_indices]

    def _compile_sensors(self) -> None:
        b = self.batch_size
        sensors = self.scenario.sensors
        sensor_positions = torch.tensor(
            [
                (*sensor.position, sensor.altitude)
                if self.spatial_dimensions == 3
                else sensor.position
                for sensor in sensors
            ],
            device=self.device,
            dtype=self.dtype,
        )
        self.sensor_positions = sensor_positions[None, :, :].expand(b, -1, -1).clone()
        self.sensor_ranges = torch.tensor(
            [sensor.range for sensor in sensors], device=self.device, dtype=self.dtype
        )[None, :, None]
        self.sensor_fov = torch.deg2rad(
            torch.tensor(
                [sensor.fov_degrees for sensor in sensors],
                device=self.device,
                dtype=self.dtype,
            )
        )[None, :, None]
        self.initial_headings = (
            torch.deg2rad(
                torch.tensor(
                    [sensor.heading_degrees for sensor in sensors],
                    device=self.device,
                    dtype=self.dtype,
                )
            )[None, :]
            .expand(b, -1)
            .clone()
        )
        self.sensor_capacity = torch.tensor(
            [sensor.capacity for sensor in sensors], device=self.device, dtype=torch.long
        )[None, :, None]
        self.sensor_pd = torch.tensor(
            [sensor.detection_probability for sensor in sensors],
            device=self.device,
            dtype=self.dtype,
        )[None, :, None]
        self.sensor_noise = torch.tensor(
            [sensor.measurement_noise for sensor in sensors],
            device=self.device,
            dtype=self.dtype,
        )[None, :, None, None]
        self.sensor_faction_indices = torch.tensor(
            [self.faction_index[sensor.faction_id] for sensor in sensors],
            device=self.device,
            dtype=torch.long,
        )
        self.sensor_slew_limits = torch.tensor(
            [
                math.radians(sensor.slew_rate_dps) * self.dt
                if sensor.slew_rate_dps is not None
                else math.inf
                for sensor in sensors
            ],
            device=self.device,
            dtype=self.dtype,
        )[None, :]
        self.cross_faction_sensor_mask = (
            self.sensor_faction_indices[:, None] != self.entity_faction_indices[None, :]
        )
        self.faction_sensor_access = torch.stack(
            [
                (self.sensor_faction_indices == faction_number)
                | self.ally_matrix[faction_number, self.sensor_faction_indices]
                for faction_number in range(self.faction_count)
            ]
        )

    def _compile_responses(self) -> None:
        b = self.batch_size
        responses = self.scenario.responses
        self.response_ids = [response.id for response in responses]
        self.response_indices_by_id = {
            response_id: i for i, response_id in enumerate(self.response_ids)
        }
        self.response_requires_authority = torch.tensor(
            [response.effector is not None for response in responses],
            device=self.device,
            dtype=torch.bool,
        )
        if responses:
            positions = torch.tensor(
                [
                    (*response.position, response.altitude)
                    if self.spatial_dimensions == 3
                    else response.position
                    for response in responses
                ],
                device=self.device,
                dtype=self.dtype,
            )
            self.response_positions = positions[None, :, :].expand(b, -1, -1).clone()
            self.response_ranges = torch.tensor(
                [response.engagement_range for response in responses],
                device=self.device,
                dtype=self.dtype,
            )[None, :, None]
            self.response_capacity = torch.tensor(
                [response.capacity_per_step for response in responses],
                device=self.device,
                dtype=torch.long,
            )[None, :, None]
            self.response_effectiveness = torch.tensor(
                [response.effectiveness for response in responses],
                device=self.device,
                dtype=self.dtype,
            )[None, :, None]
            self.response_faction_indices = torch.tensor(
                [self.faction_index[response.faction_id] for response in responses],
                device=self.device,
                dtype=torch.long,
            )
            self.response_opponent_mask = self.opponent_matrix[
                self.response_faction_indices[:, None], self.entity_faction_indices[None, :]
            ]
            self.response_sensor_share_mask = (
                self.response_faction_indices[:, None] == self.sensor_faction_indices[None, :]
            ) | self.ally_matrix[
                self.response_faction_indices[:, None], self.sensor_faction_indices[None, :]
            ]
            self.response_faction_mask = torch.stack(
                [
                    self.response_faction_indices == faction_number
                    for faction_number in range(self.faction_count)
                ]
            )
        else:
            self.response_positions = torch.empty(
                (b, 0, self.spatial_dimensions), device=self.device, dtype=self.dtype
            )
            self.response_ranges = torch.empty((1, 0, 1), device=self.device, dtype=self.dtype)
            self.response_capacity = torch.empty((1, 0, 1), device=self.device, dtype=torch.long)
            self.response_effectiveness = torch.empty(
                (1, 0, 1), device=self.device, dtype=self.dtype
            )
            self.response_faction_indices = torch.empty((0,), device=self.device, dtype=torch.long)
            self.response_opponent_mask = torch.empty(
                (0, self.entity_count), device=self.device, dtype=torch.bool
            )
            self.response_sensor_share_mask = torch.empty(
                (0, self.sensor_count), device=self.device, dtype=torch.bool
            )
            self.response_faction_mask = torch.empty(
                (self.faction_count, 0), device=self.device, dtype=torch.bool
            )

    def _set_physics_state(self, state: PhysicsState) -> None:
        self.physics_state = state
        self.positions = state.positions
        self.velocities = state.velocities
        self.orientations = state.orientations
        self.angular_velocities = state.angular_velocities

    def reset(self) -> dict[str, dict[str, torch.Tensor]]:
        b, entity_count = self.batch_size, self.entity_count
        width, height = self.scenario.world.width, self.scenario.world.height
        along = stateless_uniform(
            (b, entity_count), self.seed, 0, SPAWN_ALONG_CHANNEL, device=self.device
        )
        inset = (
            stateless_uniform(
                (b, entity_count), self.seed, 0, SPAWN_INSET_CHANNEL, device=self.device
            )
            * 4.0
        )
        edge = self.start_edge_codes[None, :]
        horizontal = (edge == EDGE_CODES["west"]) | (edge == EDGE_CODES["east"])
        x = torch.where(
            edge == EDGE_CODES["west"],
            inset,
            torch.where(edge == EDGE_CODES["east"], width - inset, along * width),
        )
        y = torch.where(
            edge == EDGE_CODES["south"],
            inset,
            torch.where(edge == EDGE_CODES["north"], height - inset, along * height),
        )
        x = torch.where(horizontal, x, along * width)
        y = torch.where(horizontal, along * height, y)

        position_parts = [x, y]
        if self.spatial_dimensions == 3:
            position_parts.append(self.entity_initial_altitudes.expand(b, -1))
        positions = torch.stack(position_parts, dim=-1).to(self.dtype)
        self._set_physics_state(
            PhysicsState.from_translation(positions, torch.zeros_like(positions))
        )
        self.active = torch.ones((b, entity_count), dtype=torch.bool, device=self.device)
        self.sensor_headings = self.initial_headings.clone()
        self.last_detection_centroids = torch.zeros(
            (b, self.faction_count, self.spatial_dimensions),
            device=self.device,
            dtype=self.dtype,
        )
        self.has_last_detections = torch.zeros(
            (b, self.faction_count), device=self.device, dtype=torch.bool
        )
        self.current_measurements = torch.zeros(
            (b, self.sensor_count, entity_count, self.spatial_dimensions),
            device=self.device,
            dtype=self.dtype,
        )
        self.current_detections = torch.zeros(
            (b, self.sensor_count, entity_count), device=self.device, dtype=torch.bool
        )
        self.delivered_detections = self.current_detections
        self.current_response_success = torch.zeros(
            (b, self.response_count, entity_count), device=self.device, dtype=torch.bool
        )
        self.response_authorizations = torch.zeros(
            (b, self.response_count, entity_count), device=self.device, dtype=torch.bool
        )
        self.current_faction_detections = torch.zeros(
            (b, self.faction_count, entity_count), device=self.device, dtype=torch.bool
        )
        self.track_age = torch.full(
            (b, self.faction_count, entity_count),
            float("inf"),
            device=self.device,
            dtype=self.dtype,
        )
        self.belief_tracks = torch.zeros(
            (b, self.faction_count, entity_count, self.spatial_dimensions),
            device=self.device,
            dtype=self.dtype,
        )
        self.track_confidence = torch.zeros(
            (b, self.faction_count, entity_count),
            device=self.device,
            dtype=self.dtype,
        )
        self.ever_detected = torch.zeros((b, entity_count), device=self.device, dtype=torch.bool)
        self.ever_detected_by_faction = torch.zeros(
            (b, self.faction_count, entity_count), device=self.device, dtype=torch.bool
        )
        self.first_detection_step = torch.full(
            (b, entity_count), -1, device=self.device, dtype=torch.long
        )
        self.first_detection_step_by_faction = torch.full(
            (b, self.faction_count, entity_count),
            -1,
            device=self.device,
            dtype=torch.long,
        )
        self.ever_entered_zone = torch.zeros(
            (b, entity_count), device=self.device, dtype=torch.bool
        )
        self.intercepted = torch.zeros((b, entity_count), device=self.device, dtype=torch.bool)
        self.intercepted_by_faction = torch.zeros(
            (b, self.faction_count, entity_count), device=self.device, dtype=torch.bool
        )
        self.attack_attempted = torch.zeros((b, entity_count), device=self.device, dtype=torch.bool)
        self.attack_succeeded = torch.zeros((b, entity_count), device=self.device, dtype=torch.bool)
        self.current_intercepts = torch.zeros(
            (b, entity_count), device=self.device, dtype=torch.bool
        )
        self.current_intercepts_by_faction = torch.zeros(
            (b, self.faction_count, entity_count), device=self.device, dtype=torch.bool
        )
        self.current_attacks = torch.zeros((b, entity_count), device=self.device, dtype=torch.bool)
        self.current_attack_successes = torch.zeros(
            (b, entity_count), device=self.device, dtype=torch.bool
        )
        self.transit_completed = torch.zeros(
            (b, entity_count), device=self.device, dtype=torch.bool
        )
        self.current_transit_completions = torch.zeros(
            (b, entity_count), device=self.device, dtype=torch.bool
        )
        self.total_detected_slots = torch.zeros((b,), device=self.device, dtype=self.dtype)
        self.total_active_slots = torch.zeros((b,), device=self.device, dtype=self.dtype)
        self.total_detected_slots_by_faction = torch.zeros(
            (b, self.faction_count), device=self.device, dtype=self.dtype
        )
        self.total_active_slots_by_faction = torch.zeros(
            (b, self.faction_count), device=self.device, dtype=self.dtype
        )
        self._dropped_report_count = torch.zeros((b,), device=self.device, dtype=torch.long)
        self._launch_failure_count = torch.zeros((b,), device=self.device, dtype=torch.long)
        self.step_index = 0
        return self._observations()

    def _observations(self) -> dict[str, dict[str, torch.Tensor]]:
        observations: dict[str, dict[str, torch.Tensor]] = {}
        for faction_id, faction_number in self.faction_index.items():
            sensor_mask = self.sensor_faction_indices == faction_number
            detected = torch.isfinite(self.track_age[:, faction_number, :])
            tracks = self.belief_tracks[:, faction_number, :, :]
            faction_sensor_positions = self.sensor_positions[:, sensor_mask, :]
            faction_sensor_headings = self.sensor_headings[:, sensor_mask]
            own_indices = self.faction_entity_indices[faction_number]
            observations[faction_id] = {
                "tracks": tracks,
                "track_mask": detected,
                "track_confidence": self.track_confidence[:, faction_number, :],
                "track_age": self.track_age[:, faction_number, :],
                "own_positions": self.positions[:, own_indices, :],
                "own_active": self.active[:, own_indices],
                "sensor_positions": faction_sensor_positions,
                "sensor_headings": faction_sensor_headings,
                "last_detection_centroid": self.last_detection_centroids[:, faction_number, :],
                "has_last_detection": self.has_last_detections[:, faction_number],
            }
        return observations

    def _validated(
        self, binding_id: str, action: torch.Tensor, shape: tuple[int, ...]
    ) -> torch.Tensor:
        if tuple(action.shape) != shape:
            raise ValueError(
                f"action {binding_id!r} must have shape {shape}, got {tuple(action.shape)}"
            )
        action = action.to(device=self.device, dtype=self.dtype)
        if not torch.isfinite(action).all():
            raise ValueError(f"action {binding_id!r} contains non-finite values")
        return action

    def _gather_actions(self, actions: Mapping[str, torch.Tensor]) -> None:
        """Actuator stage: validate commands and project them onto capabilities."""
        expected = set(self.movement_binding_entities) | set(self.sensing_binding_sensors)
        provided = set(actions)
        if provided != expected:
            missing, unknown = sorted(expected - provided), sorted(provided - expected)
            raise ValueError(
                f"actions must cover every binding; missing={missing} unknown={unknown}"
            )

        validated_sensing = {
            binding_id: self._validated(
                binding_id,
                actions[binding_id],
                (self.batch_size, sensor_indices.numel()),
            )
            for binding_id, sensor_indices in self.sensing_binding_sensors.items()
        }
        validated_movement = {
            binding_id: self._validated(
                binding_id,
                actions[binding_id],
                (self.batch_size, entity_indices.numel(), self.spatial_dimensions),
            )
            for binding_id, entity_indices in self.movement_binding_entities.items()
        }

        headings = self.sensor_headings.clone()
        sensing_saturation = torch.zeros((self.batch_size,), device=self.device, dtype=torch.long)
        for binding_id, sensor_indices in self.sensing_binding_sensors.items():
            desired = validated_sensing[binding_id]
            limits = self.sensor_slew_limits[:, sensor_indices]
            limited = torch.isfinite(limits)
            current = headings[:, sensor_indices]
            delta = wrap_angle(desired - current)
            slewed = current + torch.clamp(delta, -limits, limits)
            headings[:, sensor_indices] = torch.where(limited, slewed, desired)
            sensing_saturation += (limited & (delta.abs() > limits)).sum(dim=1)
        movement_commands = torch.zeros_like(self.velocities)
        movement_saturation = torch.zeros((self.batch_size,), device=self.device, dtype=torch.long)
        for binding_id, entity_indices in self.movement_binding_entities.items():
            command = validated_movement[binding_id]
            norm = torch.linalg.vector_norm(command, dim=-1, keepdim=True)
            over = norm > 1.0
            command = torch.where(over, command / norm.clamp_min(1e-12), command)
            movement_saturation += over.squeeze(-1).sum(dim=1)
            movement_commands[:, entity_indices, :] = command

        self.sensor_headings = headings
        self.movement_commands = movement_commands
        self._movement_saturation = movement_saturation
        self._sensing_saturation = sensing_saturation

    def _disruption_faction_mask(self, faction_ids: list[str] | None) -> torch.Tensor:
        """Resolve a spec's target factions to a ``[faction_count]`` mask.

        ``None`` targets the defending network: the evaluation faction, else
        every faction declaring an opponent or protected relationship — the
        same fallback the aggregate metrics use.
        """
        mask = torch.zeros((self.faction_count,), device=self.device, dtype=torch.bool)
        if faction_ids is None:
            if self.evaluation_faction_index is not None:
                mask[self.evaluation_faction_index] = True
                return mask
            return (self.opponent_matrix | self.protected_matrix).any(dim=1)
        unknown = sorted(set(faction_ids) - set(self.faction_index))
        if unknown:
            raise ValueError(f"disruption names unknown factions: {unknown}")
        for faction_id in faction_ids:
            mask[self.faction_index[faction_id]] = True
        return mask

    def _compile_disruptions(self) -> None:
        """Lower disruption specs onto the compiled sensor/response tensors.

        Multipliers scale tensors once here (zero per-step cost); only the
        two stochastic stages — comms delivery and effector reliability —
        keep per-tick draws, and each stays inert unless a spec covers it,
        so an empty list is bit-identical to no disruption at all.
        """
        sensor_keep = torch.ones((self.sensor_count,), device=self.device, dtype=self.dtype)
        pd_multiplier = torch.ones_like(sensor_keep)
        range_multiplier = torch.ones_like(sensor_keep)
        noise_multiplier = torch.ones_like(sensor_keep)
        effectiveness_multiplier = torch.ones(
            (self.response_count,), device=self.device, dtype=self.dtype
        )
        reliability = torch.ones_like(effectiveness_multiplier)
        for spec in self.disruptions:
            faction_mask = self._disruption_faction_mask(spec.faction_ids)
            if isinstance(spec, CommunicationsDisruption):
                covered = faction_mask[self.sensor_faction_indices]
                sensor_keep = torch.where(
                    covered, sensor_keep * (1.0 - spec.drop_probability), sensor_keep
                )
            elif isinstance(spec, SensorDisruption):
                covered = faction_mask[self.sensor_faction_indices]
                pd_multiplier = torch.where(
                    covered,
                    pd_multiplier * spec.detection_probability_multiplier,
                    pd_multiplier,
                )
                range_multiplier = torch.where(
                    covered, range_multiplier * spec.range_multiplier, range_multiplier
                )
                noise_multiplier = torch.where(
                    covered, noise_multiplier * spec.noise_multiplier, noise_multiplier
                )
            elif isinstance(spec, EffectorDisruption):
                covered = faction_mask[self.response_faction_indices]
                effectiveness_multiplier = torch.where(
                    covered,
                    effectiveness_multiplier * spec.effectiveness_multiplier,
                    effectiveness_multiplier,
                )
                reliability = torch.where(covered, reliability * spec.reliability, reliability)
        self.communication_drop_probability = 1.0 - sensor_keep
        self._communication_disruption_active = bool((sensor_keep < 1.0).any().item())
        self.sensor_pd = self.sensor_pd * pd_multiplier[None, :, None]
        self.sensor_ranges = self.sensor_ranges * range_multiplier[None, :, None]
        self.sensor_noise = self.sensor_noise * noise_multiplier[None, :, None, None]
        self.response_effectiveness = (
            self.response_effectiveness * effectiveness_multiplier[None, :, None]
        )
        self.response_reliability = reliability
        self._effector_reliability_active = bool((reliability < 1.0).any().item())

    def step(self, actions: Mapping[str, torch.Tensor]) -> StepOutput:
        if self.step_index >= self.steps:
            raise RuntimeError("episode already terminated")

        self._gather_actions(actions)
        state = self.physics.advance(
            self.physics_state,
            self.movement_commands,
            self.active,
            self.entity_speeds,
            self.entity_max_accelerations,
            self.world_bounds,
            dt=self.dt,
            substeps=self.scheduler.physics_substeps,
            meters_per_unit=(
                self.scenario.world.meters_per_unit
                if self.scenario.world.meters_per_unit is not None
                else 1.0
            ),
        )
        self._set_physics_state(state)
        self._update_transit_completion()

        if self.scheduler.sensing_due(self.step_index):
            self._apply_sensing()
            self._apply_communication_disruption()
            update_detection_attribution(self)
            update_detection_centroids(self)
        else:
            self.current_detections.zero_()
            self.delivered_detections.zero_()
            self.current_faction_detections.zero_()
            self._dropped_report_count.zero_()
            age_beliefs(self)

        if self.scheduler.effects_due(self.step_index):
            self._apply_responses()
            self._apply_attacks()
        else:
            self.current_response_success.zero_()
            self.current_intercepts.zero_()
            self.current_intercepts_by_faction.zero_()
            self.current_attacks.zero_()
            self.current_attack_successes.zero_()
            self.response_authorizations.zero_()
            self._launch_failure_count.zero_()

        opponent_detected = evaluation_detections(self) & self.opponent_entity_mask[None, :]
        opponent_remaining = self.active & self.opponent_entity_mask[None, :]
        denominator = opponent_detected.sum(dim=1) + (opponent_remaining & ~opponent_detected).sum(
            dim=1
        )
        coverage_gap = 1.0 - opponent_detected.sum(dim=1).to(self.dtype) / denominator.clamp_min(1)
        rewards = self._rewards()

        self.step_index += 1
        terminated = torch.full(
            (self.batch_size,),
            self.step_index >= self.steps,
            device=self.device,
            dtype=torch.bool,
        )
        return StepOutput(
            observations=self._observations(),
            rewards=rewards,
            terminated=terminated,
            info={
                "coverage_gap": coverage_gap,
                "detected_count": opponent_detected.sum(dim=1),
                "intercept_count": self.current_intercepts.sum(dim=1),
                "attack_count": self.current_attacks.sum(dim=1),
                "attack_success_count": self.current_attack_successes.sum(dim=1),
                "movement_saturation_count": self._movement_saturation,
                "sensing_saturation_count": self._sensing_saturation,
                "dropped_report_count": self._dropped_report_count,
                "launch_failure_count": self._launch_failure_count,
            },
        )

    def _apply_sensing(self) -> None:
        relative = self.positions[:, None, :, :] - self.sensor_positions[:, :, None, :]
        distance = torch.linalg.vector_norm(relative, dim=-1)
        bearing = torch.atan2(relative[..., 1], relative[..., 0])
        off_axis = torch.abs(wrap_angle(bearing - self.sensor_headings[..., None]))
        geometrically_visible = (
            (distance <= self.sensor_ranges)
            & (off_axis <= self.sensor_fov * 0.5)
            & self.active[:, None, :]
            & self.cross_faction_sensor_mask[None, :, :]
        )

        ranked_distance = torch.where(
            geometrically_visible, distance, torch.full_like(distance, float("inf"))
        )
        order = torch.argsort(ranked_distance, dim=-1)
        rank = torch.argsort(order, dim=-1)
        within_capacity = rank < self.sensor_capacity
        range_fraction = (distance / self.sensor_ranges.clamp_min(1e-6)).clamp(0.0, 1.0)
        probability = self.sensor_pd * (1.0 - 0.35 * range_fraction)
        random_draw = stateless_uniform(
            tuple(distance.shape),
            self.seed,
            self.step_index,
            SENSING_DETECTION_CHANNEL,
            device=self.device,
        )
        self.current_detections = (
            geometrically_visible & within_capacity & (random_draw < probability)
        )
        noise = stateless_normal(
            (*distance.shape, self.spatial_dimensions),
            self.seed,
            self.step_index,
            MEASUREMENT_NOISE_CHANNEL,
            device=self.device,
        )
        self.current_measurements = self.positions[:, None, :, :] + noise * self.sensor_noise

    def _apply_communication_disruption(self) -> None:
        """Compute the reports that survive the network hop for this tick.

        ``current_detections`` stays what sensors physically saw (analyst
        truth); ``delivered_detections`` is what the network received and is
        what beliefs, responses, and the operator picture consume. Each
        sensor's drop probability was compiled from every communications
        spec covering its faction, so uncovered sensors always deliver.
        """
        if not self._communication_disruption_active:
            self.delivered_detections = self.current_detections
            self._dropped_report_count.zero_()
            return
        delivery_draw = stateless_uniform(
            tuple(self.current_detections.shape),
            self.seed,
            self.step_index,
            COMMS_DELIVERY_CHANNEL,
            device=self.device,
        )
        delivered = delivery_draw >= self.communication_drop_probability[None, :, None]
        self.delivered_detections = self.current_detections & delivered
        self._dropped_report_count = (self.current_detections & ~delivered).sum(dim=(1, 2))

    def _update_transit_completion(self) -> None:
        edge = self.start_edge_codes[None, :]
        completed = (
            ((edge == EDGE_CODES["west"]) & (self.positions[..., 0] >= self.scenario.world.width))
            | ((edge == EDGE_CODES["east"]) & (self.positions[..., 0] <= 0.0))
            | ((edge == EDGE_CODES["north"]) & (self.positions[..., 1] <= 0.0))
            | (
                (edge == EDGE_CODES["south"])
                & (self.positions[..., 1] >= self.scenario.world.height)
            )
        ) & self.transit_mission[None, :]
        self.current_transit_completions = completed & ~self.transit_completed
        self.transit_completed |= completed

    def authorize_effect(self, response_id: str, entity_id: str, *, batch_index: int = 0) -> None:
        """Permit one authority-gated response to act on one entity for one effects tick.

        Responses without a declared ``effector`` are not gated and ignore this
        mask entirely, so legacy scenarios behave exactly as before. The mask is
        consumed by the next ``_apply_responses`` call and never carries over.
        """
        if response_id not in self.response_indices_by_id:
            raise ValueError(f"unknown response {response_id!r}")
        if entity_id not in self.entity_indices_by_id:
            raise ValueError(f"unknown entity {entity_id!r}")
        if not 0 <= batch_index < self.batch_size:
            raise ValueError(f"batch_index {batch_index} is outside the batch")
        response_number = self.response_indices_by_id[response_id]
        if not bool(self.response_requires_authority[response_number].item()):
            raise ValueError(f"response {response_id!r} declares no typed effector to authorize")
        self.response_authorizations[
            batch_index, response_number, self.entity_indices_by_id[entity_id]
        ] = True

    def _apply_responses(self) -> None:
        if not self.response_count:
            self.current_response_success.zero_()
            self.current_intercepts.zero_()
            self.current_intercepts_by_faction.zero_()
            self._launch_failure_count.zero_()
            return
        detected_for_response = (
            self.delivered_detections[:, None, :, :]
            & self.response_sensor_share_mask[None, :, :, None]
        ).any(dim=2)
        relative = self.positions[:, None, :, :] - self.response_positions[:, :, None, :]
        distance = torch.linalg.vector_norm(relative, dim=-1)
        authorized = self.response_authorizations | ~self.response_requires_authority[None, :, None]
        eligible = (
            detected_for_response
            & self.active[:, None, :]
            & self.response_opponent_mask[None, :, :]
            & (distance <= self.response_ranges)
            & authorized
        )
        ranked_distance = torch.where(eligible, distance, torch.full_like(distance, float("inf")))
        order = torch.argsort(ranked_distance, dim=-1)
        rank = torch.argsort(order, dim=-1)
        within_capacity = rank < self.response_capacity
        draw = stateless_uniform(
            tuple(distance.shape),
            self.seed,
            self.step_index,
            RESPONSE_SUCCESS_CHANNEL,
            device=self.device,
        )
        success_candidates = eligible & within_capacity & (draw < self.response_effectiveness)
        if self._effector_reliability_active:
            reliability_draw = stateless_uniform(
                tuple(distance.shape),
                self.seed,
                self.step_index,
                EFFECTOR_RELIABILITY_CHANNEL,
                device=self.device,
            )
            launched = reliability_draw < self.response_reliability[None, :, None]
            self._launch_failure_count = (success_candidates & ~launched).sum(dim=(1, 2))
            success_candidates &= launched
        else:
            self._launch_failure_count.zero_()
        has_success = success_candidates.any(dim=1)
        first_response = success_candidates.to(torch.int8).argmax(dim=1)
        response_numbers = torch.arange(self.response_count, device=self.device, dtype=torch.long)[
            None, :, None
        ]
        claimed_by_response = has_success[:, None, :] & (
            response_numbers == first_response[:, None, :]
        )
        self.current_response_success = success_candidates & claimed_by_response
        self.current_intercepts = self.current_response_success.any(dim=1)
        for faction_number in range(self.faction_count):
            response_mask = self.response_faction_mask[faction_number]
            if response_mask.any():
                self.current_intercepts_by_faction[:, faction_number, :] = (
                    self.current_response_success[:, response_mask, :].any(dim=1)
                )
            else:
                self.current_intercepts_by_faction[:, faction_number, :].zero_()
        self.intercepted_by_faction |= self.current_intercepts_by_faction
        self.intercepted |= self.current_intercepts
        self.active &= ~self.current_intercepts
        self.response_authorizations.zero_()

    def _apply_attacks(self) -> None:
        distance = torch.linalg.vector_norm(self.positions - self.entity_targets, dim=-1)
        in_zone = (
            (distance <= self.entity_target_radii) & self.active & self.attack_mission[None, :]
        )
        self.current_attacks = in_zone
        attack_draw = stateless_uniform(
            tuple(in_zone.shape),
            self.seed,
            self.step_index,
            ATTACK_SUCCESS_CHANNEL,
            device=self.device,
        )
        self.current_attack_successes = in_zone & (attack_draw < self.attack_probability)
        self.ever_entered_zone |= in_zone
        self.attack_attempted |= self.current_attacks
        self.attack_succeeded |= self.current_attack_successes
        self.active &= ~self.current_attacks

    def _rewards(self) -> dict[str, torch.Tensor]:
        return evaluate_rewards(self.scenario, self)
