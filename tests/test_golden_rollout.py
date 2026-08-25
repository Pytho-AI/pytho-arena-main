"""Contract tests pinning the corrected engine's deterministic rollout.

The compact fixture stores a canonical digest rather than duplicating every
replay frame in the repository. Any intentional dynamics change must update the
digest explicitly, so replay evidence stays stable across unrelated refactors.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pytho_arena.core.env import BatchedScenarioEnv
from pytho_arena.env.adapters import ParallelArenaEnv
from pytho_arena.env.rollout import compute_actions
from pytho_arena.policies import build_policies
from pytho_arena.scenario.models import default_scenario
from pytho_arena.server.replay import recorded_rollout

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "golden_rollout.json"


def test_scripted_rollout_reproduces_golden_fixture_exactly():
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    env = BatchedScenarioEnv(
        default_scenario(), batch_size=1, seed=golden["seed"], device=golden["device"]
    )
    frames, metrics = recorded_rollout(env, build_policies(env))
    canonical = json.dumps(
        {"frames": frames, "metrics": metrics},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert len(frames) == golden["frame_count"]
    assert hashlib.sha256(canonical).hexdigest() == golden["sha256"]


def test_parallel_adapter_exposes_binding_agents():
    scenario = default_scenario()
    arena = ParallelArenaEnv(scenario, batch_size=2, device="cpu")
    policies = build_policies(arena.env)

    observations, _ = arena.reset()
    assert set(arena.agents) == {"red-movement", "blue-sensing", "neutral-movement"}
    assert arena.trainable_agents == ["red-movement", "blue-sensing"]
    assert set(observations) == set(arena.agents)
    assert observations["red-movement"]["own_positions"].shape[0] == 2

    actions = compute_actions(policies, arena.env._observations(), arena.env.step_index)
    observations, rewards, terminations, truncations, _ = arena.step(actions)
    assert set(rewards) == set(arena.agents)
    assert all(reward.shape == (2,) for reward in rewards.values())
    assert all(not termination.any() for termination in terminations.values())
    assert all(not truncation.any() for truncation in truncations.values())
