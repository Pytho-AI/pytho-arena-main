"""Empirical-game evaluation over faction policy populations."""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core.env import BatchedScenarioEnv
from ..env.rollout import episode
from ..policies.base import Policy
from ..policies.registry import CheckpointLoader, build_policies
from ..scenario.models import ScenarioSpec
from ..simulation.contracts import environment_contract


class PolicyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=120)
    faction_id: str = Field(min_length=1, max_length=64)
    policy_overrides: dict[str, str] = Field(min_length=1)


class ExperimentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=120)
    scenario_id: str
    scenario_version: int
    scenario_hash: str
    environment_contract_hash: str
    seeds: list[int] = Field(min_length=1, max_length=1_000)
    populations: dict[str, list[PolicyCandidate]]

    @field_validator("seeds")
    @classmethod
    def unique_seeds(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("experiment seeds must be unique")
        return value

    @model_validator(mode="after")
    def validate_populations(self) -> ExperimentManifest:
        candidate_ids: set[str] = set()
        for faction_id, candidates in self.populations.items():
            if not candidates:
                raise ValueError(f"population for faction {faction_id!r} is empty")
            if any(candidate.faction_id != faction_id for candidate in candidates):
                raise ValueError(f"population key {faction_id!r} does not match its candidates")
            for candidate in candidates:
                if candidate.id in candidate_ids:
                    raise ValueError(f"duplicate policy candidate id: {candidate.id}")
                candidate_ids.add(candidate.id)
        return self

    @classmethod
    def for_scenario(
        cls,
        scenario: ScenarioSpec,
        *,
        name: str,
        seeds: list[int],
        populations: dict[str, list[PolicyCandidate]],
    ) -> ExperimentManifest:
        contract = environment_contract(scenario)
        return cls(
            name=name,
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.version,
            scenario_hash=scenario.content_hash(),
            environment_contract_hash=contract.content_hash(),
            seeds=seeds,
            populations=populations,
        )

    def content_hash(self) -> str:
        raw = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(raw).hexdigest()


class MatchupResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidates: dict[str, str]
    seed: int
    faction_returns: dict[str, float]
    policies: dict[str, str]


def _candidate_combinations(
    populations: dict[str, list[PolicyCandidate]],
) -> Iterator[tuple[PolicyCandidate, ...]]:
    ordered = [populations[faction_id] for faction_id in sorted(populations)]
    return itertools.product(*ordered)


def evaluate_population(
    scenario: ScenarioSpec,
    manifest: ExperimentManifest,
    *,
    device: str = "cpu",
    checkpoint_loader: CheckpointLoader | None = None,
) -> list[MatchupResult]:
    """Run the Cartesian policy population over every declared evaluation seed."""
    contract = environment_contract(scenario)
    if (
        manifest.scenario_id != scenario.scenario_id
        or manifest.scenario_version != scenario.version
    ):
        raise ValueError("experiment scenario identity does not match the supplied scenario")
    if manifest.scenario_hash != scenario.content_hash():
        raise ValueError("experiment scenario hash does not match the supplied scenario")
    if manifest.environment_contract_hash != contract.content_hash():
        raise ValueError("experiment environment contract does not match the supplied scenario")

    bindings = {binding.id: binding for binding in scenario.policy_bindings}
    unknown_factions = set(manifest.populations) - set(faction.id for faction in scenario.factions)
    if unknown_factions:
        raise ValueError(f"experiment contains unknown factions: {sorted(unknown_factions)}")
    results: list[MatchupResult] = []
    for candidates in _candidate_combinations(manifest.populations):
        overrides: dict[str, str] = {}
        candidate_ids: dict[str, str] = {}
        for candidate in candidates:
            candidate_ids[candidate.faction_id] = candidate.id
            for binding_id, policy_id in candidate.policy_overrides.items():
                binding = bindings.get(binding_id)
                if binding is None or binding.faction_id != candidate.faction_id:
                    raise ValueError(
                        f"candidate {candidate.id!r} overrides a binding outside its faction"
                    )
                if binding_id in overrides:
                    raise ValueError(f"multiple candidates override binding {binding_id!r}")
                overrides[binding_id] = policy_id

        for seed in manifest.seeds:
            env = BatchedScenarioEnv(scenario, batch_size=1, seed=seed, device=device)
            policies: dict[str, Policy] = build_policies(
                env, overrides, checkpoint_loader=checkpoint_loader
            )
            returns = {faction_id: 0.0 for faction_id in env.faction_ids}
            for output in episode(env, policies):
                for faction_id, reward in output.rewards.items():
                    returns[faction_id] += float(reward[0].item())
            results.append(
                MatchupResult(
                    candidates=candidate_ids,
                    seed=seed,
                    faction_returns=returns,
                    policies={
                        binding_id: policy.policy_id for binding_id, policy in policies.items()
                    },
                )
            )
    return results


def empirical_regret(results: list[MatchupResult], faction_id: str) -> dict[str, float]:
    """Return best-response regret for each candidate from empirical mean returns."""
    totals: dict[str, list[float]] = {}
    for result in results:
        candidate_id = result.candidates.get(faction_id)
        if candidate_id is not None:
            totals.setdefault(candidate_id, []).append(result.faction_returns[faction_id])
    if not totals:
        return {}
    means = {candidate: sum(values) / len(values) for candidate, values in totals.items()}
    best = max(means.values())
    return {candidate: best - value for candidate, value in means.items()}
