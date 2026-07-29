"""Production headless orchestrator — 24/7 full supervisor stack with recovery."""

from __future__ import annotations

import logging
import time
from typing import Any

from lumina_core.runtime.headless_preflight_adapter import (  # noqa: F401
    RuntimePreflightReportAdapter,
)
from lumina_core.runtime.headless_production_orchestrate import HeadlessProductionOrchestrateMixin
from lumina_core.runtime.headless_production_phases import HeadlessProductionPhasesMixin
from lumina_core.runtime.production_config import load_production_section

logger = logging.getLogger("lumina.headless.production")


class HeadlessProductionOrchestrator(
    HeadlessProductionOrchestrateMixin,
    HeadlessProductionPhasesMixin,
):
    """Continuous 24/7 headless runtime with preflight, SLO, recovery, and safe restart."""

    def __init__(
        self,
        *,
        mode: str,
        run_human_loop: bool = False,
        prod_cfg: dict[str, Any] | None = None,
    ) -> None:
        self.mode = str(mode or "sim").strip().lower()
        self.run_human_loop = bool(run_human_loop)
        self.prod_cfg = prod_cfg if prod_cfg is not None else load_production_section()
        self._started_at = time.time()
        self._last_heartbeat = 0.0
        self._last_slo = 0.0
        self._last_recon = 0.0
        self._last_recovery = 0.0
        self._last_recon_result: dict[str, Any] | None = None
        self._last_slo_breaches: tuple[str, ...] = ()
        self._shutdown_requested = False
        self._shutdown_reason = ""
        self._prev_signal_handlers: dict[int, Any] = {}
        self._last_config_reload_at: str | None = None
        self._last_config_reload_ok: bool | None = None
        self._last_config_reload_reason: str | None = None
        self._last_checkpoint_at: float | None = None
        self._config_bus_tokens: list[str] = []
        self._slo_status = "unknown"
        self._loop_components: dict[str, Any] | None = None
        self._pending_safe_restart_code: int | None = None

    def _interval(self, key: str, default: float) -> float:
        return float(self.prod_cfg.get(key, default) or default)

    def _request_shutdown(self, reason: str = "signal") -> None:
        self._shutdown_requested = True
        if not self._shutdown_reason:
            self._shutdown_reason = str(reason or "signal")
        logger.info("headless_production.shutdown_requested reason=%s", self._shutdown_reason)
