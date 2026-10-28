"""StageLoopDataOpsMixin — StageLoopSession mixin.

Bounded modules: ``stage_loop_data_cache``, ``stage_loop_data_enrich`` (Wave B PR-B4).
"""
from __future__ import annotations

from lumina_core.birth.stage_loop_data_cache import StageLoopDataCacheMixin
from lumina_core.birth.stage_loop_data_enrich import StageLoopDataEnrichMixin
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase

__all__ = ["StageLoopDataOpsMixin"]


class StageLoopDataOpsMixin(
    StageLoopDataCacheMixin,
    StageLoopDataEnrichMixin,
    StageLoopMixinBase,
):
    """See StageLoopSession for attributes."""
