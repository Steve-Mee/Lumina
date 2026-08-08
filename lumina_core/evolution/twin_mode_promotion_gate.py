"""Fail-closed promotion gates for Approval Twin judgment authority.

Wave H: twin_mode_types + twin_mode_promotion_gate_impl + twin_mode_controller.
"""
from __future__ import annotations

from lumina_core.evolution.twin_mode_controller import TwinModeController
from lumina_core.evolution.twin_mode_promotion_gate_impl import TwinModePromotionGate
from lumina_core.evolution.twin_mode_types import (  # noqa: F401
    AuthorityName,
    TwinModeCriterion,
    TwinModeCriterionResult,
    TwinModeName,
    TwinModePromotionDecision,
    TwinModePromotionEvidence,
    apply_mode_authority,
    authority_for_mode,
    canonicalize_twin_mode,
)

__all__ = [
    "AuthorityName",
    "TwinModeController",
    "TwinModeCriterion",
    "TwinModeCriterionResult",
    "TwinModeName",
    "TwinModePromotionDecision",
    "TwinModePromotionEvidence",
    "TwinModePromotionGate",
    "apply_mode_authority",
    "authority_for_mode",
    "canonicalize_twin_mode",
]
