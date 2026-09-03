"""Extract value / entropy / taken-action margin from a frozen SB3 PPO.

Pure read-only inference. Never calls learn(). Never mutates the executed action.
SYNTHETIC ≡ LIVE: same extraction for both.
"""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

import numpy as np

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.policy_signal_extract")


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _as_1d(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value, dtype=np.float64).reshape(-1)


def _unwrap_policy(model: Any) -> Any:
    if model is None:
        return None
    policy = getattr(model, "policy", None)
    if policy is not None:
        return policy
    inner = getattr(model, "_inner", None)
    return getattr(inner, "policy", None) if inner is not None else None


def _chosen_index(action: Any, n_actions: int) -> int | None:
    if action is None or n_actions < 1:
        return None
    try:
        arr = np.asarray(action).reshape(-1)
        if arr.size <= 0:
            return None
        raw = float(arr[0])
        idx = int(np.clip(np.round(raw), 0, n_actions - 1)) if n_actions <= 3 else int(raw)
        if 0 <= idx < n_actions:
            return idx
    except (TypeError, ValueError, IndexError):
        return None
    return None


def _empty() -> dict[str, float | bool | None]:
    return {
        "open_policy_value": None,
        "open_policy_entropy": None,
        "open_policy_p_chosen": None,
        "open_policy_action_margin": None,
        "open_policy_margin_is_top2": False,
    }


def _fill_from_probs(out: dict[str, float | bool | None], probs: np.ndarray, action: Any) -> None:
    flat = np.asarray(probs, dtype=np.float64).reshape(-1)
    if flat.size < 2:
        return
    chosen = _chosen_index(action, int(flat.size))
    if chosen is None:
        order = np.sort(flat)[::-1]
        out["open_policy_p_chosen"] = _finite(order[0])
        out["open_policy_action_margin"] = _finite(order[0] - order[1])
        out["open_policy_margin_is_top2"] = True
        return
    p_chosen = _finite(flat[chosen])
    others = np.delete(flat, chosen)
    p_other = _finite(np.max(others))
    out["open_policy_p_chosen"] = p_chosen
    if p_chosen is not None and p_other is not None:
        out["open_policy_action_margin"] = _finite(p_chosen - p_other)
    out["open_policy_margin_is_top2"] = False


def _obs_tensor(policy: Any, obs: np.ndarray) -> Any:
    if hasattr(policy, "obs_to_tensor"):
        packed, _ = policy.obs_to_tensor(np.asarray(obs).reshape(1, -1))
        return packed
    try:
        import torch

        return torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
    except Exception:
        return np.asarray(obs, dtype=np.float32).reshape(1, -1)


def _no_grad_ctx() -> Any:
    try:
        import torch

        return torch.no_grad()
    except Exception:
        return nullcontext()


def _maybe_entropy(out: dict[str, float | bool | None], raw: Any) -> None:
    if out["open_policy_entropy"] is not None:
        return
    ent = _as_1d(raw() if callable(raw) else raw)
    if ent.size > 0:
        out["open_policy_entropy"] = _finite(float(np.mean(ent)))


def _read_heads(policy: Any, obs: np.ndarray, action: Any) -> dict[str, float | bool | None]:
    out = _empty()
    obs_t = _obs_tensor(policy, obs)
    if hasattr(policy, "predict_values"):
        try:
            values = policy.predict_values(obs_t)
            flat_v = _as_1d(values)
            if flat_v.size > 0:
                out["open_policy_value"] = _finite(flat_v[0])
        except Exception:
            logger.debug("policy_signal_extract.predict_values.failed", exc_info=True)
    if hasattr(policy, "get_distribution"):
        try:
            dist = policy.get_distribution(obs_t)
            if hasattr(dist, "entropy"):
                _maybe_entropy(out, dist.entropy)
            inner = getattr(dist, "distribution", dist)
            probs = getattr(inner, "probs", None)
            if probs is None:
                probs = getattr(dist, "probs", None)
            if probs is not None:
                _fill_from_probs(out, _as_1d(probs), action)
        except Exception:
            logger.debug("policy_signal_extract.get_distribution.failed", exc_info=True)
    if out["open_policy_entropy"] is None and hasattr(policy, "evaluate_actions") and action is not None:
        try:
            result = policy.evaluate_actions(obs_t, np.asarray(action).reshape(1, -1))
            if isinstance(result, (tuple, list)) and len(result) >= 3:
                _maybe_entropy(out, result[2])
        except Exception:
            logger.debug("policy_signal_extract.evaluate_actions.failed", exc_info=True)
    return out


def extract_policy_signals(
    model: Any,
    obs: np.ndarray | None,
    action: Any | None = None,
) -> dict[str, float | bool | None]:
    """Return open-policy keys for *one* observation.

    Missing / non-finite → ``None`` (never 0.0-as-missing).
    Prefer taken-action margin. Top1−top2 only if ``action`` is None.
    """
    out = _empty()
    if model is None or obs is None:
        return out
    try:
        policy = _unwrap_policy(model)
        if policy is None:
            return out
        was_training = bool(getattr(policy, "training", False))
        if hasattr(policy, "eval"):
            policy.eval()
        try:
            with _no_grad_ctx():
                out.update(_read_heads(policy, np.asarray(obs), action))
        finally:
            if was_training and hasattr(policy, "train"):
                policy.train()
    except Exception:
        logger.debug("policy_signal_extract.failed", exc_info=True)
    return out


__all__ = ["extract_policy_signals"]
