"""Deterministic bridge from engine sensing to the counter-UAS decision cell.

The lane is the only place that turns measurements into an operator picture. It
reads noisy sensor measurements — never truth positions — assigns opaque track
ids in first-detection order, classifies each track from measured kinematics,
opens one authority request per hostile track, applies scheduled operator
decisions, and asks the engine to apply an effect only after a decision
authorized it.

Identification uses two inputs, and the difference matters:

- *Cooperative identification*: entities whose faction the cell's faction has
  declared ``protected`` are labeled friendly. This is scenario-declared
  doctrine (the IFF/flight-plan equivalent), not analyst truth, and it is what
  makes "do not engage protected traffic" a scoreable decision.
- *Measured kinematics*: everything else is unknown, suspect, or hostile purely
  from measured range and closure. The opponent relationship is never read, so
  the operator picture cannot inherit the answer.

Units: the engine works in scenario world units; :mod:`.cuas` works in meters.
Every value crossing this boundary is multiplied by ``world.meters_per_unit``
(1.0 when a scenario does not declare a metric scale).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from .cuas import (
    CounterDroneCell,
    EffectorKind,
    EffectorSpec,
    EffectOutcome,
    EngagementOutcome,
    EngagementStatus,
    FusedTrack,
    RoeDecision,
    RoeDisposition,
    RoeRequest,
    SensorTrackReport,
    TrackClassification,
)
from .events import EventKind

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..core.env import BatchedScenarioEnv

REQUEST_RANGE_MULTIPLIER = 1.5
"""Open the authority request while the track is still outside effector range."""

CLOSING_UPDATES_FOR_HOSTILE = 2
"""Consecutive closing updates before measured kinematics justify `hostile`."""


class ScheduledDecision(BaseModel):
    """One operator disposition replayed at a fixed step of a child run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=120)
    disposition: RoeDisposition
    operator_id: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=500)
    step: int = Field(ge=0)


class _TrackHistory:
    """Per-track measured history the classifier needs, and nothing else."""

    __slots__ = ("closing_updates", "effector_id", "range_m", "updates")

    def __init__(self) -> None:
        self.range_m: float | None = None
        self.closing_updates = 0
        self.updates = 0
        self.effector_id: str | None = None


