"""Serialize engine state into analyst replay frames and aggregate metrics.

Presentation lives here, not in the engine: the same evidence files the
operator UI replays are what training evaluation reads to score policies.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import torch

from ..core.env import BatchedScenarioEnv
from ..env.rollout import compute_actions
from ..policies.base import Policy
from ..simulation.cuas_lane import CounterDroneLane, ScheduledDecision
from ..simulation.events import EventKind, SimulationEvent


def frame(env: BatchedScenarioEnv, batch_index: int = 0) -> dict[str, Any]:
    """Copy one environment to a JSON-ready analyst replay frame."""
    positions = env.positions[batch_index].detach().cpu().tolist()
    velocities = env.velocities[batch_index].detach().cpu().tolist()
    include_attitude = env.physics.name == "multirotor_6dof"
    orientations = (
        env.orientations[batch_index].detach().cpu().tolist() if include_attitude else None
    )
    active = env.active[batch_index].detach().cpu().tolist()
    intercepted = env.intercepted[batch_index].detach().cpu().tolist()
    attack_attempted = env.attack_attempted[batch_index].detach().cpu().tolist()
    attack_succeeded = env.attack_succeeded[batch_index].detach().cpu().tolist()
    sensor_headings = env.sensor_headings[batch_index].detach().cpu().tolist()
    current_intercepts = env.current_intercepts[batch_index].detach().cpu()
    current_attacks = env.current_attacks[batch_index].detach().cpu()
    current_attack_successes = env.current_attack_successes[batch_index].detach().cpu()
    current_intercepts_by_faction = env.current_intercepts_by_faction[batch_index].detach().cpu()
    current_transit_completions = env.current_transit_completions[batch_index].detach().cpu()

    def entity_status(index: int) -> str:
        if attack_succeeded[index]:
            return "attack-succeeded"
        if attack_attempted[index]:
            return "attack-failed"
        if intercepted[index]:
            return "intercepted"
        return "active" if active[index] else "inactive"

    detections: list[dict[str, Any]] = []
    event_stream: list[dict[str, Any]] = []
    # Operator-facing reports are the network-delivered picture; the per-entity
    # "detected" flag below stays raw sensor truth for the analyst record.
    detected_matrix = env.delivered_detections[batch_index].detach().cpu()
    measurements = env.current_measurements[batch_index].detach().cpu()
    for sensor_index, sensor in enumerate(env.scenario.sensors):
        indices = torch.nonzero(detected_matrix[sensor_index], as_tuple=False).flatten().tolist()
        for entity_index in indices:
            detections.append(
                {
                    "sensorId": sensor.id,
                    "entityId": env.entity_ids[entity_index],
                    "position": measurements[sensor_index, entity_index].tolist(),
                }
            )
            event_stream.append(
                SimulationEvent(
                    kind=EventKind.DETECTION,
                    step=env.step_index,
                    time_seconds=env.step_index * env.dt,
                    source_faction_id=sensor.faction_id,
                    source_id=sensor.id,
                    target_faction_id=env.entity_faction_ids[entity_index],
                    target_id=env.entity_ids[entity_index],
                    position=tuple(measurements[sensor_index, entity_index].tolist()),
                ).model_dump(mode="json")
            )

    for entity_index in torch.nonzero(current_intercepts, as_tuple=False).flatten().tolist():
        source_faction = next(
            (
                faction_id
                for faction_number, faction_id in enumerate(env.faction_ids)
                if current_intercepts_by_faction[faction_number, entity_index]
            ),
            None,
        )
        event_stream.append(
            SimulationEvent(
                kind=EventKind.INTERCEPT,
                step=env.step_index,
                time_seconds=env.step_index * env.dt,
                source_faction_id=source_faction,
                target_faction_id=env.entity_faction_ids[entity_index],
                target_id=env.entity_ids[entity_index],
                position=tuple(positions[entity_index]),
            ).model_dump(mode="json")
        )
    for entity_index in torch.nonzero(current_attacks, as_tuple=False).flatten().tolist():
        event_stream.append(
            SimulationEvent(
                kind=EventKind.ATTACK,
                step=env.step_index,
                time_seconds=env.step_index * env.dt,
                source_faction_id=env.entity_faction_ids[entity_index],
                source_id=env.entity_ids[entity_index],
                position=tuple(positions[entity_index]),
                attributes={"succeeded": bool(current_attack_successes[entity_index].item())},
            ).model_dump(mode="json")
        )
    for entity_index in (
        torch.nonzero(current_transit_completions, as_tuple=False).flatten().tolist()
    ):
        event_stream.append(
            SimulationEvent(
                kind=EventKind.TRANSIT_COMPLETION,
                step=env.step_index,
                time_seconds=env.step_index * env.dt,
                source_faction_id=env.entity_faction_ids[entity_index],
                source_id=env.entity_ids[entity_index],
                position=tuple(positions[entity_index]),
            ).model_dump(mode="json")
        )

    return {
        "step": env.step_index,
        "time": round(env.step_index * env.dt, 4),
        "truth": [
            {
                "id": env.entity_ids[i],
                "factionId": env.entity_faction_ids[i],
                "groupId": env.entity_group_ids[i],
                "position": position,
                "velocity": velocities[i],
                "active": active[i],
                "status": entity_status(i),
                "detected": bool(env.current_detections[batch_index, :, i].any().item()),
                "enteredZone": bool(env.ever_entered_zone[batch_index, i].item()),
                **({"orientationWxyz": orientations[i]} if include_attitude else {}),
            }
            for i, position in enumerate(positions)
        ],
        "detections": detections,
        "eventStream": event_stream,
        "sensors": [
            {
                "id": sensor.id,
                "factionId": sensor.faction_id,
                "position": env.sensor_positions[batch_index, i].detach().cpu().tolist(),
                "range": sensor.range,
                "fovDegrees": sensor.fov_degrees,
                "headingRadians": sensor_headings[i],
            }
            for i, sensor in enumerate(env.scenario.sensors)
        ],
        "responses": [
            {
                "id": response.id,
                "factionId": response.faction_id,
                "position": env.response_positions[batch_index, i].detach().cpu().tolist(),
                "engagementRange": response.engagement_range,
            }
            for i, response in enumerate(env.scenario.responses)
        ],
        "events": {
            "intercepts": [
                {
                    "entityId": env.entity_ids[i],
                    "position": positions[i],
                    "sourceFactionId": next(
                        (
                            faction_id
                            for faction_number, faction_id in enumerate(env.faction_ids)
                            if current_intercepts_by_faction[faction_number, i]
                        ),
                        None,
                    ),
                }
                for i in torch.nonzero(current_intercepts, as_tuple=False).flatten().tolist()
            ],
            "attacks": [
                {
                    "entityId": env.entity_ids[i],
                    "position": positions[i],
                    "succeeded": bool(current_attack_successes[i].item()),
                }
                for i in torch.nonzero(current_attacks, as_tuple=False).flatten().tolist()
            ],
        },
    }


def metrics(env: BatchedScenarioEnv, batch_index: int = 0) -> dict[str, Any]:
    evaluator = env.evaluation_faction_index
    if evaluator is None:
        total = float(env.total_active_slots[batch_index].item())
        detected_slots = float(env.total_detected_slots[batch_index].item())
        first_detection = env.first_detection_step[batch_index]
        ever_detected = env.ever_detected[batch_index]
        evaluator_intercepts = env.intercepted[batch_index]
    else:
        total = float(env.total_active_slots_by_faction[batch_index, evaluator].item())
        detected_slots = float(env.total_detected_slots_by_faction[batch_index, evaluator].item())
        first_detection = env.first_detection_step_by_faction[batch_index, evaluator]
        ever_detected = env.ever_detected_by_faction[batch_index, evaluator]
        evaluator_intercepts = env.intercepted_by_faction[batch_index, evaluator]
    opponent_mask = env.opponent_entity_mask
    first = first_detection[opponent_mask]
    valid_first = first[first >= 0]
    mean_delay = (
        float(valid_first.to(env.dtype).mean().item() * env.dt) if valid_first.numel() else None
    )
    opponent_intercepts = int((evaluator_intercepts & opponent_mask).sum().item())
    opponent_attacks = int((env.attack_attempted[batch_index] & opponent_mask).sum().item())
    opponent_attack_successes = int(
        (env.attack_succeeded[batch_index] & opponent_mask).sum().item()
    )
    resolved = opponent_intercepts + opponent_attacks

    faction_metrics: dict[str, dict[str, int]] = {}
    for faction_number, faction_id in enumerate(env.faction_ids):
        mask = env.faction_entity_mask[faction_number]
        faction_metrics[faction_id] = {
            "entities": int(mask.sum().item()),
            "active_at_end": int((env.active[batch_index] & mask).sum().item()),
            "ever_detected": int((env.ever_detected[batch_index] & mask).sum().item()),
            "intercepted": int((env.intercepted[batch_index] & mask).sum().item()),
            "attack_attempts": int((env.attack_attempted[batch_index] & mask).sum().item()),
            "attack_successes": int((env.attack_succeeded[batch_index] & mask).sum().item()),
        }

    background_mask = torch.zeros((env.entity_count,), device=env.device, dtype=torch.bool)
    for faction_number, faction in enumerate(env.scenario.factions):
        if faction.category == "background":
            background_mask |= env.faction_entity_mask[faction_number]

    return {
        "detection_rate": round(detected_slots / total, 6) if total else 0.0,
        "coverage_gap": round(1.0 - detected_slots / total, 6) if total else 1.0,
        "opponent_entities": int(opponent_mask.sum().item()),
        "ever_detected": int((ever_detected & opponent_mask).sum().item()),
        "mean_first_detection_seconds": (round(mean_delay, 4) if mean_delay is not None else None),
        "defense_intercepts": opponent_intercepts,
        "attack_attempts": opponent_attacks,
        "attack_successes": opponent_attack_successes,
        "defense_rate": round(opponent_intercepts / resolved, 6) if resolved else 0.0,
        "objective_damage": opponent_attack_successes,
        "active_at_end": int((env.active[batch_index] & opponent_mask).sum().item()),
        "background_entities": int(background_mask.sum().item()),
        "background_active_at_end": int((env.active[batch_index] & background_mask).sum().item()),
        "protected_intercepts": int(
            (evaluator_intercepts & env.protected_entity_mask).sum().item()
        ),
        "factions": faction_metrics,
    }


def recorded_rollout(
    env: BatchedScenarioEnv,
    policies: Mapping[str, Policy],
    *,
    record_frames: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run one full episode and return (frames, metrics) replay evidence."""
    observations = env.reset()
    frames: list[dict[str, Any]] = []
    if record_frames:
        frames.append(frame(env))
    while env.step_index < env.steps:
        output = env.step(compute_actions(policies, observations, env.step_index))
        observations = output.observations
        if record_frames:
            frames.append(frame(env))
    return frames, metrics(env)


