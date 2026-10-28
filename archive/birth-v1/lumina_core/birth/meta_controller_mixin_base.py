"""Shared attribute declarations for BirthMetaController mixins (mypy)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
    from lumina_core.birth.meta_self_eval import SelfEvalState

    class MetaControllerMixinBase:
        cfg: BirthCurriculumConfig
        baseline_reward: BirthRewardConfig
        active_reward: BirthRewardConfig
        strategy_history: list[dict[str, Any]]
        patterns_last_inject: int
        oracle_wins_last_inject: int
        explore_multiplier: float
        last_review_trigger: str
        rollouts_since_review: int
        self_eval: SelfEvalState
        self_eval_history: list[dict[str, Any]]
        approval_twin: Any | None
else:

    class MetaControllerMixinBase:
        """Marker base for meta-controller mixins."""
