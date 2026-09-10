"""Birth PPO VecEnv factory — DummyVecEnv on CUDA, single env otherwise."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment
from lumina_core.rl.ppo_device import _resolve_ppo_device

logger = get_logger("lumina.rl.ppo_vec")

_GPU_N_ENVS_CAP = 8
_MIN_N_STEPS = 64


def _resolve_ppo_n_envs() -> int:
    """Lungs VecEnv width. CUDA + gpu_accelerated → 2–8; else 1 (fail-closed)."""
    if _resolve_ppo_device() != "cuda":
        return 1
    try:
        from lumina_core.hardware_intelligence import get_or_create_hardware_profile

        payload = get_or_create_hardware_profile()
        if str(payload.get("profile") or "").strip().lower() != "gpu_accelerated":
            return 1
        detection = payload.get("detection") if isinstance(payload.get("detection"), dict) else {}
        cores = int(detection.get("cpu_cores") or 8)
    except Exception:
        return 1
    return int(max(2, min(_GPU_N_ENVS_CAP, max(1, cores) // 4)))


def _largest_divisor(value: int, *, cap: int) -> int:
    n = max(1, int(value))
    limit = max(1, min(int(cap), n))
    for candidate in range(limit, 0, -1):
        if n % candidate == 0:
            return candidate
    return 1


def align_ppo_hyperparams(hyper: dict[str, Any], n_envs: int) -> dict[str, Any]:
    """Keep rollout = n_steps * n_envs; batch_size must divide rollout."""
    out = dict(hyper)
    envs = max(1, int(n_envs))
    n_steps = max(_MIN_N_STEPS, int(out.get("n_steps", 1024) or 1024))
    if envs > 1:
        n_steps = max(_MIN_N_STEPS, n_steps // envs)
    rollout = n_steps * envs
    preferred = int(out.get("batch_size", 256) or 256)
    batch = preferred if rollout % preferred == 0 else _largest_divisor(rollout, cap=preferred)
    out["n_steps"] = n_steps
    out["batch_size"] = max(1, batch)
    return out


def make_birth_ppo_env(
    *,
    engine: Any,
    bars: list[dict[str, Any]],
    rl_cfg: RLConfig,
    dna_hash: str | None,
    n_envs: int,
) -> Any:
    """One Gym env, or DummyVecEnv of n copies (shared bars, private config/state)."""

    def _factory() -> RLTradingEnvironment:
        env = RLTradingEnvironment(engine, bars, config=replace(rl_cfg))
        if dna_hash:
            env.set_dna_hash(str(dna_hash))
        return env

    width = max(1, int(n_envs))
    if width <= 1:
        return _factory()
    try:
        from stable_baselines3.common.vec_env import DummyVecEnv
    except ImportError:
        logger.warning("ppo.vec_env.dummy_unavailable fallback_n_envs=1")
        return _factory()
    return DummyVecEnv([_factory for _ in range(width)])


def transfer_ppo_policy_weights(source: Any, dest: Any) -> bool:
    """Copy actor-critic weights so VecEnv bursts continue the plant, not a random MLP."""
    src_pol = getattr(source, "policy", None)
    dst_pol = getattr(dest, "policy", None)
    if src_pol is None or dst_pol is None:
        return False
    try:
        dst_pol.load_state_dict(src_pol.state_dict())
        return True
    except Exception:
        logger.warning("ppo.vec_env.weight_transfer_failed", exc_info=True)
        return False


__all__ = [
    "align_ppo_hyperparams",
    "make_birth_ppo_env",
    "transfer_ppo_policy_weights",
    "_resolve_ppo_n_envs",
]
