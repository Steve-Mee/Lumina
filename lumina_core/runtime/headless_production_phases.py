"""Headless production loop / restart phases (mixin for orchestrator)."""
from __future__ import annotations

import logging
import time
from typing import Any

from lumina_core.runtime.daemon_registry import RuntimeDaemonRegistry
from lumina_core.runtime.headless_telemetry import HeadlessTelemetry
from lumina_core.runtime.never_stop_recovery import NeverStopRecovery
from lumina_core.runtime.runtime_reconciliation_loop import RuntimeReconciliationLoop
from lumina_core.runtime.runtime_slo_monitor import RuntimeSloMonitor
from lumina_core.runtime.safe_restart_policy import SafeRestartPolicy

logger = logging.getLogger("lumina.headless.production")


class HeadlessProductionPhasesMixin:
    """Main-loop and deferred-restart phases for HeadlessProductionOrchestrator."""

    __slots__ = ()

    def _handle_deferred_restart(
        self,
        *,
        container: Any,
        telemetry: HeadlessTelemetry,
        restart_policy: SafeRestartPolicy,
    ) -> None:
        state = restart_policy.evaluate_deferred_restart(container)
        if state.should_alert:
            telemetry.on_restart_deferred(state.reasons, age_s=state.age_s)
            restart_policy.mark_deferred_alert_sent()
        if state.should_escalate:
            telemetry.alert(
                f"Deferred restart exceeded max ({state.age_s:.0f}s): {'; '.join(state.reasons)}",
                alert_type="restart_deferred_escalated",
                data={"reasons": list(state.reasons), "age_s": state.age_s},
            )
            restart_policy.mark_deferred_escalation_sent()
            if self.mode == "sim":
                decision = restart_policy.evaluate_process_restart(container)
                if decision.allowed:
                    exit_code = restart_policy.execute_safe_restart(container)
                    if exit_code is not None:
                        raise SystemExit(exit_code)

    def _stall_signals_from_slo(self, breaches: tuple[str, ...], warnings: tuple[str, ...]) -> list[str]:
        signals: list[str] = []
        for item in list(breaches) + list(warnings):
            text = str(item)
            lower = text.lower()
            if "supervisor_tick_stale" in lower or "supervisor_tick_missing" in lower:
                signals.append(text)
            if "reconciler_status_stale" in lower or "reconciler_status_missing" in lower:
                signals.append(text)
        return signals

    def _main_loop(
        self,
        *,
        container: Any,
        telemetry: HeadlessTelemetry,
        slo_monitor: RuntimeSloMonitor,
        reconciliation: RuntimeReconciliationLoop,
        recovery: NeverStopRecovery,
        restart_policy: SafeRestartPolicy,
    ) -> str:
        slo_status = "pass"
        self._slo_status = slo_status
        pending_stall_signals: list[str] = []

        while not self._shutdown_requested:
            now = time.time()
            heartbeat_iv = self._interval("heartbeat_interval_s", 15.0)
            slo_iv = self._interval("slo_eval_interval_s", 30.0)
            recon_iv = self._interval("reconciliation_interval_s", 10.0)
            recovery_iv = min(heartbeat_iv, recon_iv)

            if now - self._last_heartbeat >= heartbeat_iv:
                self._touch_heartbeat()
                telemetry.record_uptime_tick()
                dead_count = len(RuntimeDaemonRegistry.get().dead_daemons())
                deferred_age = restart_policy.deferred_restart_age_s()
                recon_ok = None
                if self._last_recon_result is not None:
                    recon_ok = bool(self._last_recon_result.get("ok", True))
                telemetry.record_runtime_gauges(
                    dead_daemon_count=dead_count,
                    deferred_restart_age_s=deferred_age,
                    reconciliation_ok=recon_ok,
                )
                autonomy = self._autonomy_snapshot()
                if autonomy is not None:
                    telemetry.on_autonomy_snapshot(autonomy)
                self._write_status(
                    container=container,
                    slo_status=slo_status,
                    phase="running",
                    restart_policy=restart_policy,
                )
                self._last_heartbeat = now

            if now - self._last_slo >= slo_iv:
                deferred_age = restart_policy.deferred_restart_age_s()
                evaluation = slo_monitor.tick(deferred_restart_age_s=deferred_age)
                slo_status = evaluation.status
                self._slo_status = slo_status
                self._last_slo_breaches = evaluation.breaches
                telemetry.record_slo_eval_tick()
                pending_stall_signals = self._stall_signals_from_slo(
                    evaluation.breaches, evaluation.warnings
                )
                if evaluation.breaches:
                    telemetry.on_slo_breach(evaluation.breaches)
                    if evaluation.status == "fail" and self.mode == "real":
                        restart_policy.request_process_restart(
                            f"slo_fail:{';'.join(evaluation.breaches)}"
                        )
                if evaluation.warnings:
                    telemetry.emit("runtime.slo.warning", warnings=list(evaluation.warnings))
                self._last_slo = now

            if now - self._last_recon >= recon_iv:
                recon_result = reconciliation.tick()
                self._last_recon_result = recon_result.to_dict()
                if recon_result.issues:
                    telemetry.on_reconciliation_issue(recon_result.issues)
                    for issue in recon_result.issues:
                        if issue.startswith("position_drift"):
                            telemetry.on_position_drift(issue)
                        if "reconciler_status_stale" in issue or "reconciler_status_missing" in issue:
                            pending_stall_signals.append(issue)
                self._handle_deferred_restart(
                    container=container,
                    telemetry=telemetry,
                    restart_policy=restart_policy,
                )
                self._last_recon = now

            if now - self._last_recovery >= recovery_iv:
                telemetry.record_recovery_tick()
                result = recovery.tick(
                    telemetry_emit=telemetry.event_sink(),
                    telemetry=telemetry,
                    stall_signals=tuple(pending_stall_signals),
                )
                pending_stall_signals = []
                if result.escalated:
                    telemetry.on_recovery_escalated(restart_policy.restart_reason())
                self._last_recovery = now

            if restart_policy.restart_requested():
                exit_code = restart_policy.execute_safe_restart(container)
                if exit_code is not None:
                    self._pending_safe_restart_code = int(exit_code)
                    self._last_checkpoint_at = time.time()
                    return "safe_restart"

            time.sleep(1.0)

        return "shutdown"


