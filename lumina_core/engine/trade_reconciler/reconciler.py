"""TradeReconciler orchestrator (mixin composition)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.trade_reconciler.audit_status_mixin import AuditStatusMixin
from lumina_core.engine.trade_reconciler.fill_ingest_mixin import FillIngestMixin
from lumina_core.engine.trade_reconciler.fill_matching_mixin import FillMatchingMixin
from lumina_core.engine.trade_reconciler.fill_normalization_mixin import FillNormalizationMixin
from lumina_core.engine.trade_reconciler.finalize_mixin import FinalizeMixin
from lumina_core.engine.trade_reconciler.lifecycle_mixin import LifecycleMixin
from lumina_core.engine.trade_reconciler.schemas import FillEvent
from lumina_core.engine.trade_reconciler.transport_mixin import TransportMixin
from lumina_core.engine.valuation_engine import ValuationEngine

@dataclass(slots=True)
class TradeReconciler(
    LifecycleMixin,
    FillIngestMixin,
    TransportMixin,
    FillMatchingMixin,
    FinalizeMixin,
    AuditStatusMixin,
    FillNormalizationMixin,
):
    """Reconciles broker fill events against locally detected close snapshots."""

    engine: LuminaEngine
    stop_requested: bool = False
    _recent_fills: deque[FillEvent] = field(default_factory=lambda: deque(maxlen=100))
    _seen_fill_ids: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    _backoff_seconds: float = 1.0
    _max_backoff_seconds: float = 30.0
    _heartbeat_seconds: float = 20.0
    valuation_engine: ValuationEngine = field(default_factory=ValuationEngine)

