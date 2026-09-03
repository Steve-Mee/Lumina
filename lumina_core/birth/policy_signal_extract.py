"""Extract value / entropy / action-margin from a frozen SB3 PPO at one observation.

Pure read-only inference. Never calls learn(). Never mutates the model.
SYNTHETIC ≡ LIVE: same extraction for both.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.policy_signal_extract")


def extract_policy_signals(model: Any, obs: np.ndarray) -> dict[str, float | None]:
    """Return ``{value, entropy, action_margin}`` for *one* observation.

    All three are best-effort. Missing field → ``None``.
    Never raises: caller must not skip a trade because extraction failed.
    """
    out: dict[str, float | None] = {
        "open_policy_value": None,
        "open_policy_entropy": None,
        "open_policy_action_margin": None,
    }
    if model is None:
        return out
    try:
        import torch

        policy = getattr(model, "policy", None)
        if policy is None:
            return out
        was_training = policy.training
        policy.eval()
        try:
            obs_t = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            if hasattr(policy, "obs_to_tensor"):
                obs_t, _ = policy.obs_to_tensor(obs.reshape(1, -1))
            with torch.no_grad():
                dist = policy.get_distribution(obs_t)
                values = policy.predict_values(obs_t)
                out["open_policy_value"] = float(values.cpu().item())
                ent = dist.entropy()
                if ent is not None and ent.numel() > 0:
                    out["open_policy_entropy"] = float(ent.mean().cpu().item())
                probs = dist.distribution.probs if hasattr(dist, "distribution") else None
                if probs is None and hasattr(dist, "probs"):
                    probs = dist.probs
                if probs is not None and probs.numel() >= 2:
                    sorted_p, _ = torch.sort(probs.flatten(), descending=True)
                    out["open_policy_action_margin"] = float(
                        (sorted_p[0] - sorted_p[1]).cpu().item()
                    )
                elif probs is None:
                    logits = getattr(getattr(dist, "distribution", dist), "logits", None)
                    if logits is not None and logits.numel() >= 2:
                        sorted_l, _ = torch.sort(logits.flatten(), descending=True)
                        out["open_policy_action_margin"] = float(
                            (sorted_l[0] - sorted_l[1]).cpu().item()
                        )
        finally:
            if was_training:
                policy.train()
    except Exception:
        logger.debug("policy_signal_extract.failed", exc_info=True)
    return out


__all__ = ["extract_policy_signals"]
