"""Fast-path / SLA / consensus path helpers mixed into ReasoningService."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from lumina_core.order_gatekeeper import session_guard_allows_trading
from lumina_core.risk.regime_detector import RegimeSnapshot
from .errors import format_error_code
from lumina_core.logging_utils import correlation_id, get_logger, record_reasoning_latency_monitoring

logger = get_logger("lumina.reasoning.service")


from lumina_core.engine.reasoning_paths_infer_head import ReasoningPathsInferHeadMixin
from lumina_core.engine.reasoning_paths_infer_tail import ReasoningPathsInferTailMixin

class ReasoningPathsMixin(ReasoningPathsInferHeadMixin, ReasoningPathsInferTailMixin):
    """Reasoning path routing + infer_json (M5 façade)."""

    __slots__ = ()