def scenario_has_typed_effector(env: BatchedScenarioEnv) -> bool:
    return any(response.effector is not None for response in env.scenario.responses)


def first_divergent_frame(
    parent_frames: Sequence[dict[str, Any]],
    child_frames: Sequence[dict[str, Any]],
    *,
    limit: int,
) -> int | None:
    """Index of the first of ``limit`` frames that differs, or ``None`` if all match."""

    if limit > len(parent_frames) or limit > len(child_frames):
        return min(len(parent_frames), len(child_frames))
    for index in range(limit):
        if _canonical(parent_frames[index]) != _canonical(child_frames[index]):
            return index
    return None


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def cuas_frame(env: BatchedScenarioEnv, lane: CounterDroneLane, *, since: int) -> dict[str, Any]:
    """One analyst frame plus the operator picture and the lane's new evidence.

    The base frame is produced by :func:`frame` and is not modified, so a run
    without a typed effector records byte-identical evidence to before.

    One frame carries one coordinate contract: every ``position`` is in scenario
    world units. Counter-UAS evidence is metric, so its event positions are
    rescaled on the way in; scalars that name their unit (``distance_m``) are
    left alone, and ``CounterDroneCell.replay_evidence`` still reads in meters.
    """
    payload = frame(env)
    payload["tracks"] = lane.operator_tracks(payload["time"])
    payload["decisions"] = lane.operator_requests()
    payload["eventStream"] = [
        *payload["eventStream"],
        *(_in_world_units(event, lane) for event in lane.cell.replay_evidence(since=since)),
    ]
    return payload


