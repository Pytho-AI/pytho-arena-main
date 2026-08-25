"""Device selection shared by the engine, adapters, and server."""

from __future__ import annotations

import ctypes
import platform

import torch


def _rosetta_translated() -> bool:
    """True when this is an x86_64 Python emulated on Apple Silicon."""
    if platform.system() != "Darwin" or platform.machine() != "x86_64":
        return False
    try:
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        value = ctypes.c_int(0)
        size = ctypes.c_size_t(ctypes.sizeof(value))
        status = libc.sysctlbyname(
            b"sysctl.proc_translated", ctypes.byref(value), ctypes.byref(size), None, 0
        )
        return status == 0 and value.value == 1
    except OSError:
        return False


def mps_usable() -> bool:
    """Whether MPS can actually run, not just whether torch advertises it.

    x86_64 torch builds under Rosetta report MPS as available but segfault the
    process on real engine workloads, so translated processes must stay on CPU.
    """
    return torch.backends.mps.is_available() and not _rosetta_translated()


def select_device(requested: str = "auto") -> torch.device:
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise ValueError("CUDA was requested but is not available")
        return torch.device("cuda")
    if requested == "mps":
        if torch.backends.mps.is_available() and not mps_usable():
            raise ValueError(
                "MPS was requested but this Python is an x86_64 build running "
                "under Rosetta, which crashes on MPS workloads; recreate the "
                "virtualenv with an arm64 Python to use MPS"
            )
        if not torch.backends.mps.is_available():
            raise ValueError("MPS was requested but is not available")
        return torch.device("mps")
    if requested == "cpu":
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device("cuda")
    if mps_usable():
        return torch.device("mps")
    return torch.device("cpu")
