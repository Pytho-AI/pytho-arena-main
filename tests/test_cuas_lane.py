"""Counter-UAS lane: operator picture, authority gate, and immutable branch runs."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pytho_arena.core.env import BatchedScenarioEnv
from pytho_arena.policies import build_policies
from pytho_arena.scenario.models import ScenarioSpec
from pytho_arena.server.app import create_app
from pytho_arena.server.replay import first_divergent_frame, recorded_cuas_rollout
from pytho_arena.simulation.cuas_lane import CounterDroneLane, ScheduledDecision
from tests.test_sim import authority_gated, slow_engagement_scenario

DECISION_STEP = 5
FIRST_REQUEST_ID = "roe-001"


def lane_scenario(**effector: object) -> ScenarioSpec:
    return authority_gated(slow_engagement_scenario(), **effector)


def lane_rollout(
    scenario: ScenarioSpec | None = None,
    *,
    decisions: list[ScheduledDecision] | None = None,
) -> tuple[list[dict], dict]:
    env = BatchedScenarioEnv(scenario or lane_scenario(available_uses=4), device="cpu")
    return recorded_cuas_rollout(env, build_policies(env, None), decisions=list(decisions or []))


def authorize(request_id: str = FIRST_REQUEST_ID, step: int = DECISION_STEP) -> ScheduledDecision:
    return ScheduledDecision(
        request_id=request_id,
        disposition="authorize",
        operator_id="operator-alvarez",
        rationale="Inbound track correlated on the flight line",
        step=step,
    )


def events_of(frames: list[dict], kind: str) -> list[dict]:
    return [event for frame in frames for event in frame["eventStream"] if event["kind"] == kind]


def test_pending_authority_leaves_every_typed_effect_closed():
    frames, metrics = lane_rollout()

    assert metrics["defense_intercepts"] == 0
    assert metrics["counter_uas"]["requests_opened"] == 4
    assert metrics["counter_uas"]["effects_attempted"] == 0
    assert metrics["counter_uas"]["pending_requests_at_end"] == 4
    assert metrics["counter_uas"]["authority_violations"] == 0
    assert events_of(frames, "effector_use") == []
    assert frames[-1]["decisions"][0]["pending"] is True


def test_operator_picture_carries_measurements_not_truth():
    frames, _ = lane_rollout()
    truth_ids = {entity["id"] for entity in frames[-1]["truth"]}
    faction_ids = {entity["factionId"] for entity in frames[-1]["truth"]}

    tracks = frames[-1]["tracks"]
    assert tracks
    for track in tracks:
        serialized = json.dumps(track)
        assert track["trackId"].startswith("track-")
        assert not any(entity_id in serialized for entity_id in truth_ids)
        assert not any(faction_id in serialized for faction_id in faction_ids)
        assert track["evidenceReportIds"]


def test_operator_track_position_is_the_measurement_not_the_truth():
    base = slow_engagement_scenario()
    noisy = authority_gated(
        base.model_copy(
            update={"sensors": [base.sensors[0].model_copy(update={"measurement_noise": 0.4})]}
        ),
        available_uses=4,
    )
    frames, _ = lane_rollout(noisy)

    tracks = frames[-1]["tracks"]
    assert tracks
    truth_positions = {tuple(entity["position"]) for entity in frames[-1]["truth"]}
    assert not {tuple(track["position"]) for track in tracks} & truth_positions


def test_cooperative_traffic_is_identified_and_never_requested():
    frames, metrics = lane_rollout()
    tracks = frames[-1]["tracks"]

    friendly = [track for track in tracks if track["classification"] == "friendly"]
    hostile = [track for track in tracks if track["classification"] == "hostile"]
    assert len(friendly) == 2
    assert len(hostile) == 4
    requested = {row["trackId"] for row in frames[-1]["decisions"]}
    assert not requested & {track["trackId"] for track in friendly}
    assert metrics["counter_uas"]["hostile_classifications_incorrect"] == 0
    assert metrics["counter_uas"]["protected_traffic_effects"] == 0


def test_authorized_decision_activates_one_effect_and_the_engine_reports_the_outcome():
    frames, metrics = lane_rollout(decisions=[authorize()])

    uses = events_of(frames, "effector_use")
    outcomes = events_of(frames, "effect_outcome")
    assert len(uses) == 1
    assert uses[0]["attributes"]["status"] == "effect_activated"
    assert uses[0]["attributes"]["disposition"] == "authorize"
    assert len(outcomes) == 1
    assert outcomes[0]["attributes"]["outcome"] == "defeated"
    assert outcomes[0]["attributes"]["request_id"] == FIRST_REQUEST_ID
    assert metrics["defense_intercepts"] == 1
    assert metrics["counter_uas"]["effects_activated"] == 1
    assert metrics["counter_uas"]["mean_decision_latency_seconds"] == 1.0
    assert metrics["counter_uas"]["authority_violations"] == 0


@pytest.mark.parametrize("disposition", ["deny", "hold"])
def test_deny_and_hold_record_the_decision_without_any_effect(disposition):
    decision = authorize().model_copy(update={"disposition": disposition})
    frames, metrics = lane_rollout(decisions=[decision])

    decisions = events_of(frames, "roe_decision")
    assert len(decisions) == 1
    assert decisions[0]["attributes"]["disposition"] == disposition
    assert events_of(frames, "effector_use") == []
    assert metrics["defense_intercepts"] == 0
    assert metrics["counter_uas"]["effects_activated"] == 0


def test_declared_authority_window_reaches_the_decision_record():
    frames, _ = lane_rollout(
        lane_scenario(available_uses=4, authority_valid_for_seconds=0.5),
        decisions=[authorize()],
    )

    decision = events_of(frames, "roe_decision")[0]
    assert decision["attributes"]["valid_for_seconds"] == 0.5


def test_a_decision_naming_an_unopened_request_is_rejected():
    with pytest.raises(ValueError, match="does not exist at step"):
        lane_rollout(decisions=[authorize(request_id="roe-404", step=2)])


def test_two_runs_of_one_decision_produce_identical_evidence():
    first, first_metrics = lane_rollout(decisions=[authorize()])
    second, second_metrics = lane_rollout(decisions=[authorize()])

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first_metrics == second_metrics


def test_a_decision_changes_nothing_before_its_own_step():
    parent, _ = lane_rollout()
    child, _ = lane_rollout(decisions=[authorize()])

    assert first_divergent_frame(parent, child, limit=DECISION_STEP) is None
    assert json.dumps(parent[DECISION_STEP]) != json.dumps(child[DECISION_STEP])


def test_lane_requires_a_typed_effector():
    env = BatchedScenarioEnv(slow_engagement_scenario(), device="cpu")
    with pytest.raises(ValueError, match="no typed effector"):
        CounterDroneLane(env)


@pytest.mark.asyncio
async def test_api_branches_from_a_decision_without_touching_the_parent(tmp_path: Path):
    app = create_app(tmp_path / "data")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            scenario = lane_scenario(available_uses=4).model_copy(
                update={"scenario_id": "lane-scenario"}
            )
            saved = await client.post("/api/scenarios", json=scenario.model_dump(mode="json"))
            assert saved.status_code == 201, saved.text

            run = await client.post(
                "/api/runs",
                json={"scenario_id": "lane-scenario", "scenario_version": 1, "device": "cpu"},
            )
            assert run.status_code == 201, run.text
            parent = run.json()
            assert parent["parent_run_id"] is None
            assert parent["metrics"]["counter_uas"]["requests_opened"] == 4
            assert parent["metrics"]["defense_intercepts"] == 0

            parent_replay = (await client.get(f"/api/runs/{parent['run_id']}/replay")).json()
            pending = parent_replay["frames"][DECISION_STEP]["decisions"]
            assert pending[0]["pending"] is True

            branch = await client.post(
                f"/api/runs/{parent['run_id']}/branches",
                json={
                    "decisions": [
                        {
                            "request_id": pending[0]["requestId"],
                            "disposition": "authorize",
                            "operator_id": "operator-alvarez",
                            "rationale": "Inbound track correlated on the flight line",
                            "step": DECISION_STEP,
                        }
                    ]
                },
            )
            assert branch.status_code == 201, branch.text
            child = branch.json()
            assert child["run_id"] != parent["run_id"]
            assert child["parent_run_id"] == parent["run_id"]
            assert child["seed"] == parent["seed"]
            assert child["scenario_hash"] == parent["scenario_hash"]
            assert child["branch_decisions"][0]["disposition"] == "authorize"
            assert child["metrics"]["defense_intercepts"] == 1
            assert child["metrics"]["counter_uas"]["effects_activated"] == 1

            child_replay = (await client.get(f"/api/runs/{child['run_id']}/replay")).json()
            assert (
                first_divergent_frame(
                    parent_replay["frames"], child_replay["frames"], limit=DECISION_STEP
                )
                is None
            )
            unchanged = (await client.get(f"/api/runs/{parent['run_id']}/replay")).json()
            assert unchanged == parent_replay

            missing = await client.post(
                f"/api/runs/{parent['run_id']}/branches",
                json={
                    "decisions": [
                        {
                            "request_id": pending[0]["requestId"],
                            "disposition": "deny",
                            "operator_id": "operator-chen",
                            "rationale": "Beyond the parent run",
                            "step": 999,
                        }
                    ]
                },
            )
            assert missing.status_code == 400
            assert "outside the parent run" in missing.json()["detail"]

            unknown = await client.post(
                "/api/runs/does-not-exist/branches",
                json={
                    "decisions": [
                        {
                            "request_id": "roe-001",
                            "disposition": "deny",
                            "operator_id": "operator-chen",
                            "rationale": "No such parent",
                            "step": 1,
                        }
                    ]
                },
            )
            assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_api_rejects_a_branch_on_a_scenario_without_a_typed_effector(tmp_path: Path):
    app = create_app(tmp_path / "data")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            scenario = slow_engagement_scenario().model_copy(
                update={"scenario_id": "untyped-scenario"}
            )
            saved = await client.post("/api/scenarios", json=scenario.model_dump(mode="json"))
            assert saved.status_code == 201, saved.text
            run = await client.post(
                "/api/runs",
                json={"scenario_id": "untyped-scenario", "scenario_version": 1, "device": "cpu"},
            )
            assert run.status_code == 201, run.text
            summary = run.json()
            assert "counter_uas" not in summary["metrics"]

            branch = await client.post(
                f"/api/runs/{summary['run_id']}/branches",
                json={
                    "decisions": [
                        {
                            "request_id": "roe-001",
                            "disposition": "authorize",
                            "operator_id": "operator-alvarez",
                            "rationale": "No typed effector exists",
                            "step": 1,
                        }
                    ]
                },
            )
            assert branch.status_code == 400
            assert "no typed effector" in branch.json()["detail"]