class CounterDroneLane:
    """Drive one :class:`~.cuas.CounterDroneCell` from one environment's sensing."""

    def __init__(
        self,
        env: BatchedScenarioEnv,
        *,
        decisions: list[ScheduledDecision] | None = None,
        batch_index: int = 0,
    ) -> None:
        typed = [
            (number, response)
            for number, response in enumerate(env.scenario.responses)
            if response.effector is not None
        ]
        if not typed:
            raise ValueError("scenario declares no typed effector; the counter-UAS lane is idle")
        faction_ids = {response.faction_id for _, response in typed}
        if len(faction_ids) != 1:
            raise ValueError("typed effectors must belong to one faction in this slice")
        if not 0 <= batch_index < env.batch_size:
            raise ValueError(f"batch_index {batch_index} is outside the batch")

        self.env = env
        self.batch_index = batch_index
        self.faction_id = next(iter(faction_ids))
        self.faction_number = env.faction_index[self.faction_id]
        self.meters_per_unit = (
            1.0
            if env.scenario.world.meters_per_unit is None
            else float(env.scenario.world.meters_per_unit)
        )
        self.typed_response_numbers = {response.id: number for number, response in typed}
        self.cell = CounterDroneCell(
            [
                EffectorSpec(
                    effector_id=response.id,
                    kind=EffectorKind(response.effector.kind),
                    max_range_m=response.engagement_range * self.meters_per_unit,
                    available_uses=response.effector.available_uses,
                )
                for _, response in typed
            ]
        )
        self.authority_windows = {
            response.id: response.effector.authority_valid_for_seconds for _, response in typed
        }
        self.scheduled_decisions = list(decisions or [])
        self._sensor_numbers = [
            number
            for number, allowed in enumerate(
                env.faction_sensor_access[self.faction_number].tolist()
            )
            if allowed
        ]
        self._cooperative = [
            bool(env.protected_matrix[self.faction_number, faction_number].item())
            for faction_number in env.entity_faction_indices.tolist()
        ]
        self._track_ids: dict[int, str] = {}
        self._entity_numbers: dict[str, int] = {}
        self._history: dict[str, _TrackHistory] = {}
        self._classifications: dict[str, TrackClassification] = {}
        self._requests: dict[str, RoeRequest] = {}
        self._request_by_track: dict[str, str] = {}
        self._last_measurements: dict[tuple[int, int], tuple[float, tuple[float, ...]]] = {}
        self._open_uses: dict[str, tuple[str, int]] = {}
        self._applied_decisions: set[str] = set()
        self._first_detection_seconds: float | None = None
        self._first_hostile_seconds: float | None = None
        self._decision_latencies: list[float] = []
        self._peak_pending = 0
        self._effects_attempted = 0
        self._effects_activated = 0

    # -- engine-facing hooks -------------------------------------------------

    def after_step(self, step: int) -> None:
        """Absorb the sensing and effects of the step that just ran.

        ``step`` is the *frame label* the recorder will stamp on the resulting
        frame, which is ``env.step_index`` after the increment — the same label
        :func:`~pytho_arena.server.replay.frame` gives that step's detections.
        """

        time_seconds = step * self.env.dt
        self._record_outcomes(step, time_seconds)
        self._ingest(step, time_seconds)

    def before_step(self, step: int) -> None:
        """Open requests, apply scheduled decisions, and authorize eligible effects.

        ``step`` is the frame label of the step about to run. Scheduling still
        reads the engine's own pre-increment clock, so effects are authorized on
        exactly the ticks ``_apply_responses`` will run.
        """

        time_seconds = step * self.env.dt
        self._open_requests(step, time_seconds)
        self._apply_scheduled_decisions(step, time_seconds)
        if self.env.scheduler.effects_due(self.env.step_index):
            self._engage(step, time_seconds)
        self._peak_pending = max(self._peak_pending, len(self.pending_request_ids()))

    # -- operator-visible state ----------------------------------------------

    def pending_request_ids(self) -> list[str]:
        """Requests with no terminal disposition, oldest first."""

        return [
            request_id
            for request_id in self._requests
            if self.cell.decisions.get(request_id) is None
            or self.cell.decisions[request_id].disposition is RoeDisposition.HOLD
        ]

    def to_world_units(self, metric: tuple[float, ...]) -> list[float]:
        """Convert a metric vector back to the scenario world units a frame uses."""

        return [metric[axis] / self.meters_per_unit for axis in range(self.env.spatial_dimensions)]

    def operator_tracks(self, time_seconds: float) -> list[dict[str, Any]]:
        """The operator picture: measured tracks, no truth position or faction.

        Positions are scenario world units, matching every other position a
        replay frame carries. The metric values the counter-UAS contract records
        stay in the event stream.
        """

        tracks: list[dict[str, Any]] = []
        for track_id, track in sorted(self.cell.tracks.items()):
            request_id = self._request_by_track.get(track_id)
            decision = None if request_id is None else self.cell.decisions.get(request_id)
            tracks.append(
                {
                    "trackId": track_id,
                    "position": self.to_world_units(track.position_m),
                    "velocity": self.to_world_units(track.velocity_mps),
                    "classification": str(self._classifications[track_id]),
                    "confidence": round(float(track.confidence), 6),
                    "ageSeconds": round(
                        max(0.0, time_seconds - float(track.simulation_time_seconds)), 4
                    ),
                    "sourceSensorIds": list(track.source_sensor_ids),
                    "evidenceReportIds": list(track.evidence_report_ids),
                    "requestId": request_id,
                    "disposition": None if decision is None else str(decision.disposition),
                }
            )
        return tracks

    def operator_requests(self) -> list[dict[str, Any]]:
        """The decision queue: one row per authority request, pending or decided."""

        rows: list[dict[str, Any]] = []
        for request_id, request in self._requests.items():
            decision = self.cell.decisions.get(request_id)
            rows.append(
                {
                    "requestId": request_id,
                    "trackId": request.track_id,
                    "effectorId": request.effector_id,
                    "rationale": request.rationale,
                    "step": request.step,
                    "timeSeconds": round(float(request.simulation_time_seconds), 4),
                    "classification": str(self._classifications[request.track_id]),
                    "disposition": None if decision is None else str(decision.disposition),
                    "decisionId": None if decision is None else decision.decision_id,
                    "decisionStep": None if decision is None else decision.step,
                    "pending": request_id in self.pending_request_ids(),
                }
            )
        return rows

    # -- internals -----------------------------------------------------------

    def _to_meters(self, values: list[float]) -> tuple[float, float, float]:
        scaled = [float(value) * self.meters_per_unit for value in values]
        while len(scaled) < 3:
            scaled.append(0.0)
        return (scaled[0], scaled[1], scaled[2])

    def _effector_position_m(self, effector_id: str) -> tuple[float, float, float]:
        number = self.typed_response_numbers[effector_id]
        return self._to_meters(
            self.env.response_positions[self.batch_index, number].detach().cpu().tolist()
        )

    def _ingest(self, step: int, time_seconds: float) -> None:
        detections = self.env.delivered_detections[self.batch_index]
        measurements = self.env.current_measurements[self.batch_index]
        for entity_number in range(self.env.entity_count):
            reports: list[SensorTrackReport] = []
            for sensor_number in self._sensor_numbers:
                if not bool(detections[sensor_number, entity_number].item()):
                    continue
                sensor = self.env.scenario.sensors[sensor_number]
                position_m = self._to_meters(
                    measurements[sensor_number, entity_number].detach().cpu().tolist()
                )
                track_id = self._assign_track_id(entity_number)
                key = (sensor_number, entity_number)
                previous = self._last_measurements.get(key)
                self._last_measurements[key] = (time_seconds, position_m)
                if previous is None or time_seconds <= previous[0]:
                    velocity_mps = (0.0, 0.0, 0.0)
                else:
                    elapsed = time_seconds - previous[0]
                    velocity_mps = tuple(
                        (position_m[axis] - previous[1][axis]) / elapsed for axis in range(3)
                    )
                sensor_position_m = self._to_meters(
                    self.env.sensor_positions[self.batch_index, sensor_number]
                    .detach()
                    .cpu()
                    .tolist()
                )
                range_m = _distance(position_m, sensor_position_m)
                sensor_range_m = sensor.range * self.meters_per_unit
                range_fraction = min(1.0, range_m / sensor_range_m) if sensor_range_m > 0.0 else 1.0
                reports.append(
                    SensorTrackReport(
                        report_id=f"{sensor.id}-{step:05d}-{track_id}",
                        sensor_id=sensor.id,
                        track_id=track_id,
                        step=step,
                        simulation_time_seconds=time_seconds,
                        position_m=position_m,
                        velocity_mps=velocity_mps,
                        confidence=max(
                            0.0,
                            min(
                                1.0,
                                sensor.detection_probability * (1.0 - 0.35 * range_fraction),
                            ),
                        ),
                        classification=self._classifications.get(
                            track_id, TrackClassification.UNKNOWN
                        ),
                    )
                )
            if not reports:
                continue
            track = self.cell.ingest(reports)
            if track.step != step:
                continue
            if self._first_detection_seconds is None:
                self._first_detection_seconds = time_seconds
            self._classify(track, entity_number, time_seconds)

    def _assign_track_id(self, entity_number: int) -> str:
        track_id = self._track_ids.get(entity_number)
        if track_id is None:
            track_id = f"track-{len(self._track_ids) + 1:03d}"
            self._track_ids[entity_number] = track_id
            self._entity_numbers[track_id] = entity_number
            self._history[track_id] = _TrackHistory()
        return track_id

    def _classify(self, track: FusedTrack, entity_number: int, time_seconds: float) -> None:
        history = self._history[track.track_id]
        history.updates += 1
        effector_id, range_m = self._nearest_effector(track)
        history.effector_id = effector_id
        previous_range = history.range_m
        history.range_m = range_m
        if previous_range is not None and range_m < previous_range:
            history.closing_updates += 1
        else:
            history.closing_updates = 0

        if self._cooperative[entity_number]:
            classification = TrackClassification.FRIENDLY
        else:
            request_range_m = self._request_range_m(effector_id)
            if range_m > request_range_m:
                classification = TrackClassification.UNKNOWN
            elif history.closing_updates >= CLOSING_UPDATES_FOR_HOSTILE:
                classification = TrackClassification.HOSTILE
            else:
                classification = TrackClassification.SUSPECT
        self._classifications[track.track_id] = classification
        if classification is TrackClassification.HOSTILE and self._first_hostile_seconds is None:
            self._first_hostile_seconds = time_seconds

    def _nearest_effector(self, track: FusedTrack) -> tuple[str, float]:
        ranges = {
            effector_id: _distance(track.position_m, self._effector_position_m(effector_id))
            for effector_id in self.typed_response_numbers
        }
        effector_id = min(sorted(ranges), key=lambda key: ranges[key])
        return effector_id, ranges[effector_id]

    def _request_range_m(self, effector_id: str) -> float:
        return self.cell.effectors[effector_id].max_range_m * REQUEST_RANGE_MULTIPLIER

    def _open_requests(self, step: int, time_seconds: float) -> None:
        for track_id, classification in sorted(self._classifications.items()):
            if classification is not TrackClassification.HOSTILE:
                continue
            if track_id in self._request_by_track:
                continue
            effector_id = self._history[track_id].effector_id
            if effector_id is None:
                continue
            request = RoeRequest(
                request_id=f"roe-{len(self._requests) + 1:03d}",
                track_id=track_id,
                effector_id=effector_id,
                requested_by=f"{self.faction_id}-c2",
                rationale=(
                    f"{track_id} closed on {effector_id} for "
                    f"{self._history[track_id].closing_updates} consecutive updates"
                ),
                step=step,
                simulation_time_seconds=time_seconds,
            )
            self.cell.request_engagement(request)
            self._requests[request.request_id] = request
            self._request_by_track[track_id] = request.request_id

    def _apply_scheduled_decisions(self, step: int, time_seconds: float) -> None:
        for scheduled in self.scheduled_decisions:
            if scheduled.step != step or scheduled.request_id in self._applied_decisions:
                continue
            request = self._requests.get(scheduled.request_id)
            if request is None:
                raise ValueError(
                    f"scheduled decision names request {scheduled.request_id!r}, "
                    f"which does not exist at step {step}"
                )
            self.cell.record_decision(
                RoeDecision(
                    decision_id=f"decision-{len(self.cell.decisions) + 1:03d}",
                    request_id=scheduled.request_id,
                    operator_id=scheduled.operator_id,
                    disposition=scheduled.disposition,
                    rationale=scheduled.rationale,
                    step=step,
                    simulation_time_seconds=time_seconds,
                    valid_for_seconds=self.authority_windows[request.effector_id],
                )
            )
            self._applied_decisions.add(scheduled.request_id)
            self._decision_latencies.append(
                round(time_seconds - float(request.simulation_time_seconds), 4)
            )

    def _engage(self, step: int, time_seconds: float) -> None:
        for request_id, request in self._requests.items():
            decision = self.cell.decisions.get(request_id)
            if decision is None or decision.disposition is not RoeDisposition.AUTHORIZE:
                continue
            entity_number = self._entity_numbers[request.track_id]
            if not bool(self.env.active[self.batch_index, entity_number].item()):
                continue
            # Hold the authorization until the track is inside the firing envelope,
            # so one recorded attempt means one trigger pull rather than one tick.
            current = self.cell.tracks.get(request.track_id)
            effector_position_m = self._effector_position_m(request.effector_id)
            if current is None or (
                _distance(current.position_m, effector_position_m)
                > self.cell.effectors[request.effector_id].max_range_m
            ):
                continue
            result = self.cell.engage(
                use_id=f"use-{request_id}-{step:05d}",
                request_id=request_id,
                effector_position_m=effector_position_m,
                step=step,
                simulation_time_seconds=time_seconds,
            )
            self._effects_attempted += 1
            if result.status is not EngagementStatus.EFFECT_ACTIVATED:
                continue
            self._effects_activated += 1
            self.env.authorize_effect(
                request.effector_id,
                self.env.entity_ids[entity_number],
                batch_index=self.batch_index,
            )
            self._open_uses[result.use_id] = (request.effector_id, entity_number)

    def _record_outcomes(self, step: int, time_seconds: float) -> None:
        for use_id, (effector_id, entity_number) in list(self._open_uses.items()):
            response_number = self.typed_response_numbers[effector_id]
            defeated = bool(
                self.env.current_response_success[
                    self.batch_index, response_number, entity_number
                ].item()
            )
            self.cell.record_outcome(
                EngagementOutcome(
                    use_id=use_id,
                    outcome=EffectOutcome.DEFEATED if defeated else EffectOutcome.NO_EFFECT,
                    step=step,
                    simulation_time_seconds=time_seconds,
                    detail=(
                        "Engine adjudicated the authorized effect against the live track"
                        if defeated
                        else "Effector activated; the engine reported no change to the track"
                    ),
                )
            )
            del self._open_uses[use_id]

    # -- after-action ---------------------------------------------------------

    def metrics(self) -> dict[str, Any]:
        """Analyst-side scoring; this is the only place truth may be compared."""

        opponent = self.env.opponent_entity_mask.tolist()
        hostile_tracks = [
            track_id
            for track_id, classification in self._classifications.items()
            if classification is TrackClassification.HOSTILE
        ]
        defeated = [
            outcome
            for outcome in self.cell.outcomes.values()
            if outcome.outcome is EffectOutcome.DEFEATED
        ]
        protected_effects = sum(
            1
            for use_id in self.cell.outcomes
            if self._cooperative[self._entity_numbers[self._track_of_use(use_id)]]
        )
        return {
            "tracks_held": len(self.cell.tracks),
            "requests_opened": len(self._requests),
            "decisions_recorded": len(self.cell.decisions),
            "pending_requests_at_end": len(self.pending_request_ids()),
            "peak_pending_requests": self._peak_pending,
            "effects_attempted": self._effects_attempted,
            "effects_activated": self._effects_activated,
            "effects_defeated": len(defeated),
            "protected_traffic_effects": protected_effects,
            "authority_violations": self._authority_violations(),
            "first_detection_seconds": self._first_detection_seconds,
            "first_hostile_classification_seconds": self._first_hostile_seconds,
            "mean_decision_latency_seconds": (
                round(sum(self._decision_latencies) / len(self._decision_latencies), 4)
                if self._decision_latencies
                else None
            ),
            "hostile_classifications_correct": sum(
                1 for track_id in hostile_tracks if opponent[self._entity_numbers[track_id]]
            ),
            "hostile_classifications_incorrect": sum(
                1 for track_id in hostile_tracks if not opponent[self._entity_numbers[track_id]]
            ),
        }

    def _track_of_use(self, use_id: str) -> str:
        request_id = use_id.removeprefix("use-").rsplit("-", 1)[0]
        return self._requests[request_id].track_id

    def _authority_violations(self) -> int:
        """Activations whose request never carried an authorize disposition."""

        violations = 0
        for event in self.cell.events:
            if event.kind is not EventKind.EFFECTOR_USE:
                continue
            if event.attributes["status"] != EngagementStatus.EFFECT_ACTIVATED.value:
                continue
            if event.attributes["disposition"] != RoeDisposition.AUTHORIZE.value:
                violations += 1
        return violations


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum((float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=True)) ** 0.5


__all__ = ["CounterDroneLane", "ScheduledDecision", "REQUEST_RANGE_MULTIPLIER"]
