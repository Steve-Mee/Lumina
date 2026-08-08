"""Self-play lab scaffold (ADR-0037 Phase 0) — pure ranking + fail-closed gates.

Shadow reports only. No broker/order path. No birth progress mutation.
Default: disabled.
"""

from lumina_core.birth.self_play.gates import (
    SelfPlayGateResult,
    assert_self_play_allowed,
    evaluate_self_play_gate,
)
from lumina_core.birth.self_play.report import build_self_play_lab_report
from lumina_core.birth.self_play.scorer import (
    rank_self_play_variants,
    score_variant,
)
from lumina_core.birth.self_play.types import (
    SelfPlayLabConfig,
    SelfPlayVariantResult,
)

__all__ = [
    "SelfPlayGateResult",
    "SelfPlayLabConfig",
    "SelfPlayVariantResult",
    "assert_self_play_allowed",
    "build_self_play_lab_report",
    "evaluate_self_play_gate",
    "rank_self_play_variants",
    "score_variant",
]
