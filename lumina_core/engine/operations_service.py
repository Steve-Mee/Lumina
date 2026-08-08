from __future__ import annotations

import json
import logging
import os
import queue
import signal
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from lumina_core.broker.broker_bridge import AccountInfo, Order
from .errors import BrokerBridgeError, ErrorSeverity, LuminaError, format_error_code, log_structured
from .lumina_engine import LuminaEngine
from lumina_core.risk.policy_engine import PolicyEngine
from .valuation_engine import ValuationEngine
from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.logging_utils import log_event, log_runtime_trace, runtime_trace_enabled

logger = logging.getLogger(__name__)


from lumina_core.engine.operations_service_orders import OperationsOrdersMixin
from lumina_core.engine.operations_service_market import OperationsMarketMixin

@dataclass(slots=True)
class OperationsService(OperationsOrdersMixin, OperationsMarketMixin):
    """Owns remaining runtime helper operations that should not route through legacy wrappers."""

    engine: LuminaEngine
    container: Any | None = None
    thought_queue: queue.Queue = field(default_factory=queue.Queue)
    valuation_engine: ValuationEngine = field(default_factory=ValuationEngine)

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("OperationsService requires a LuminaEngine")
        self.valuation_engine.load_calibration_file("state/validation/fill_calibration.json")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def _broker(self):
        broker = getattr(self.container, "broker", None)
        if broker is None:
            raise BrokerBridgeError("BrokerBridge is not configured on the container")
        return broker

    def thought_logger_thread(self) -> None:
        app = self._app()
        while True:
            try:
                entry = self.thought_queue.get()
                self.engine.config.thought_log.parent.mkdir(parents=True, exist_ok=True)
                with self.engine.config.thought_log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                self.thought_queue.task_done()
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                    code="OPS_THOUGHT_LOG_001",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                app.logger.error(f"Thought log error: {exc}")

    def log_thought(self, data: dict[str, Any]) -> None:
        payload = dict(data)
        payload["timestamp"] = datetime.now().isoformat()
        self.thought_queue.put(payload)


