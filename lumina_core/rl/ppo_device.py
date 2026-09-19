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


def _resolve_ppo_n_envs() -> int:
    """Re-export: VecEnv width lives with the factory (lungs CUDA profile)."""
    from lumina_core.rl.ppo_vec_env import _resolve_ppo_n_envs as _impl

    return _impl()


def _scale_timesteps_for_device(timesteps: int) -> int:
    """Return requested timesteps unchanged.

    CUDA must select the device, not double env steps. Birth PPO is
    CPU-env bound; doubling made a faster GPU take longer wall-clock.
    """
    return max(1, int(timesteps))


__all__ = ["_resolve_ppo_device", "_scale_timesteps_for_device", "_resolve_ppo_n_envs"]
