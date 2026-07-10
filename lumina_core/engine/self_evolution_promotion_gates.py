"""Promotion gate helpers for ``SelfEvolutionMetaAgent`` (keeps meta-agent file smaller)."""

from __future__ import annotations

from typing import Any


SIM_AUTO_APPROVE_TWIN_FLOOR = 0.90


def should_auto_approve_sim_evolution(
    *,
    mode: str,
    twin_confidence: float,
    approval_required: bool,
) -> bool:
    """Zero-touch SIM evolution when twin confidence meets floor."""
    mode_key = str(mode or "sim").strip().lower()
    if mode_key == "real":
        return False
    if not approval_required:
        return True
    try:
        confidence = float(twin_confidence)
    except (TypeError, ValueError):
        return False
    if confidence > 1.0:
        confidence /= 100.0
    return confidence >= SIM_AUTO_APPROVE_TWIN_FLOOR


def promotion_readiness_blocks_auto_apply(mode_key: str, best: dict[str, Any]) -> bool:
    """True when protected-mode promotion bundle fails for hyperparam auto-apply."""
    from lumina_core.evolution.promotion_readiness import check_promotion_readiness, is_protected_promotion_mode

    if not is_protected_promotion_mode(str(mode_key)):
        return False
    pr = check_promotion_readiness(mode=str(mode_key), challenger=best, proposal=None)
    return not pr.ok
