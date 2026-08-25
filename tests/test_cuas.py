"""Counter-UAS track, authorization, effector, and evidence contracts."""

from __future__ import annotations

import pytest

from pytho_arena.simulation.cuas import (
    CounterDroneCell,
    EffectorKind,
    EffectorSpec,
    EffectOutcome,
    EngagementOutcome,
    EngagementStatus,
    RoeDecision,
    RoeDisposition,
    RoeRequest,
    SensorTrackReport,
    TrackClassification,
    fuse_track,
)


def report(
    *,
    report_id: str,
    sensor_id: str,
    track_id: str = "track-7",
    east_m: float = 0.0,
    confidence: float = 0.5,
    classification: TrackClassification = TrackClassification.UNKNOWN,
    step: int = 20,
    simulation_time_seconds: float = 1.0,
) -> SensorTrackReport:
    return SensorTrackReport(
        report_id=report_id,
        sensor_id=sensor_id,
        track_id=track_id,
        step=step,
        simulation_time_seconds=simulation_time_seconds,
        position_m=(east_m, 10.0, 30.0),
        velocity_mps=(4.0, 0.0, 0.0),
        confidence=confidence,
        classification=classification,
    )


def counter_drone_cell(*, available_uses: int = 1) -> CounterDroneCell:
    return CounterDroneCell(
        [
            EffectorSpec(
                effector_id="jammer-1",
                kind=EffectorKind.RF_JAMMER,
                max_range_m=250.0,
                available_uses=available_uses,
            )
        ]
    )


def ingest_hostile_track(
    cell: CounterDroneCell,
    *,
    east_m: float = 100.0,
    step: int = 20,
    simulation_time_seconds: float = 1.0,
    report_id: str = "radar-20",
) -> None:
    cell.ingest(
        [
            report(
                report_id=report_id,
                sensor_id="radar",
                east_m=east_m,
                confidence=0.9,
                classification=TrackClassification.HOSTILE,
                step=step,
                simulation_time_seconds=simulation_time_seconds,
            )
        ]
    )


def request(cell: CounterDroneCell, *, request_id: str = "roe-1") -> RoeRequest:
    roe_request = RoeRequest(
        request_id=request_id,
        track_id="track-7",
        effector_id="jammer-1",
        requested_by="c2-service",
        rationale="Track is approaching the protected zone",
        step=21,
        simulation_time_seconds=1.05,
    )
    cell.request_engagement(roe_request)
    return roe_request


def decide(
    cell: CounterDroneCell,
    *,
    disposition: RoeDisposition,
    decision_id: str = "decision-1",
    request_id: str = "roe-1",
    step: int = 23,
    simulation_time_seconds: float = 1.15,
    valid_for_seconds: float | None = None,
) -> RoeDecision:
    decision = RoeDecision(
        decision_id=decision_id,
        request_id=request_id,
        operator_id="operator-alvarez",
        disposition=disposition,
        rationale="Visual correlation confirms hostile UAS",
        step=step,
        simulation_time_seconds=simulation_time_seconds,
        valid_for_seconds=valid_for_seconds,
    )
    cell.record_decision(decision)
    return decision


def test_track_fusion_is_confidence_weighted_and_auditable():
    fused = fuse_track(
        [
            report(
                report_id="radar-20",
                sensor_id="radar",
                east_m=0.0,
                confidence=0.8,
                classification=TrackClassification.HOSTILE,
            ),
            report(
                report_id="eo-20",
                sensor_id="eo",
                east_m=100.0,
                confidence=0.2,
                classification=TrackClassification.UNKNOWN,
            ),
        ]
    )

    assert fused.position_m == pytest.approx((20.0, 10.0, 30.0))
    assert fused.velocity_mps == pytest.approx((4.0, 0.0, 0.0))
    assert fused.confidence == pytest.approx(0.84)
    assert fused.classification is TrackClassification.HOSTILE
    assert fused.source_sensor_ids == ("eo", "radar")
    assert fused.evidence_report_ids == ("eo-20", "radar-20")


@pytest.mark.parametrize(
    ("step", "simulation_time_seconds"),
    [(21, 1.0), (20, 1.05)],
)
def test_fusion_rejects_reports_taken_at_different_simulation_times(step, simulation_time_seconds):
    with pytest.raises(ValueError, match="one step and simulation time"):
        fuse_track(
            [
                report(report_id="radar-20", sensor_id="radar"),
                report(
                    report_id="eo-20",
                    sensor_id="eo",
                    step=step,
                    simulation_time_seconds=simulation_time_seconds,
                ),
            ]
        )


