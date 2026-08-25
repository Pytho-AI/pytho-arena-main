"""Faction-attributed belief updates and evaluation-view detection metrics."""

from __future__ import annotations

from typing import Protocol

import torch


class BeliefState(Protocol):
    faction_count: int
    step_index: int
    dt: float
    delivered_detections: torch.Tensor
    current_measurements: torch.Tensor
    faction_sensor_access: torch.Tensor
    first_detection_step: torch.Tensor
    first_detection_step_by_faction: torch.Tensor
    ever_detected: torch.Tensor
    ever_detected_by_faction: torch.Tensor
    belief_tracks: torch.Tensor
    current_faction_detections: torch.Tensor
    track_age: torch.Tensor
    track_confidence: torch.Tensor
    active: torch.Tensor
    faction_opponent_entity_mask: torch.Tensor
    opponent_entity_mask: torch.Tensor
    total_detected_slots_by_faction: torch.Tensor
    total_active_slots_by_faction: torch.Tensor
    total_detected_slots: torch.Tensor
    total_active_slots: torch.Tensor
    evaluation_faction_index: int | None
    last_detection_centroids: torch.Tensor
    has_last_detections: torch.Tensor


def evaluation_detections(state: BeliefState) -> torch.Tensor:
    if state.evaluation_faction_index is None:
        return state.delivered_detections.any(dim=1)
    return state.current_faction_detections[:, state.evaluation_faction_index, :]


def age_beliefs(state: BeliefState) -> None:
    finite = torch.isfinite(state.track_age)
    state.track_age = torch.where(finite, state.track_age + state.dt, state.track_age)
    state.track_confidence *= 0.95


def update_detection_attribution(state: BeliefState) -> None:
    """Fuse the network-delivered reports into per-faction beliefs.

    Everything here reads ``delivered_detections`` — the post-communication
    picture — never raw sensor truth, so detection aggregates describe what
    the network knew. Sensor-local truth stays in ``current_detections`` for
    the analyst record.
    """
    detected = state.delivered_detections.any(dim=1)
    newly_detected = detected & (state.first_detection_step < 0)
    state.first_detection_step = torch.where(
        newly_detected,
        torch.full_like(state.first_detection_step, state.step_index),
        state.first_detection_step,
    )
    state.ever_detected |= detected
    for faction_number in range(state.faction_count):
        sensor_mask = state.faction_sensor_access[faction_number]
        detections = state.delivered_detections[:, sensor_mask, :]
        faction_detected = detections.any(dim=1)
        if sensor_mask.any():
            measurements = state.current_measurements[:, sensor_mask, :, :]
            counts = detections.sum(dim=1).clamp_min(1)[..., None]
            measured_tracks = (measurements * detections[..., None]).sum(dim=1) / counts
            state.belief_tracks[:, faction_number, :, :] = torch.where(
                faction_detected[..., None],
                measured_tracks,
                state.belief_tracks[:, faction_number, :, :],
            )
        state.current_faction_detections[:, faction_number, :] = faction_detected
        faction_first = state.first_detection_step_by_faction[:, faction_number, :]
        newly_detected = faction_detected & (faction_first < 0)
        state.first_detection_step_by_faction[:, faction_number, :] = torch.where(
            newly_detected,
            torch.full_like(faction_first, state.step_index),
            faction_first,
        )
        state.ever_detected_by_faction[:, faction_number, :] |= faction_detected
        previous_age = state.track_age[:, faction_number, :]
        state.track_age[:, faction_number, :] = torch.where(
            faction_detected,
            torch.zeros_like(previous_age),
            previous_age + state.dt,
        )
        previous_confidence = state.track_confidence[:, faction_number, :]
        state.track_confidence[:, faction_number, :] = torch.where(
            faction_detected,
            torch.ones_like(previous_confidence),
            previous_confidence * 0.95,
        )
        opponent_active = state.active & state.faction_opponent_entity_mask[faction_number]
        state.total_detected_slots_by_faction[:, faction_number] += (
            faction_detected & opponent_active
        ).sum(dim=1)
        state.total_active_slots_by_faction[:, faction_number] += opponent_active.sum(dim=1)

    evaluator_detected = evaluation_detections(state)
    opponent_active = state.active & state.opponent_entity_mask[None, :]
    state.total_detected_slots += (evaluator_detected & opponent_active).sum(dim=1)
    state.total_active_slots += opponent_active.sum(dim=1)


def update_detection_centroids(state: BeliefState) -> None:
    for faction_number in range(state.faction_count):
        sensor_mask = state.faction_sensor_access[faction_number]
        if not sensor_mask.any():
            continue
        detections = state.delivered_detections[:, sensor_mask, :]
        measurements = state.current_measurements[:, sensor_mask, :, :]
        count = detections.sum(dim=(1, 2)).clamp_min(1)[..., None]
        centroid = (measurements * detections[..., None]).sum(dim=(1, 2)) / count
        has_detection = detections.any(dim=(1, 2))
        state.last_detection_centroids[:, faction_number, :] = torch.where(
            has_detection[:, None],
            centroid,
            state.last_detection_centroids[:, faction_number, :],
        )
        state.has_last_detections[:, faction_number] |= has_detection
