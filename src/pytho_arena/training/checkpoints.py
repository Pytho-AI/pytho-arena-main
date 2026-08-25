"""Filesystem checkpoint store: trained binding policies as run-selectable ids.

A checkpoint holds the actor state dicts produced by one training job plus the
metadata needed to validate reuse. Runs reference it through the policy
registry as ``checkpoint:<checkpoint_id>``; :meth:`CheckpointStore.loader`
adapts the store to the registry's loader contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import torch

from ..core.env import BatchedScenarioEnv
from ..policies.base import Policy
from ..policies.learned import learned_policy_from_state
from ..scenario.models import PolicyBindingSpec
from ..scenario.store import write_json_atomic
from ..simulation.contracts import environment_contract


class CheckpointStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    @staticmethod
    def _validate_id(checkpoint_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}", checkpoint_id):
            raise ValueError("checkpoint id contains unsupported characters")
        return checkpoint_id

    def save(
        self,
        checkpoint_id: str,
        meta: dict[str, Any],
        policies: dict[str, dict[str, Any]],
    ) -> None:
        checkpoint_id = self._validate_id(checkpoint_id)
        self.root.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self.root / f"{checkpoint_id}.pt"
        temporary_path = checkpoint_path.with_suffix(".pt.tmp")
        torch.save({"policies": policies}, temporary_path)
        temporary_path.replace(checkpoint_path)
        write_json_atomic(self.root / f"{checkpoint_id}.json", meta)

    def meta(self, checkpoint_id: str) -> dict[str, Any]:
        checkpoint_id = self._validate_id(checkpoint_id)
        path = self.root / f"{checkpoint_id}.json"
        if not path.exists():
            raise KeyError(checkpoint_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def list_meta(self) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("*.json"))
        ]

    def load_policies(self, checkpoint_id: str) -> dict[str, dict[str, Any]]:
        checkpoint_id = self._validate_id(checkpoint_id)
        path = self.root / f"{checkpoint_id}.pt"
        if not path.exists():
            raise KeyError(checkpoint_id)
        return torch.load(path, map_location="cpu", weights_only=True)["policies"]

    def build_policy(
        self, env: BatchedScenarioEnv, binding: PolicyBindingSpec, checkpoint_id: str
    ) -> Policy:
        """Rebuild the trained policy for one binding, validating compatibility."""
        try:
            meta = self.meta(checkpoint_id)
            policies = self.load_policies(checkpoint_id)
        except KeyError as exc:
            raise ValueError(f"unknown checkpoint: {checkpoint_id}") from exc
        if meta.get("scenario_id") != env.scenario.scenario_id:
            raise ValueError(
                f"checkpoint {checkpoint_id} was trained on scenario "
                f"{meta.get('scenario_id')!r}, not {env.scenario.scenario_id!r}"
            )
        scenario_hash = env.scenario_hash
        if meta.get("scenario_hash") != scenario_hash:
            raise ValueError(
                f"checkpoint {checkpoint_id} scenario hash does not match the selected "
                "immutable scenario version"
            )
        expected_contract = environment_contract(
            env.scenario, scenario_hash=env.scenario_hash
        ).content_hash()
        stored_contract = meta.get("environment_contract_hash")
        if stored_contract is not None and stored_contract != expected_contract:
            raise ValueError(
                f"checkpoint {checkpoint_id} action/observation contract is incompatible"
            )
        trained_version = meta.get("scenario_version")
        if trained_version is not None and trained_version != env.scenario.version:
            raise ValueError(
                f"checkpoint {checkpoint_id} was trained on scenario version "
                f"{trained_version}, not version {env.scenario.version}"
            )
        payload = policies.get(binding.id)
        if payload is None or payload["role"] != binding.role:
            raise ValueError(
                f"checkpoint {checkpoint_id} has no trained {binding.role} policy "
                f"for binding {binding.id!r}"
            )
        if payload.get("spatial_dimensions", 2) != env.spatial_dimensions:
            raise ValueError(
                f"checkpoint {checkpoint_id} spatial dimensions are incompatible with "
                f"binding {binding.id!r}"
            )
        try:
            return learned_policy_from_state(
                env,
                binding,
                payload["state_dict"],
                policy_id=f"checkpoint:{checkpoint_id}",
            )
        except RuntimeError as exc:
            raise ValueError(
                f"checkpoint {checkpoint_id} is incompatible with binding {binding.id!r}: {exc}"
            ) from exc

    def loader(self):
        """The ``checkpoint_loader`` callable :func:`build_policies` expects."""
        return self.build_policy
