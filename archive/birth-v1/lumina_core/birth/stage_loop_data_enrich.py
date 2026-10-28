"""StageLoopDataEnrichMixin — entropy, EdgeScore, exploration, swarm.

Part of StageLoopDataOpsMixin (Wave B PR-B4). Wave G: swarm methods extracted.
"""
from __future__ import annotations

from lumina_core.birth.stage_loop_data_enrich_core import StageLoopDataEnrichMixinCore
from lumina_core.birth.stage_loop_enrich_swarm import StageLoopEnrichSwarmMixin
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase


class StageLoopDataEnrichMixin(
    StageLoopEnrichSwarmMixin,
    StageLoopDataEnrichMixinCore,
    StageLoopMixinBase,
):
    """Composed StageLoopDataEnrichMixin."""