def test_stale_report_set_is_dropped_and_the_newer_track_is_retained():
    cell = counter_drone_cell()
    ingest_hostile_track(cell, east_m=100.0, step=30, simulation_time_seconds=1.5)

    retained = cell.ingest(
        [
            report(
                report_id="radar-late-20",
                sensor_id="radar",
                east_m=900.0,
                confidence=0.9,
                step=20,
                simulation_time_seconds=1.0,
            )
        ]
    )

    assert retained.step == 30
    assert retained.position_m == pytest.approx((100.0, 10.0, 30.0))
    assert cell.tracks["track-7"].step == 30
    drop = cell.replay_evidence()[-1]
    assert drop["kind"] == "track_drop"
    assert drop["attributes"]["reason"] == "stale"
    assert drop["attributes"]["dropped_report_ids"] == ["radar-late-20"]
    assert drop["attributes"]["retained_step"] == 30


def test_replayed_report_id_is_dropped_and_recorded():
    cell = counter_drone_cell()
    ingest_hostile_track(cell, east_m=100.0, step=20, simulation_time_seconds=1.0)

    retained = cell.ingest(
        [
            report(
                report_id="radar-20",
                sensor_id="radar",
                east_m=900.0,
                confidence=0.9,
                step=30,
                simulation_time_seconds=1.5,
            )
        ]
    )

    assert retained.step == 20
    assert cell.tracks["track-7"].position_m == pytest.approx((100.0, 10.0, 30.0))
    drop = cell.replay_evidence()[-1]
    assert drop["kind"] == "track_drop"
    assert drop["attributes"]["reason"] == "duplicate_report"


def test_human_roe_gate_and_typed_effector_emit_replay_evidence():
    cell = counter_drone_cell()
    ingest_hostile_track(cell)
    request(cell)

    blocked = cell.engage(
        use_id="use-pending",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=22,
        simulation_time_seconds=1.1,
    )
    assert blocked.status is EngagementStatus.BLOCKED_PENDING_DECISION
    assert blocked.remaining_uses == 1

    decide(cell, disposition=RoeDisposition.AUTHORIZE)
    applied = cell.engage(
        use_id="use-approved",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=24,
        simulation_time_seconds=1.2,
    )

    assert applied.status is EngagementStatus.EFFECT_ACTIVATED
    assert applied.effector_kind is EffectorKind.RF_JAMMER
    assert applied.disposition is RoeDisposition.AUTHORIZE
    assert applied.remaining_uses == 0
    assert applied.evidence_report_ids == ("radar-20",)
    evidence = cell.replay_evidence()
    assert [event["kind"] for event in evidence] == [
        "track_fusion",
        "roe_request",
        "effector_use",
        "roe_decision",
        "effector_use",
    ]
    assert evidence[0]["attributes"]["evidence_report_ids"] == ["radar-20"]
    assert evidence[1]["attributes"]["pinned_track_step"] == 20
    assert evidence[3]["source_id"] == "operator-alvarez"
    assert evidence[3]["attributes"]["disposition"] == "authorize"
    assert evidence[4]["attributes"]["decision_id"] == "decision-1"
    assert all(event["attributes"]["event_id"] for event in evidence)


def test_hold_blocks_the_effect_and_may_be_superseded_by_an_authorization():
    cell = counter_drone_cell()
    ingest_hostile_track(cell)
    request(cell)
    decide(cell, disposition=RoeDisposition.HOLD, decision_id="decision-hold")

    held = cell.engage(
        use_id="use-held",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=24,
        simulation_time_seconds=1.2,
    )
    assert held.status is EngagementStatus.BLOCKED_HELD
    assert held.remaining_uses == 1

    decide(
        cell,
        disposition=RoeDisposition.AUTHORIZE,
        decision_id="decision-authorize",
        step=25,
        simulation_time_seconds=1.25,
    )
    applied = cell.engage(
        use_id="use-after-hold",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=26,
        simulation_time_seconds=1.3,
    )

    assert applied.status is EngagementStatus.EFFECT_ACTIVATED
    decisions = [event for event in cell.replay_evidence() if event["kind"] == "roe_decision"]
    assert [event["attributes"]["disposition"] for event in decisions] == ["hold", "authorize"]
    assert decisions[1]["attributes"]["supersedes_decision_id"] == "decision-hold"


