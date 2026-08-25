"""Deterministic track fusion and human-authorized counter-UAS effects.

Coordinate frame: every ``*_m`` and ``*_mps`` vector in this module is scene-local
ENU meters ordered ``(east, north, up)`` from the scenario origin, the same frame
``scenario/models.py`` uses for static assets. No geodetic datum is implied.

Evidence naming: event ``attributes`` keys are snake_case so they match the
``SimulationEvent`` envelope they travel in. Each counter-UAS event carries a
deterministic ``event_id`` in its attributes; identical inputs in identical order
produce identical ids, which is what lets a branched child run prove that its
pre-decision prefix matches its parent.

Authority scope: one :class:`RoeDecision` covers exactly one :class:`RoeRequest`,
which names one track and one effector. Authorizing does not apply an effect, and
activating an effector does not decide its outcome -- the engine reports that
separately through :meth:`CounterDroneCell.record_outcome`.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from .events import EventKind, SimulationEvent

CUAS_CONTRACT_VERSION = 1
COORDINATE_FRAME = "scene_local_enu_m"

Vector3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]


class TrackClassification(StrEnum):
    UNKNOWN = "unknown"
    FRIENDLY = "friendly"
    SUSPECT = "suspect"
    HOSTILE = "hostile"


class EffectorKind(StrEnum):
    RF_JAMMER = "rf_jammer"


class RoeDisposition(StrEnum):
    """Operator disposition for one authority request.

    ``HOLD`` is deliberately non-terminal: it defers the request and a later
    decision may supersede it. ``DENY`` and ``AUTHORIZE`` are terminal.
    """

    HOLD = "hold"
    DENY = "deny"
    AUTHORIZE = "authorize"


class EngagementStatus(StrEnum):
    """Why an effector attempt did or did not activate.

    ``EFFECT_ACTIVATED`` means the effector fired against the authorized track.
    It is not a claim about the effect on that track; see :class:`EffectOutcome`.
    """

    BLOCKED_PENDING_DECISION = "blocked_pending_decision"
    BLOCKED_HELD = "blocked_held"
    BLOCKED_DENIED = "blocked_denied"
    BLOCKED_AUTHORIZATION_SPENT = "blocked_authorization_spent"
    BLOCKED_EXPIRED = "blocked_expired"
    OUT_OF_RANGE = "out_of_range"
    UNAVAILABLE = "unavailable"
    EFFECT_ACTIVATED = "effect_activated"


class EffectOutcome(StrEnum):
    """Authoritative engine result for one activated effector use."""

    NO_EFFECT = "no_effect"
    DEGRADED = "degraded"
    DEFEATED = "defeated"


class TrackUpdateRejection(StrEnum):
    """Why an ingested report set did not become the authoritative track."""

    STALE = "stale"
    DUPLICATE_REPORT = "duplicate_report"


class SensorTrackReport(BaseModel):
    """One sensor's estimate for an already-associated track."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str = Field(min_length=1, max_length=120)
    sensor_id: str = Field(min_length=1, max_length=120)
    track_id: str = Field(min_length=1, max_length=120)
    step: int = Field(ge=0)
    simulation_time_seconds: FiniteFloat = Field(ge=0.0)
    position_m: Vector3
    velocity_mps: Vector3 = (0.0, 0.0, 0.0)
    confidence: FiniteFloat = Field(ge=0.0, le=1.0)
    classification: TrackClassification = TrackClassification.UNKNOWN


