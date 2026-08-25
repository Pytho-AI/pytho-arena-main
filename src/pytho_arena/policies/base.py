"""The contract every controller satisfies — scripted, learned, human, or remote."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import torch


@runtime_checkable
class Policy(Protocol):
    """One controller for one policy binding.

    ``act`` receives only its own faction's observation dict and the current
    step index, and returns the binding's normalized command tensor: unit-ball
    direction vectors ``[batch, k, D]`` for movement bindings (the engine
    multiplies by declared speed), desired absolute headings in radians
    ``[batch, k]`` for sensing bindings (the engine applies any declared slew
    limit). Out-of-bounds commands are projected by the engine, never obeyed.
    """

    binding_id: str
    faction_id: str
    policy_id: str

    def act(self, observation: dict[str, torch.Tensor], step: int) -> torch.Tensor: ...