@pytest.mark.parametrize("disposition", [RoeDisposition.AUTHORIZE, RoeDisposition.DENY])
def test_a_terminal_disposition_cannot_be_decided_again(disposition):
    cell = counter_drone_cell()
    ingest_hostile_track(cell)
    request(cell)
    decide(cell, disposition=disposition)

    with pytest.raises(ValueError, match="cannot be decided again"):
        decide(
            cell,
            disposition=RoeDisposition.AUTHORIZE,
            decision_id="decision-2",
            step=25,
            simulation_time_seconds=1.25,
        )


@pytest.mark.parametrize(
    ("disposition", "east_m", "expected_status"),
    [
        (RoeDisposition.DENY, 100.0, EngagementStatus.BLOCKED_DENIED),
        (RoeDisposition.AUTHORIZE, 300.0, EngagementStatus.OUT_OF_RANGE),
    ],
)
def test_denied_decision_and_range_limit_do_not_consume_effector(
    disposition, east_m, expected_status
):
    cell = counter_drone_cell()
    ingest_hostile_track(cell, east_m=east_m)
    request(cell)
    decide(cell, disposition=disposition, step=22, simulation_time_seconds=1.1)

    result = cell.engage(
        use_id="use-1",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=23,
        simulation_time_seconds=1.15,
    )

    assert result.status is expected_status
    assert result.remaining_uses == 1


def test_one_authorization_permits_exactly_one_activation():
    cell = counter_drone_cell(available_uses=2)
    ingest_hostile_track(cell)
    request(cell)
    decide(cell, disposition=RoeDisposition.AUTHORIZE)

    first = cell.engage(
        use_id="use-1",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=24,
        simulation_time_seconds=1.2,
    )
    second = cell.engage(
        use_id="use-2",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=25,
        simulation_time_seconds=1.25,
    )

    assert first.status is EngagementStatus.EFFECT_ACTIVATED
    assert second.status is EngagementStatus.BLOCKED_AUTHORIZATION_SPENT
    assert second.remaining_uses == 1
    assert cell.remaining_uses["jammer-1"] == 1


@pytest.mark.parametrize(
    ("use_time", "expected_status"),
    [
        (1.30, EngagementStatus.EFFECT_ACTIVATED),
        (1.50, EngagementStatus.BLOCKED_EXPIRED),
    ],
)
def test_authorization_expires_after_its_authority_window(use_time, expected_status):
    cell = counter_drone_cell()
    ingest_hostile_track(cell)
    request(cell)
    decide(cell, disposition=RoeDisposition.AUTHORIZE, valid_for_seconds=0.2)

    result = cell.engage(
        use_id="use-1",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=26,
        simulation_time_seconds=use_time,
    )

    assert result.status is expected_status


def test_engagement_aims_at_the_current_track_and_pins_the_authorized_evidence():
    cell = counter_drone_cell()
    ingest_hostile_track(cell, east_m=100.0, step=20, simulation_time_seconds=1.0)
    request(cell)
    decide(cell, disposition=RoeDisposition.AUTHORIZE)
    ingest_hostile_track(
        cell,
        east_m=200.0,
        step=30,
        simulation_time_seconds=1.5,
        report_id="radar-30",
    )

    result = cell.engage(
        use_id="use-1",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=31,
        simulation_time_seconds=1.55,
    )

    assert cell.tracks["track-7"].position_m[0] == pytest.approx(200.0)
    assert result.status is EngagementStatus.EFFECT_ACTIVATED
    assert result.distance_m == pytest.approx(202.485, abs=1e-3)
    assert result.authorized_offset_m == pytest.approx(100.0)
    assert result.pinned_track_step == 20
    assert result.evidence_report_ids == ("radar-20",)


def test_an_authorized_track_that_leaves_the_envelope_is_out_of_range():
    cell = counter_drone_cell()
    ingest_hostile_track(cell, east_m=100.0, step=20, simulation_time_seconds=1.0)
    request(cell)
    decide(cell, disposition=RoeDisposition.AUTHORIZE)
    ingest_hostile_track(
        cell,
        east_m=3_000.0,
        step=30,
        simulation_time_seconds=1.5,
        report_id="radar-30",
    )

    result = cell.engage(
        use_id="use-1",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=31,
        simulation_time_seconds=1.55,
    )

    assert result.status is EngagementStatus.OUT_OF_RANGE
    assert result.remaining_uses == 1
    assert result.authorized_offset_m == pytest.approx(2_900.0)


