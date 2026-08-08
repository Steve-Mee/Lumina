"""Fast-path / SLA / consensus path helpers mixed into ReasoningService."""

from __future__ import annotations


from lumina_core.logging_utils import get_logger
from lumina_core.engine.reasoning_paths_infer_head import ReasoningPathsInferHeadMixin
from lumina_core.engine.reasoning_paths_infer_tail import ReasoningPathsInferTailMixin

logger = get_logger("lumina.reasoning.service")


class ReasoningPathsMixin(ReasoningPathsInferHeadMixin, ReasoningPathsInferTailMixin):
    """Reasoning path routing + infer_json (M5 façade)."""

    __slots__ = ()
