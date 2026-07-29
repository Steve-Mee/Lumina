"""Approval Twin DNA / code / shadow evaluation helpers.

Bounded modules: ``approval_twin_eval_dna``, ``approval_twin_eval_code``,
``approval_twin_eval_shadow``.
"""
from __future__ import annotations

from lumina_core.evolution.approval_twin_eval_code import ApprovalTwinCodeEvaluatorMixin  # noqa: F401
from lumina_core.evolution.approval_twin_eval_dna import ApprovalTwinDnaEvaluatorMixin  # noqa: F401
from lumina_core.evolution.approval_twin_eval_shadow import ApprovalTwinShadowEvaluatorMixin  # noqa: F401


class ApprovalTwinEvaluatorsMixin(
    ApprovalTwinDnaEvaluatorMixin,
    ApprovalTwinCodeEvaluatorMixin,
    ApprovalTwinShadowEvaluatorMixin,
):
    """Combined evaluator surface kept for ApprovalTwinAgent MRO."""


__all__ = [
    "ApprovalTwinCodeEvaluatorMixin",
    "ApprovalTwinDnaEvaluatorMixin",
    "ApprovalTwinEvaluatorsMixin",
    "ApprovalTwinShadowEvaluatorMixin",
]