def test_effect_cannot_be_timestamped_before_its_decision():
    cell = counter_drone_cell()
    ingest_hostile_track(cell)
    request(cell)
    decide(cell, disposition=RoeDisposition.AUTHORIZE, step=23, simulation_time_seconds=1.15)

    with pytest.raises(ValueError, match="cannot predate its ROE decision"):
        cell.engage(
            use_id="use-1",
            request_id="roe-1",
            effector_position_m=(0.0, 0.0, 0.0),
            step=22,
            simulation_time_seconds=1.1,
        )


def test_decision_ids_are_unique_across_requests():
    cell = counter_drone_cell()
    ingest_hostile_track(cell)
    request(cell, request_id="roe-1")
    request(cell, request_id="roe-2")
    decide(cell, disposition=RoeDisposition.HOLD, decision_id="decision-1", request_id="roe-1")

    with pytest.raises(ValueError, match="duplicate ROE decision"):
        decide(
            cell,
            disposition=RoeDisposition.AUTHORIZE,
            decision_id="decision-1",
            request_id="roe-2",
        )


def test_event_ids_are_stable_for_identical_evidence_and_differ_otherwise():
    def build(rationale: str) -> list[str]:
        cell = counter_drone_cell()
        ingest_hostile_track(cell)
        cell.request_engagement(
            RoeRequest(
                request_id="roe-1",
                track_id="track-7",
                effector_id="jammer-1",
                requested_by="c2-service",
                rationale=rationale,
                step=21,
                simulation_time_seconds=1.05,
            )
        )
        decide(cell, disposition=RoeDisposition.AUTHORIZE)
        cell.engage(
            use_id="use-1",
            request_id="roe-1",
            effector_position_m=(0.0, 0.0, 0.0),
            step=24,
            simulation_time_seconds=1.2,
        )
        return [event.attributes["event_id"] for event in cell.events]

    baseline = build("Track is approaching the protected zone")
    assert build("Track is approaching the protected zone") == baseline
    assert len(set(baseline)) == len(baseline)
    diverged = build("Track turned toward the flight line")
    assert diverged[0] == baseline[0]
    assert diverged[1] != baseline[1]


def test_effect_outcome_is_recorded_by_the_engine_not_claimed_by_activation():
    cell = counter_drone_cell()
    ingest_hostile_track(cell)
    request(cell)
    decide(cell, disposition=RoeDisposition.AUTHORIZE)
    activation = cell.engage(
        use_id="use-1",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=24,
        simulation_time_seconds=1.2,
    )
    assert activation.status is EngagementStatus.EFFECT_ACTIVATED
    assert "use-1" not in cell.outcomes

    cell.record_outcome(
        EngagementOutcome(
            use_id="use-1",
            outcome=EffectOutcome.DEGRADED,
            step=26,
            simulation_time_seconds=1.3,
            detail="Control link degraded; track continued on course",
        )
    )

    outcome_event = cell.replay_evidence()[-1]
    assert outcome_event["kind"] == "effect_outcome"
    assert outcome_event["attributes"]["outcome"] == "degraded"
    assert outcome_event["attributes"]["request_id"] == "roe-1"
    assert outcome_event["attributes"]["decision_id"] == "decision-1"
    assert cell.outcomes["use-1"].outcome is EffectOutcome.DEGRADED


def test_outcome_requires_an_activated_effect():
    cell = counter_drone_cell()
    ingest_hostile_track(cell)
    request(cell)
    cell.engage(
        use_id="use-pending",
        request_id="roe-1",
        effector_position_m=(0.0, 0.0, 0.0),
        step=22,
        simulation_time_seconds=1.1,
    )

    with pytest.raises(ValueError, match="did not activate an effect"):
        cell.record_outcome(
            EngagementOutcome(
                use_id="use-pending",
                outcome=EffectOutcome.DEFEATED,
                step=23,
                simulation_time_seconds=1.15,
            )
        )


def test_replay_evidence_cursor_returns_only_new_events():
    cell = counter_drone_cell()
    ingest_hostile_track(cell)
    cursor = cell.event_count

    request(cell)
    decide(cell, disposition=RoeDisposition.DENY)

    assert cursor == 1
    assert [event["kind"] for event in cell.replay_evidence(since=cursor)] == [
        "roe_request",
        "roe_decision",
    ]
    assert len(cell.replay_evidence()) == 3
    assert cell.replay_evidence(since=cell.event_count) == []
