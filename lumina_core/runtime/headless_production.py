"""Production headless orchestrator — 24/7 full supervisor stack with recovery."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

from lumina_core.bootstrap import attach_runtime_app_to_module, bootstrap_runtime
from lumina_core.container import ApplicationContainer, create_application_container
from lumina_core.evolution.promotion_readiness import _reconciler_status_path
from lumina_core.logging_utils import flush_logger_handlers
from lumina_core.runtime.daemon_registry import RuntimeDaemonRegistry
from lumina_core.runtime.headless_telemetry import HeadlessTelemetry
from lumina_core.runtime.never_stop_recovery import NeverStopRecovery
from lumina_core.runtime.production_config import (
    load_production_section,
    resolve_heartbeat_path,
    resolve_status_path,
)
from lumina_core.runtime.runtime_preflight import (
    merge_preflight_reports,
    persist_preflight_report,
    run_preflight_early,
    run_preflight_post_bootstrap,
)
from lumina_core.runtime.runtime_reconciliation_loop import RuntimeReconciliationLoop
from lumina_core.runtime.runtime_slo_monitor import RuntimeSloMonitor
from lumina_core.runtime.safe_restart_policy import PREFLIGHT_FAIL_EXIT_CODE, SafeRestartPolicy

logger = logging.getLogger("lumina.headless.production")


class HeadlessProductionOrchestrator:
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

    def _interval(self, key: str, default: float) -> float:
        return float(self.prod_cfg.get(key, default) or default)

    def _touch_heartbeat(self) -> None:
        path = resolve_heartbeat_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    def _write_status(
        self,
        *,
        container: Any,
        slo_status: str = "unknown",
        phase: str = "running",
        extra: dict[str, Any] | None = None,
        restart_policy: SafeRestartPolicy | None = None,
    ) -> None:
        reconciler_pending = None
        path = _reconciler_status_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                reconciler_pending = int(data.get("pending_count", 0) or 0)
            except Exception:
                reconciler_pending = None

        dead_daemons = RuntimeDaemonRegistry.get().dead_daemons()
        payload: dict[str, Any] = {
            "runtime": "headless_production",
            "mode": self.mode,
            "phase": phase,
            "uptime_s": round(time.time() - self._started_at, 1),
            "slo_status": slo_status,
            "reconciler_pending": reconciler_pending,
            "dead_daemon_count": len(dead_daemons),
            "dead_daemons": list(dead_daemons),
            "daemons": RuntimeDaemonRegistry.get().snapshot(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if restart_policy is not None:
            age = restart_policy.deferred_restart_age_s()
            payload["deferred_restart_age_s"] = round(age, 1) if age is not None else None
            payload["restart_requested"] = restart_policy.restart_requested()
        if self._last_recon_result is not None:
            payload["reconciliation"] = self._last_recon_result
        if extra:
            payload.update(extra)
        out = resolve_status_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _bind_runtime_module(self, container: ApplicationContainer) -> None:
        runtime_module = sys.modules.get("__main__")
        if runtime_module is not None:
            container.bind_runtime_module(runtime_module)
            attach_runtime_app_to_module(container, runtime_module)

    def _apply_mode_env(self) -> None:
        os.environ.setdefault("LUMINA_ENFORCE_ENV_RUNTIME_MODE", "true")
        os.environ["LUMINA_MODE"] = self.mode
        os.environ["TRADE_MODE"] = self.mode

    def run(self) -> int:
        RuntimeDaemonRegistry.reset()
        self._apply_mode_env()
        telemetry = HeadlessTelemetry(mode=self.mode, started_at=self._started_at)

        early_report = run_preflight_early(mode=self.mode, prod_cfg=self.prod_cfg)
        if not early_report.ok:
            persist_preflight_report(early_report)
            telemetry.begin()
            telemetry.on_preflight_failed(early_report.failure_reasons)
            telemetry.end(status="preflight_failed", exit_code=PREFLIGHT_FAIL_EXIT_CODE)
            return PREFLIGHT_FAIL_EXIT_CODE

        container = create_application_container()
        container.start()
        self._bind_runtime_module(container)
        telemetry = HeadlessTelemetry(mode=self.mode, container=container, started_at=self._started_at)
        telemetry.begin()

        try:
            bootstrap_runtime(container)
        except Exception as exc:
            logger.exception("headless_production.bootstrap_failed")
            post_report = RuntimePreflightReportAdapter.from_exception(exc)
            merged = merge_preflight_reports(early_report, post_report)
            persist_preflight_report(merged)
            telemetry.on_preflight_failed(merged.failure_reasons)
            telemetry.end(status="bootstrap_failed", exit_code=PREFLIGHT_FAIL_EXIT_CODE)
            return PREFLIGHT_FAIL_EXIT_CODE

        post_report = run_preflight_post_bootstrap(mode=self.mode, container=container)
        merged = merge_preflight_reports(early_report, post_report)
        persist_preflight_report(merged)
        if not merged.ok:
            telemetry.on_preflight_failed(merged.failure_reasons)
            telemetry.end(status="preflight_failed", exit_code=PREFLIGHT_FAIL_EXIT_CODE)
            return PREFLIGHT_FAIL_EXIT_CODE

        if self.run_human_loop or bool(container.config.use_human_main_loop):
            import threading

            threading.Thread(target=container.analysis_service.run_main_loop, daemon=True).start()

        container.start_config_hot_reload()

        restart_policy = SafeRestartPolicy(mode=self.mode, prod_cfg=self.prod_cfg)
        slo_monitor = RuntimeSloMonitor(
            mode=self.mode,
            container=container,
            prod_cfg=self.prod_cfg,
            started_at=self._started_at,
        )
        reconciliation = RuntimeReconciliationLoop(
            mode=self.mode,
            container=container,
            restart_policy=restart_policy,
            prod_cfg=self.prod_cfg,
        )
        recovery = NeverStopRecovery(
            mode=self.mode,
            container=container,
            restart_policy=restart_policy,
            prod_cfg=self.prod_cfg,
        )

        container.logger.info(
            "HEADLESS_PRODUCTION_START mode=%s uptime_target=24/7",
            self.mode,
        )
        flush_logger_handlers(container.logger)

        try:
            self._main_loop(
                container=container,
                telemetry=telemetry,
                slo_monitor=slo_monitor,
                reconciliation=reconciliation,
                recovery=recovery,
                restart_policy=restart_policy,
            )
        except KeyboardInterrupt:
            container.engine.save_state()
            telemetry.end(status="interrupted", exit_code=0)
            return 0
        except SystemExit as exc:
            code = int(exc.code) if exc.code is not None else 0
            try:
                container.engine.save_state()
            except Exception:
                logger.exception("headless_production.save_state_on_exit_failed")
            telemetry.end(status="system_exit", exit_code=code)
            return code

        exit_code = restart_policy.execute_safe_restart(container)
        if exit_code is not None:
            telemetry.on_safe_restart_scheduled(restart_policy.restart_reason())
            telemetry.end(status="safe_restart", exit_code=exit_code)
            raise SystemExit(exit_code)

        telemetry.end(status="ok", exit_code=0)
        return 0

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
        heartbeat_iv = self._interval("heartbeat_interval_s", 15.0)
        slo_iv = self._interval("slo_eval_interval_s", 30.0)
        recon_iv = self._interval("reconciliation_interval_s", 10.0)
        recovery_iv = min(heartbeat_iv, recon_iv)
        slo_status = "pass"

        while True:
            now = time.time()

            if now - self._last_heartbeat >= heartbeat_iv:
                self._touch_heartbeat()
                telemetry.record_uptime_tick()
                self._write_status(
                    container=container,
                    slo_status=slo_status,
                    restart_policy=restart_policy,
                )
                self._last_heartbeat = now

            if now - self._last_slo >= slo_iv:
                deferred_age = restart_policy.deferred_restart_age_s()
                evaluation = slo_monitor.tick(deferred_restart_age_s=deferred_age)
                slo_status = evaluation.status
                telemetry.record_slo_eval_tick()
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
                self._handle_deferred_restart(
                    container=container,
                    telemetry=telemetry,
                    restart_policy=restart_policy,
                )
                self._last_recon = now

            if now - self._last_recovery >= recovery_iv:
                telemetry.record_recovery_tick()
                result = recovery.tick(telemetry_emit=telemetry.event_sink(), telemetry=telemetry)
                if result.escalated:
                    telemetry.on_recovery_escalated(restart_policy.restart_reason())
                self._last_recovery = now

            if restart_policy.restart_requested():
                exit_code = restart_policy.execute_safe_restart(container)
                if exit_code is not None:
                    raise SystemExit(exit_code)

            time.sleep(1.0)


class RuntimePreflightReportAdapter:
    """Minimal adapter for bootstrap exceptions."""

    @staticmethod
    def from_exception(exc: Exception):
        from lumina_core.runtime.runtime_preflight import RuntimePreflightReport

        return RuntimePreflightReport(
            ok=False,
            mode="unknown",
            checks={"bootstrap": "fail"},
            failure_reasons=(f"bootstrap:{type(exc).__name__}:{exc}",),
            message="Bootstrap failed",
        )
