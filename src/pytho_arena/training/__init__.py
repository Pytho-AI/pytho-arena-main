"""Generalized policy-training algorithms, execution, and checkpoints."""

from .checkpoints import CheckpointStore
from .contracts import TrainingAlgorithmDescriptor, TrainingConfig, TrainingResult
from .registry import (
    DEFAULT_ALGORITHM_ID,
    available_training_algorithms,
    normalize_training_config,
    register_training_algorithm,
)
from .session import TrainingSession
from .trainer import train

__all__ = [
    "CheckpointStore",
    "DEFAULT_ALGORITHM_ID",
    "TrainingAlgorithmDescriptor",
    "TrainingConfig",
    "TrainingResult",
    "TrainingSession",
    "available_training_algorithms",
    "normalize_training_config",
    "register_training_algorithm",
    "train",
]
