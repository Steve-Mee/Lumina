"""Headless production main run loop orchestration."""
from __future__ import annotations

import logging
from typing import Any

from lumina_core.bootstrap import bootstrap_runtime
from lumina_core.container import create_application_container
from lumina_core.logging_utils import flush_logger_handlers
from lumina_core.runtime.daemon_registry import RuntimeDaemonRegistry
from lumina_core.runtime.headless_preflight_adapter import RuntimePreflightReportAdapter
from lumina_core.runtime.headless_telemetry import HeadlessTelemetry
from lumina_core.runtime.never_stop_recovery import NeverStopRecovery
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


class HeadlessProductionRunMixin:
    """Main run() orchestration for headless production."""

    def run(self) -> int:
        RuntimeDaemonRegistry.reset()
        self._apply_mode_env()
        self._install_signal_handlers()
        telemetry = HeadlessTelemetry(mode=self.mode, started_at=self._started_at)
        container: Any | None = None
        restart_policy: SafeRestartPolicy | None = None
        exit_code = 0
        status = "ok"
        shutdown_done = False

        try:
            early_report = run_preflight_early(mode=self.mode, prod_cfg=self.prod_cfg)
            if not early_report.ok:
                persist_preflight_report(early_report)
                telemetry.begin()
                telemetry.on_preflight_failed(early_report.failure_reasons)
                self._write_status(phase="preflight_failed", slo_status="fail")
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
                self._save_checkpoint(container, telemetry, reason="bootstrap_failed")
                self._graceful_shutdown(
                    container=container,
                    telemetry=telemetry,
                    status="bootstrap_failed",
                    exit_code=PREFLIGHT_FAIL_EXIT_CODE,
                    reason="bootstrap_failed",
                    already_checkpointed=True,
                )
                shutdown_done = True
                return PREFLIGHT_FAIL_EXIT_CODE

            post_report = run_preflight_post_bootstrap(mode=self.mode, container=container)
            merged = merge_preflight_reports(early_report, post_report)
            persist_preflight_report(merged)
            if not merged.ok:
                telemetry.on_preflight_failed(merged.failure_reasons)
                self._graceful_shutdown(
                    container=container,
                    telemetry=telemetry,
                    status="preflight_failed",
                    exit_code=PREFLIGHT_FAIL_EXIT_CODE,
                    reason="post_bootstrap_preflight",
                )
                shutdown_done = True
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
            self._loop_components = {
                "restart_policy": restart_policy,
                "slo_monitor": slo_monitor,
                "reconciliation": reconciliation,
                "recovery": recovery,
            }
            self._subscribe_config_events(
                container,
                telemetry,
                restart_policy=restart_policy,
                slo_monitor=slo_monitor,
                reconciliation=reconciliation,
                recovery=recovery,
            )

            container.logger.info(
                "HEADLESS_PRODUCTION_START mode=%s uptime_target=24/7",
                self.mode,
            )
            flush_logger_handlers(container.logger)
            self._write_status(
                container=container,
                slo_status="pass",
                phase="running",
                restart_policy=restart_policy,
            )

            loop_exit = self._main_loop(
                container=container,
                telemetry=telemetry,
                slo_monitor=slo_monitor,
                reconciliation=reconciliation,
                recovery=recovery,
                restart_policy=restart_policy,
            )

            if loop_exit == "safe_restart":
                code = self._pending_safe_restart_code
                if code is None and restart_policy is not None:
                    code = restart_policy.execute_safe_restart(container)
                if code is not None:
                    telemetry.on_safe_restart_scheduled(
                        restart_policy.restart_reason() if restart_policy else "safe_restart"
                    )
                    self._graceful_shutdown(
                        container=container,
                        telemetry=telemetry,
                        status="safe_restart",
                        exit_code=int(code),
                        reason=(
                            restart_policy.restart_reason()
                            if restart_policy is not None
                            else "safe_restart"
                        ),
                        restart_policy=restart_policy,
                        already_checkpointed=True,
                    )
                    shutdown_done = True
                    return int(code)

            status = "interrupted" if loop_exit == "shutdown" else "ok"
            exit_code = 0
            self._graceful_shutdown(
                container=container,
                telemetry=telemetry,
                status=status,
                exit_code=exit_code,
                reason=self._shutdown_reason or loop_exit,
                restart_policy=restart_policy,
            )
            shutdown_done = True
            return exit_code

        except KeyboardInterrupt:
            status = "interrupted"
            exit_code = 0
            if not shutdown_done:
                self._graceful_shutdown(
                    container=container,
                    telemetry=telemetry,
                    status=status,
                    exit_code=exit_code,
                    reason="keyboard_interrupt",
                    restart_policy=restart_policy,
                )
                shutdown_done = True
            return exit_code
        except SystemExit as exc:
            code = int(exc.code) if isinstance(exc.code, int) else (0 if exc.code is None else 1)
            if not shutdown_done:
                self._graceful_shutdown(
                    container=container,
                    telemetry=telemetry,
                    status="system_exit",
                    exit_code=code,
                    reason=self._shutdown_reason or f"system_exit:{code}",
                    restart_policy=restart_policy,
                    already_checkpointed=code == 42,
                )
                shutdown_done = True
            return code
        except Exception as exc:
            logger.exception("headless_production.fatal")
            status = "fatal"
            exit_code = 1
            telemetry.alert(
                f"Headless production fatal error: {type(exc).__name__}: {exc}",
                alert_type="fatal_error",
                data={"error": str(exc)},
            )
            if not shutdown_done:
                self._graceful_shutdown(
                    container=container,
                    telemetry=telemetry,
                    status=status,
                    exit_code=exit_code,
                    reason=f"fatal:{type(exc).__name__}",
                    restart_policy=restart_policy,
                )
                shutdown_done = True
            return exit_code
        finally:
            self._restore_signal_handlers()
            if not shutdown_done:
                try:
                    self._graceful_shutdown(
                        container=container,
                        telemetry=telemetry,
                        status=status,
                        exit_code=exit_code,
                        reason=self._shutdown_reason or "finally",
                        restart_policy=restart_policy,
                    )
                except Exception:
                    logger.exception("headless_production.final_shutdown_failed")
