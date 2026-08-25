"""Arena side of the cross-repo contract gate: the imported bundle is fresh
against COA, and the generated Python client parses the shared golden
fixtures (including 64-bit ids beyond 2^53)."""

import pathlib
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "contracts-import" / "fixtures"

from pytho.sim.v1 import commands_pb2, projection_pb2, state_pb2  # noqa: E402


def test_contract_clients_are_fresh_against_coa():
    coa = REPO_ROOT.parent / "coa-engine"
    if not (coa / "contracts" / "dist" / "SHA256SUMS").exists():
        pytest.skip("sibling coa-engine checkout not present")
    result = subprocess.run(
        [str(REPO_ROOT / "scripts" / "sync-coa-contracts.sh"), "--check"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"stale contract clients:\n{result.stdout}\n{result.stderr}"


def test_entity_fixture_round_trips_ids_above_2_53():
    entity = state_pb2.EntityState.FromString((FIXTURES / "entity_state.binpb").read_bytes())
    assert entity.entity_id.value == 2**63 + 4242
    reparsed = state_pb2.EntityState.FromString(entity.SerializeToString())
    assert reparsed.entity_id.value == entity.entity_id.value
    assert reparsed.identity.display_name == "Raven UAS Tráck"


def test_command_fixture_carries_the_authorization_oneof():
    cmd = commands_pb2.CommandEnvelope.FromString(
        (FIXTURES / "command_envelope.binpb").read_bytes()
    )
    assert cmd.WhichOneof("payload") == "effect_authorization"
    assert cmd.effect_authorization.request_id == "roe-req-17"


def test_projection_fixture_parses():
    frame = projection_pb2.ProjectionFrame.FromString(
        (FIXTURES / "projection_frame.binpb").read_bytes()
    )
    assert frame.sequence == 2**53 + 99
    assert frame.tracks[0].classification == "hostile-uas"
