"""PPO device selection helpers (Wave B PR-B4)."""
from __future__ import annotations


def _resolve_ppo_device() -> str:
    """Select CUDA when available; CPU otherwise (BRO PR-N)."""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def _scale_timesteps_for_device(timesteps: int) -> int:
    device = _resolve_ppo_device()
    if device == "cuda":
        return max(int(timesteps), int(timesteps) * 2)
    return int(timesteps)


__all__ = ["_resolve_ppo_device", "_scale_timesteps_for_device"]
