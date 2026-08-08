from __future__ import annotations

import json
import logging
import queue
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


from .errors import BrokerBridgeError, ErrorSeverity, LuminaError, log_structured
from .lumina_engine import LuminaEngine
from .valuation_engine import ValuationEngine
from lumina_core.engine.operations_service_orders import OperationsOrdersMixin
from lumina_core.engine.operations_service_market import OperationsMarketMixin
from lumina_core.order_gatekeeper import (  # noqa: F401 — re-export for tests/monkeypatch
    enforce_pre_trade_gate as enforce_pre_trade_gate,
)

logger = logging.getLogger(__name__)


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


