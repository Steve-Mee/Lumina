"""
RuntimeWorkersFacade — D2 sub-slice 18: supervisor loop wiring extracted from runtime_workers.

Non-capital orchestration surface; supervisor tick = price fetch + SupervisorPhaseStateMachine.
Per 2026-06-04-phase3-d2-completion-roadmap.md Track A sub18 + runtime_workers close-out gate.
"""

from __future__ import annotations

import os
import time
import traceback
from datetime import datetime

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.engine.price_dupe_resolver import PriceDupeResolver
from lumina_core.engine.supervisor_phase_state_machine import SupervisorPhaseStateMachine
from lumina_core.runtime_context import RuntimeContext


_SIM_TICK_MODES = frozenset({"sim", "paper", "sim_real_guard"})


def trade_mode_of(app: object) -> str:
    """Configured mode. An empty reading stays empty so the loop fails closed."""
    for owner in (
        getattr(app, "config", None),
        getattr(getattr(app, "engine", None), "config", None),
    ):
        raw = getattr(owner, "trade_mode", None)
        if raw:
            return str(raw).strip().lower()
    return str(os.getenv("LUMINA_MODE", "")).strip().lower()


def tick_failure_is_fatal(mode: str) -> bool:
    """REAL and an unknown mode end the supervisor. SIM keeps the next tick."""
    cleaned = str(mode or "").strip().lower()
    if cleaned == "real" or not cleaned:
        return True
    return cleaned not in _SIM_TICK_MODES


class SupervisorLoopRunner:
    """Bounded owner for supervisor loop bootstrap + tick (D2 sub-slice 18)."""

    def __init__(self, *, app: RuntimeContext) -> None:
        self.app = app

    def run(self) -> None:
        try:
            self.run_inner()
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                code="SUPERVISOR_LOOP_CRASH",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            self.app.logger.error(f"supervisor_loop CRASHED: {exc}\n{traceback.format_exc()}")
            raise

    def run_inner(self) -> None:
        app = self.app
        if getattr(app.engine, "last_validation", None) is None:
            app.engine.last_validation = datetime.now()

        from lumina_core.engine.emotional_twin_worker import EmotionalTwinWorker

        EmotionalTwinWorker(app=app).start_daemon_thread()

        phases = SupervisorPhaseStateMachine(app=app)
        _supervisor_loop_started = False
        last_tick_fault = 0.0
        while True:
            if not _supervisor_loop_started:
                app.logger.info("SUPERVISOR_LOOP_ENTER,status=first_iteration")
                _supervisor_loop_started = True

            try:
                price = PriceDupeResolver(app=app).fetch_locked_price()
                dream_snapshot = (
                    app.get_current_dream_snapshot()
                    if hasattr(app, "get_current_dream_snapshot")
                    else None
                )
                phases.advance_or_tick(float(price), dream_snapshot=dream_snapshot)
            except Exception as exc:
                if tick_failure_is_fatal(trade_mode_of(app)):
                    raise
                now = time.time()
                if now - last_tick_fault >= 30.0:
                    app.logger.error("supervisor_loop tick failed, continuing: %s", exc)
                    last_tick_fault = now
            time.sleep(1)


def run_supervisor_loop(app: RuntimeContext) -> None:
    """Public entry for bootstrap + runtime_workers compat."""
    SupervisorLoopRunner(app=app).run()


def run_forever(app: RuntimeContext) -> None:
    run_supervisor_loop(app)