class FusedTrack(BaseModel):
    """Track estimate plus the report IDs needed to audit it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    track_id: str
    step: int = Field(ge=0)
    simulation_time_seconds: FiniteFloat = Field(ge=0.0)
    position_m: Vector3
    velocity_mps: Vector3
    confidence: FiniteFloat = Field(ge=0.0, le=1.0)
    classification: TrackClassification
    source_sensor_ids: tuple[str, ...]
    evidence_report_ids: tuple[str, ...]


class EffectorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    effector_id: str = Field(min_length=1, max_length=120)
    kind: EffectorKind
    max_range_m: FiniteFloat = Field(gt=0.0)
    available_uses: int = Field(ge=0)


class RoeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=120)
    track_id: str = Field(min_length=1, max_length=120)
    effector_id: str = Field(min_length=1, max_length=120)
    requested_by: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=500)
    step: int = Field(ge=0)
    simulation_time_seconds: FiniteFloat = Field(ge=0.0)


class RoeDecision(BaseModel):
    """One operator disposition of one request.

    ``valid_for_seconds`` is the authority window measured from
    ``simulation_time_seconds``; ``None`` means the authorization does not expire.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=1, max_length=120)
    request_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    disposition: RoeDisposition
    rationale: str = Field(min_length=1, max_length=500)
    step: int = Field(ge=0)
    simulation_time_seconds: FiniteFloat = Field(ge=0.0)
    valid_for_seconds: FiniteFloat | None = Field(default=None, gt=0.0)

    @property
    def expires_at_seconds(self) -> float | None:
        if self.valid_for_seconds is None:
            return None
        return float(self.simulation_time_seconds) + float(self.valid_for_seconds)


class EngagementResult(BaseModel):
    """One effector attempt, pinned to the evidence that authorized it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    use_id: str
    request_id: str
    decision_id: str | None
    disposition: RoeDisposition | None
    track_id: str
    effector_id: str
    effector_kind: EffectorKind
    status: EngagementStatus
    distance_m: FiniteFloat = Field(ge=0.0)
    remaining_uses: int = Field(ge=0)
    pinned_track_step: int = Field(ge=0)
    #: Distance the track moved between the authorized estimate and this use.
    authorized_offset_m: FiniteFloat = Field(ge=0.0)
    evidence_report_ids: tuple[str, ...]


class EngagementOutcome(BaseModel):
    """Engine-authoritative result of one activated effector use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    use_id: str = Field(min_length=1, max_length=120)
    outcome: EffectOutcome
    step: int = Field(ge=0)
    simulation_time_seconds: FiniteFloat = Field(ge=0.0)
    detail: str = Field(default="", max_length=500)


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return math.sqrt(
        sum((float(left[axis]) - float(right[axis])) ** 2 for axis in range(len(left)))
    )


def fuse_track(reports: Sequence[SensorTrackReport]) -> FusedTrack:
    """Fuse one report per sensor, taken at one simulation time, into one track."""

    if not reports:
        raise ValueError("track fusion requires at least one report")
    track_ids = {report.track_id for report in reports}
    if len(track_ids) != 1:
        raise ValueError("track fusion reports must reference one track_id")
    sensor_ids = [report.sensor_id for report in reports]
    if len(sensor_ids) != len(set(sensor_ids)):
        raise ValueError("track fusion accepts at most one report per sensor")
    report_ids = [report.report_id for report in reports]
    if len(report_ids) != len(set(report_ids)):
        raise ValueError("track fusion report_id values must be unique")
    stamps = {(report.step, float(report.simulation_time_seconds)) for report in reports}
    if len(stamps) != 1:
        raise ValueError("track fusion reports must share one step and simulation time")

    ordered = sorted(reports, key=lambda report: report.report_id)
    weight_sum = sum(float(report.confidence) for report in ordered)
    weights = (
        [float(report.confidence) for report in ordered]
        if weight_sum > 0.0
        else [1.0 for _ in ordered]
    )
    denominator = weight_sum if weight_sum > 0.0 else float(len(ordered))
    position_m = tuple(
        sum(
            weight * float(report.position_m[axis])
            for weight, report in zip(weights, ordered, strict=True)
        )
        / denominator
        for axis in range(3)
    )
    velocity_mps = tuple(
        sum(
            weight * float(report.velocity_mps[axis])
            for weight, report in zip(weights, ordered, strict=True)
        )
        / denominator
        for axis in range(3)
    )
    classification = max(
        ordered,
        key=lambda report: float(report.confidence),
    ).classification
    confidence = 1.0 - math.prod(1.0 - float(report.confidence) for report in ordered)
    step, simulation_time_seconds = next(iter(stamps))
    return FusedTrack(
        track_id=ordered[0].track_id,
        step=step,
        simulation_time_seconds=simulation_time_seconds,
        position_m=position_m,
        velocity_mps=velocity_mps,
        confidence=confidence,
        classification=classification,
        source_sensor_ids=tuple(sorted(sensor_ids)),
        evidence_report_ids=tuple(report.report_id for report in ordered),
    )