def _in_world_units(event: dict[str, Any], lane: CounterDroneLane) -> dict[str, Any]:
    if event["position"] is None:
        return event
    return {**event, "position": lane.to_world_units(tuple(event["position"]))}


def recorded_cuas_rollout(
    env: BatchedScenarioEnv,
    policies: Mapping[str, Policy],
    *,
    decisions: Sequence[ScheduledDecision] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run one episode through the counter-UAS lane and record its evidence.

    Each frame carries the analyst truth :func:`frame` already recorded plus the
    operator track picture, the authority queue, and the counter-UAS events that
    occurred since the previous frame. Scheduled decisions are replayed at their
    declared step, which is what makes a child run reproduce its parent exactly
    up to the branch point.
    """
    lane = CounterDroneLane(env, decisions=list(decisions))
    observations = env.reset()
    frames = [cuas_frame(env, lane, since=0)]
    cursor = lane.cell.event_count
    while env.step_index < env.steps:
        label = env.step_index + 1
        lane.before_step(label)
        output = env.step(compute_actions(policies, observations, env.step_index))
        observations = output.observations
        lane.after_step(label)
        frames.append(cuas_frame(env, lane, since=cursor))
        cursor = lane.cell.event_count
    return frames, {**metrics(env), "counter_uas": lane.metrics()}
