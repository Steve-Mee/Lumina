"""StageLoopProgressMixin — StageLoopSession mixin.

Wave F: metrics payload + write path split.
"""
from __future__ import annotations

from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.birth.stage_loop_progress_metrics import StageLoopProgressMetricsMixin
from lumina_core.birth.stage_loop_progress_write import StageLoopProgressWriteMixin

__all__ = ["StageLoopProgressMixin"]


class StageLoopProgressMixin(
    StageLoopProgressMetricsMixin,
    StageLoopProgressWriteMixin,
    StageLoopMixinBase,
):
    """See StageLoopSession for attributes."""
