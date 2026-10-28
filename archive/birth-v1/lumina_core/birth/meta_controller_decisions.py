"""MetaControllerDecisionsMixin (Wave G decide_* split)."""
from __future__ import annotations

from lumina_core.birth.meta_decide_pre_rollout import MetaDecidePreRolloutMixin
from lumina_core.birth.meta_decide_after_rollout import MetaDecideAfterRolloutMixin
from lumina_core.birth.meta_decide_periodic import MetaDecidePeriodicMixin
from lumina_core.birth.meta_decide_adaptation import MetaDecideAdaptationMixin
from lumina_core.birth.meta_controller_decisions_core import MetaControllerDecisionsCore
from lumina_core.birth.meta_controller_mixin_base import MetaControllerMixinBase


class MetaControllerDecisionsMixin(
    MetaDecidePreRolloutMixin,
    MetaDecideAfterRolloutMixin,
    MetaDecidePeriodicMixin,
    MetaDecideAdaptationMixin,
    MetaControllerDecisionsCore,
    MetaControllerMixinBase,
):
    """Composed meta decision surface."""
