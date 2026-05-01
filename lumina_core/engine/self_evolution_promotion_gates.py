"""Promotion gate helpers for ``SelfEvolutionMetaAgent`` (keeps meta-agent file smaller)."""

from __future__ import annotations

from typing import Any


def promotion_readiness_blocks_auto_apply(mode_key: str, best: dict[str, Any]) -> bool:
    """True when protected-mode promotion bundle fails for hyperparam auto-apply."""
    from lumina_core.evolution.promotion_readiness import check_promotion_readiness, is_protected_promotion_mode

    if not is_protected_promotion_mode(str(mode_key)):
        return False
    pr = check_promotion_readiness(mode=str(mode_key), challenger=best, proposal=None)
    return not pr.ok
