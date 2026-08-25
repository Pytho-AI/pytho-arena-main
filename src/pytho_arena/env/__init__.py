"""RL-facing layer: rollout drivers and multi-agent environment adapters."""

from .adapters import ParallelArenaEnv
from .rollout import compute_actions, episode

__all__ = ["ParallelArenaEnv", "compute_actions", "episode"]
