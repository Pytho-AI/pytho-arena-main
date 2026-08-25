"""Stateless deterministic pseudo-random helpers keyed by (seed, step, channel)."""

from __future__ import annotations

import math

import torch

# Channel registry: every stochastic stage owns one constant so new streams
# can never collide with an existing one. stateless_normal consumes channel
# and channel + 1, so paired channels stay two apart.
SPAWN_ALONG_CHANNEL = 1
SPAWN_INSET_CHANNEL = 2
SENSING_DETECTION_CHANNEL = 10
MEASUREMENT_NOISE_CHANNEL = 20  # also consumes 21 via stateless_normal
RESPONSE_SUCCESS_CHANNEL = 30
ATTACK_SUCCESS_CHANNEL = 40
COMMS_DELIVERY_CHANNEL = 50
EFFECTOR_RELIABILITY_CHANNEL = 60

_UINT64_MASK = (1 << 64) - 1


def _mix64(value: int) -> int:
    """SplitMix64 finalizer executed with exact Python integer arithmetic."""
    value = (value + 0x9E3779B97F4A7C15) & _UINT64_MASK
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _UINT64_MASK
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _UINT64_MASK
    return (value ^ (value >> 31)) & _UINT64_MASK


def _stream_seed(seed: int, step: int, channel: int) -> int:
    key = seed & _UINT64_MASK
    key ^= ((step + 1) * 0xD2B74407B1CE6E93) & _UINT64_MASK
    key ^= ((channel + 1) * 0xCA5A826395121157) & _UINT64_MASK
    return _mix64(key)


def stateless_uniform(
    shape: tuple[int, ...],
    seed: int,
    step: int,
    channel: int,
    *,
    device: torch.device,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Generate a device-local deterministic stream without touching global RNG state."""
    generator = torch.Generator(device=device)
    generator.manual_seed(_stream_seed(seed, step, channel))
    return torch.rand(shape, generator=generator, device=device, dtype=dtype)


def stateless_normal(
    shape: tuple[int, ...],
    seed: int,
    step: int,
    channel: int,
    *,
    device: torch.device,
) -> torch.Tensor:
    u1 = stateless_uniform(shape, seed, step, channel, device=device).clamp_min(1e-6)
    u2 = stateless_uniform(shape, seed, step, channel + 1, device=device)
    return torch.sqrt(-2.0 * torch.log(u1)) * torch.cos(2.0 * math.pi * u2)


def wrap_angle(angle: torch.Tensor) -> torch.Tensor:
    return torch.atan2(torch.sin(angle), torch.cos(angle))