class CounterDroneCell:
    """Small C2 state machine with replay-ready evidence for every decision."""

    def __init__(self, effectors: Sequence[EffectorSpec]) -> None:
        if not effectors:
            raise ValueError("counter-drone cell requires at least one effector")
        if len(effectors) != len({effector.effector_id for effector in effectors}):
            raise ValueError("effector_id values must be unique")
        self.effectors = {effector.effector_id: effector for effector in effectors}
        self.remaining_uses = {
            effector.effector_id: effector.available_uses for effector in effectors
        }
        self.tracks: dict[str, FusedTrack] = {}
        self.requests: dict[str, RoeRequest] = {}
        self.decisions: dict[str, RoeDecision] = {}
        self.outcomes: dict[str, EngagementOutcome] = {}
        self.events: list[SimulationEvent] = []
        self.pinned_tracks: dict[str, FusedTrack] = {}
        self._decision_ids: set[str] = set()
        self._use_ids: set[str] = set()
        self._ingested_report_ids: set[str] = set()
        self._spent_authorizations: set[str] = set()

    @property
    def event_count(self) -> int:
        """Cursor a per-frame caller stores to read only the next delta."""

        return len(self.events)

    def _record_event(
        self,
        kind: EventKind,
        *,
        step: int,
        time_seconds: float,
        source_id: str | None = None,
        target_id: str,
        position: Vector3,
        attributes: Mapping[str, Any],
    ) -> None:
        sequence = len(self.events)
        canonical = json.dumps(
            {
                "sequence": sequence,
                "kind": str(kind),
                "step": step,
                "time_seconds": float(time_seconds),
                "source_id": source_id,
                "target_id": target_id,
                "position": [float(value) for value in position],
                "attributes": dict(attributes),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
        self.events.append(
            SimulationEvent(
                kind=kind,
                step=step,
                time_seconds=time_seconds,
                source_id=source_id,
                target_id=target_id,
                position=position,
                attributes={"event_id": f"cuas-{sequence:04d}-{digest}", **attributes},
            )
        )

    def ingest(self, reports: Sequence[SensorTrackReport]) -> FusedTrack:
        """Fuse one same-time report set and return the authoritative track.

        A report set that is not newer than the stored track, or that reuses a
        report id already ingested, is dropped and recorded as an explicit
        ``track_drop`` event; the previously stored track stays authoritative.
        """

        candidate = fuse_track(reports)
        current = self.tracks.get(candidate.track_id)
        rejection: TrackUpdateRejection | None = None
        if any(report.report_id in self._ingested_report_ids for report in reports):
            rejection = TrackUpdateRejection.DUPLICATE_REPORT
        elif current is not None and (
            candidate.step,
            float(candidate.simulation_time_seconds),
        ) <= (current.step, float(current.simulation_time_seconds)):
            rejection = TrackUpdateRejection.STALE

        if rejection is not None:
            retained = current if current is not None else candidate
            self._record_event(
                EventKind.TRACK_DROP,
                step=candidate.step,
                time_seconds=candidate.simulation_time_seconds,
                target_id=candidate.track_id,
                position=retained.position_m,
                attributes={
                    "reason": str(rejection),
                    "dropped_report_ids": list(candidate.evidence_report_ids),
                    "dropped_step": candidate.step,
                    "retained_step": retained.step,
                },
            )
            if current is not None:
                return current
            # A duplicate report id can only exist after a prior accepted ingest of
            # that track, so `current is None` here means the id came from another
            # track. Store nothing and let the caller see the rejected estimate.
            return candidate

        self._ingested_report_ids.update(report.report_id for report in reports)
        self.tracks[candidate.track_id] = candidate
        self._record_event(
            EventKind.TRACK_FUSION,
            step=candidate.step,
            time_seconds=candidate.simulation_time_seconds,
            target_id=candidate.track_id,
            position=candidate.position_m,
            attributes={
                "classification": str(candidate.classification),
                "confidence": float(candidate.confidence),
                "source_sensor_ids": list(candidate.source_sensor_ids),
                "evidence_report_ids": list(candidate.evidence_report_ids),
            },
        )
        return candidate

    def request_engagement(self, request: RoeRequest) -> FusedTrack:
        """Open one authority request and pin the track estimate it is judged on."""

        if request.request_id in self.requests:
            raise ValueError(f"duplicate ROE request {request.request_id!r}")
        if request.track_id not in self.tracks:
            raise ValueError(f"unknown track {request.track_id!r}")
        if request.effector_id not in self.effectors:
            raise ValueError(f"unknown effector {request.effector_id!r}")
        pinned = self.tracks[request.track_id]
        if request.step < pinned.step or (
            request.simulation_time_seconds < pinned.simulation_time_seconds
        ):
            raise ValueError("ROE request cannot predate the track estimate it cites")
        self.requests[request.request_id] = request
        self.pinned_tracks[request.request_id] = pinned
        self._record_event(
            EventKind.ROE_REQUEST,
            step=request.step,
            time_seconds=request.simulation_time_seconds,
            source_id=request.requested_by,
            target_id=request.track_id,
            position=pinned.position_m,
            attributes={
                "request_id": request.request_id,
                "effector_id": request.effector_id,
                "rationale": request.rationale,
                "pinned_track_step": pinned.step,
                "evidence_report_ids": list(pinned.evidence_report_ids),
            },
        )
        return pinned

    def record_decision(self, decision: RoeDecision) -> None:
        """Record one disposition. A hold may be superseded; deny and authorize are final."""

        request = self.requests.get(decision.request_id)
        if request is None:
            raise ValueError(f"unknown ROE request {decision.request_id!r}")
        if decision.decision_id in self._decision_ids:
            raise ValueError(f"duplicate ROE decision {decision.decision_id!r}")
        current = self.decisions.get(decision.request_id)
        if current is not None and current.disposition is not RoeDisposition.HOLD:
            raise ValueError(
                f"ROE request {decision.request_id!r} is already "
                f"{current.disposition.value} and cannot be decided again"
            )
        if (
            decision.step < request.step
            or decision.simulation_time_seconds < request.simulation_time_seconds
        ):
            raise ValueError("ROE decision cannot predate its request")
        if current is not None and (
            decision.step < current.step
            or decision.simulation_time_seconds < current.simulation_time_seconds
        ):
            raise ValueError("ROE decision cannot predate the hold it supersedes")
        pinned = self.pinned_tracks[decision.request_id]
        self.decisions[decision.request_id] = decision
        self._decision_ids.add(decision.decision_id)
        self._record_event(
            EventKind.ROE_DECISION,
            step=decision.step,
            time_seconds=decision.simulation_time_seconds,
            source_id=decision.operator_id,
            target_id=request.track_id,
            position=pinned.position_m,
            attributes={
                "request_id": request.request_id,
                "decision_id": decision.decision_id,
                "disposition": str(decision.disposition),
                "rationale": decision.rationale,
                "valid_for_seconds": (
                    None
                    if decision.valid_for_seconds is None
                    else float(decision.valid_for_seconds)
                ),
                "supersedes_decision_id": None if current is None else current.decision_id,
            },
        )

    def engage(
        self,
        *,
        use_id: str,
        request_id: str,
        effector_position_m: Vector3,
        step: int,
        simulation_time_seconds: FiniteFloat,
    ) -> EngagementResult:
        """Attempt one effector use against the track pinned by its request."""

        if not use_id:
            raise ValueError("use_id must not be empty")
        if use_id in self._use_ids:
            raise ValueError(f"duplicate effector use {use_id!r}")
        if step < 0 or not math.isfinite(float(simulation_time_seconds)):
            raise ValueError("effector use time must be finite and nonnegative")
        if simulation_time_seconds < 0.0:
            raise ValueError("effector use time must be finite and nonnegative")
        if len(effector_position_m) != 3 or not all(
            math.isfinite(float(value)) for value in effector_position_m
        ):
            raise ValueError("effector position must contain three finite values")
        request = self.requests.get(request_id)
        if request is None:
            raise ValueError(f"unknown ROE request {request_id!r}")
        if step < request.step or simulation_time_seconds < request.simulation_time_seconds:
            raise ValueError("effector use cannot predate its ROE request")
        decision = self.decisions.get(request_id)
        if decision is not None and (
            step < decision.step or simulation_time_seconds < decision.simulation_time_seconds
        ):
            raise ValueError("effector use cannot predate its ROE decision")

        # The authorization is pinned to the estimate the operator judged, but the
        # effect is aimed at the current estimate: an authorization aimed at a
        # frozen position could never reach a track that kept moving. How far the
        # track travelled since is recorded, so a reviewer can see the difference.
        pinned = self.pinned_tracks[request_id]
        track = self.tracks.get(request.track_id, pinned)
        effector = self.effectors[request.effector_id]
        distance_m = _distance(track.position_m, effector_position_m)
        expires_at = None if decision is None else decision.expires_at_seconds
        if decision is None:
            status = EngagementStatus.BLOCKED_PENDING_DECISION
        elif decision.disposition is RoeDisposition.HOLD:
            status = EngagementStatus.BLOCKED_HELD
        elif decision.disposition is RoeDisposition.DENY:
            status = EngagementStatus.BLOCKED_DENIED
        elif request_id in self._spent_authorizations:
            status = EngagementStatus.BLOCKED_AUTHORIZATION_SPENT
        elif expires_at is not None and float(simulation_time_seconds) > expires_at:
            status = EngagementStatus.BLOCKED_EXPIRED
        elif distance_m > effector.max_range_m:
            status = EngagementStatus.OUT_OF_RANGE
        elif self.remaining_uses[effector.effector_id] == 0:
            status = EngagementStatus.UNAVAILABLE
        else:
            status = EngagementStatus.EFFECT_ACTIVATED
        remaining_uses = self.remaining_uses[effector.effector_id]
        if status is EngagementStatus.EFFECT_ACTIVATED:
            remaining_uses -= 1

        result = EngagementResult(
            use_id=use_id,
            request_id=request_id,
            decision_id=None if decision is None else decision.decision_id,
            disposition=None if decision is None else decision.disposition,
            track_id=track.track_id,
            effector_id=effector.effector_id,
            effector_kind=effector.kind,
            status=status,
            distance_m=distance_m,
            remaining_uses=remaining_uses,
            pinned_track_step=pinned.step,
            authorized_offset_m=_distance(pinned.position_m, track.position_m),
            evidence_report_ids=pinned.evidence_report_ids,
        )
        self._use_ids.add(use_id)
        self.remaining_uses[effector.effector_id] = remaining_uses
        if status is EngagementStatus.EFFECT_ACTIVATED:
            self._spent_authorizations.add(request_id)
        self._record_event(
            EventKind.EFFECTOR_USE,
            step=step,
            time_seconds=float(simulation_time_seconds),
            source_id=effector.effector_id,
            target_id=track.track_id,
            position=track.position_m,
            attributes=result.model_dump(mode="json"),
        )
        return result

    def record_outcome(self, outcome: EngagementOutcome) -> None:
        """Record the engine's authoritative result for one activated use."""

        activation = next(
            (
                event
                for event in self.events
                if event.kind is EventKind.EFFECTOR_USE
                and event.attributes["use_id"] == outcome.use_id
                and event.attributes["status"] == EngagementStatus.EFFECT_ACTIVATED.value
            ),
            None,
        )
        if activation is None:
            raise ValueError(f"effector use {outcome.use_id!r} did not activate an effect")
        if outcome.use_id in self.outcomes:
            raise ValueError(f"effector use {outcome.use_id!r} already has an outcome")
        if (
            outcome.step < activation.step
            or outcome.simulation_time_seconds < activation.time_seconds
        ):
            raise ValueError("effect outcome cannot predate its effector use")
        self.outcomes[outcome.use_id] = outcome
        self._record_event(
            EventKind.EFFECT_OUTCOME,
            step=outcome.step,
            time_seconds=outcome.simulation_time_seconds,
            source_id=activation.source_id,
            target_id=activation.target_id,
            position=activation.position,
            attributes={
                "use_id": outcome.use_id,
                "request_id": activation.attributes["request_id"],
                "decision_id": activation.attributes["decision_id"],
                "outcome": str(outcome.outcome),
                "detail": outcome.detail,
            },
        )

    def replay_evidence(self, *, since: int = 0) -> list[dict]:
        """Return recorded events from cursor ``since`` onward, oldest first."""

        if since < 0:
            raise ValueError("replay evidence cursor must be nonnegative")
        return [event.model_dump(mode="json") for event in self.events[since:]]
