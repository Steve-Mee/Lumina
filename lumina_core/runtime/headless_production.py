"""Production headless orchestrator — 24/7 full supervisor stack with recovery."""

from __future__ import annotations

import json
import logging
import os
import signal
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
    checkpoint_status_enabled,
    force_checkpoint_on_shutdown,
    load_production_section,
    resolve_engine_state_paths,
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

    def _install_signal_handlers(self) -> None:
        def _handler(signum: int, _frame: Any) -> None:
            try:
                name = signal.Signals(signum).name
            except Exception:
                name = str(signum)
            self._request_shutdown(f"signal:{name}")

        for sig_name in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                self._prev_signal_handlers[int(sig)] = signal.getsignal(sig)
                signal.signal(sig, _handler)
            except (ValueError, OSError, RuntimeError) as exc:
                logger.debug("headless_production.signal_register_skipped sig=%s detail=%s", sig_name, exc)

    def _restore_signal_handlers(self) -> None:
        for sig, handler in self._prev_signal_handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError, RuntimeError):
                pass
        self._prev_signal_handlers.clear()

    def _touch_heartbeat(self) -> None:
        path = resolve_heartbeat_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    def _checkpoint_meta(self) -> dict[str, Any]:
        if not checkpoint_status_enabled(self.prod_cfg):
            return {}
        meta: dict[str, Any] = {
            "state_persist_alive": RuntimeDaemonRegistry.get().is_alive("state-persist-daemon"),
        }
        if self._last_checkpoint_at is not None:
            meta["last_checkpoint_at"] = datetime.fromtimestamp(
                self._last_checkpoint_at, tz=timezone.utc
            ).isoformat()
            meta["checkpoint_age_s"] = round(time.time() - self._last_checkpoint_at, 1)
            return meta

        for candidate in resolve_engine_state_paths():
            try:
                if candidate.is_file():
                    mtime = candidate.stat().st_mtime
                    meta["last_checkpoint_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                    meta["checkpoint_age_s"] = round(time.time() - mtime, 1)
                    meta["checkpoint_path"] = str(candidate)
                    break
            except OSError:
                continue
        return meta

    def _autonomy_snapshot(self) -> dict[str, Any] | None:
        try:
            from lumina_core.runtime.runtime_twin_oversight import RuntimeTwinOversight

            return RuntimeTwinOversight.get().snapshot().to_dict()
        except Exception:
            logger.debug("headless_production.autonomy_snapshot_failed", exc_info=True)
            return None

    def _write_status(
        self,
        *,
        container: Any | None = None,
        slo_status: str = "unknown",
        phase: str = "running",
        extra: dict[str, Any] | None = None,
        restart_policy: SafeRestartPolicy | None = None,
    ) -> None:
        _ = container  # reserved for future container-bound fields
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
            "last_config_reload_at": self._last_config_reload_at,
            "last_config_reload_ok": self._last_config_reload_ok,
            "last_config_reload_reason": self._last_config_reload_reason,
        }
        if self._shutdown_reason:
            payload["shutdown_reason"] = self._shutdown_reason
        payload.update(self._checkpoint_meta())
        autonomy = self._autonomy_snapshot()
        if autonomy is not None:
            payload["autonomy"] = autonomy
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
        try:
            tmp = out.with_suffix(out.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(out)
        except Exception:
            out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _save_checkpoint(
        self,
        container: Any | None,
        telemetry: HeadlessTelemetry | None,
        *,
        reason: str = "",
    ) -> bool:
        if container is None:
            return False
        if reason.startswith("shutdown") and not force_checkpoint_on_shutdown(self.prod_cfg):
            return False
        engine = getattr(container, "engine", None)
        if engine is None:
            return False
        save = getattr(engine, "save_state", None)
        if not callable(save):
            return False
        try:
            save()
            self._last_checkpoint_at = time.time()
            if telemetry is not None:
                telemetry.on_checkpoint_saved(ok=True, detail=reason)
            logger.info("headless_production.checkpoint_saved reason=%s", reason or "unspecified")
            return True
        except Exception as exc:
            logger.exception("headless_production.checkpoint_failed reason=%s", reason)
            if telemetry is not None:
                telemetry.on_checkpoint_saved(ok=False, detail=f"{reason}:{type(exc).__name__}")
            return False

    def _bind_runtime_module(self, container: ApplicationContainer) -> None:
        runtime_module = sys.modules.get("__main__")
        if runtime_module is not None:
            container.bind_runtime_module(runtime_module)
            attach_runtime_app_to_module(container, runtime_module)

    def _apply_mode_env(self) -> None:
        os.environ.setdefault("LUMINA_ENFORCE_ENV_RUNTIME_MODE", "true")
        os.environ["LUMINA_MODE"] = self.mode
        os.environ["TRADE_MODE"] = self.mode

    def _refresh_prod_cfg(
        self,
        *,
        restart_policy: SafeRestartPolicy | None = None,
        slo_monitor: RuntimeSloMonitor | None = None,
        reconciliation: RuntimeReconciliationLoop | None = None,
        recovery: NeverStopRecovery | None = None,
        source: str = "hot_reload",
    ) -> None:
        # Prefer live config.yaml production section; preserve env override keys if present.
        fresh = load_production_section()
        env_override = os.getenv("LUMINA_HEADLESS_PRODUCTION_JSON", "").strip()
        if env_override:
            try:
                parsed = json.loads(env_override)
                if isinstance(parsed, dict):
                    fresh = {**fresh, **parsed}
            except json.JSONDecodeError:
                logger.warning("headless_production.prod_cfg_override_invalid source=%s", source)
        self.prod_cfg = fresh
        if restart_policy is not None:
            restart_policy.update_prod_cfg(fresh)
        if slo_monitor is not None:
            slo_monitor.update_prod_cfg(fresh)
        if reconciliation is not None:
            reconciliation.update_prod_cfg(fresh)
        if recovery is not None:
            recovery.update_prod_cfg(fresh)
        logger.info("headless_production.prod_cfg_refreshed source=%s", source)

    def _subscribe_config_events(
        self,
        container: Any,
        telemetry: HeadlessTelemetry,
        *,
        restart_policy: SafeRestartPolicy,
        slo_monitor: RuntimeSloMonitor,
        reconciliation: RuntimeReconciliationLoop,
        recovery: NeverStopRecovery,
    ) -> None:
        bus = getattr(container, "event_bus", None)
        if bus is None or not hasattr(bus, "subscribe"):
            return

        def _on_reloaded(event: Any) -> None:
            payload = getattr(event, "payload", None) or {}
            if not isinstance(payload, dict):
                payload = {}
            self._last_config_reload_at = datetime.now(timezone.utc).isoformat()
            self._last_config_reload_ok = True
            sections = list(payload.get("changed_sections") or [])
            self._last_config_reload_reason = "ok:" + (",".join(sections) if sections else "none")
            self._refresh_prod_cfg(
                restart_policy=restart_policy,
                slo_monitor=slo_monitor,
                reconciliation=reconciliation,
                recovery=recovery,
                source=str(payload.get("source") or "event_bus"),
            )
            telemetry.on_config_reloaded(sections=sections, source=str(payload.get("source") or ""))

        def _on_failed(event: Any) -> None:
            payload = getattr(event, "payload", None) or {}
            if not isinstance(payload, dict):
                payload = {}
            self._last_config_reload_at = datetime.now(timezone.utc).isoformat()
            self._last_config_reload_ok = False
            reason = str(payload.get("reason") or "unknown")
            fields = list(payload.get("immutable_fields") or [])
            self._last_config_reload_reason = reason
            telemetry.on_config_reload_rejected(reason=reason, fields=fields)

        try:
            tok_ok = bus.subscribe("runtime.config.reloaded", _on_reloaded)
            tok_fail = bus.subscribe("runtime.config.reload_failed", _on_failed)
            if tok_ok:
                self._config_bus_tokens.append(str(tok_ok))
            if tok_fail:
                self._config_bus_tokens.append(str(tok_fail))
        except Exception:
            logger.debug("headless_production.config_event_subscribe_failed", exc_info=True)

    def _unsubscribe_config_events(self, container: Any | None) -> None:
        if container is None:
            self._config_bus_tokens.clear()
            return
        bus = getattr(container, "event_bus", None)
        if bus is None:
            self._config_bus_tokens.clear()
            return
        for token in self._config_bus_tokens:
            try:
                bus.unsubscribe(token)
            except Exception:
                logger.debug("headless_production.config_event_unsubscribe_failed", exc_info=True)
        self._config_bus_tokens.clear()

    def _stop_observability(self, container: Any | None) -> None:
        if container is None:
            return
        obs = getattr(container, "observability_service", None)
        if obs is None:
            return
        stop = getattr(obs, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                logger.debug("headless_production.observability_stop_failed", exc_info=True)

    def _graceful_shutdown(
        self,
        *,
        container: Any | None,
        telemetry: HeadlessTelemetry,
        status: str,
        exit_code: int,
        reason: str = "",
        restart_policy: SafeRestartPolicy | None = None,
        already_checkpointed: bool = False,
    ) -> int:
        if reason and not self._shutdown_reason:
            self._shutdown_reason = reason
        phase_reason = reason or self._shutdown_reason or status
        try:
            self._write_status(
                container=container,
                slo_status=self._slo_status,
                phase="shutting_down",
                restart_policy=restart_policy,
                extra={"shutdown_reason": phase_reason},
            )
        except Exception:
            logger.debug("headless_production.status_shutdown_write_failed", exc_info=True)

        if not already_checkpointed and force_checkpoint_on_shutdown(self.prod_cfg):
            self._save_checkpoint(container, telemetry, reason=f"shutdown:{phase_reason}")

        if container is not None:
            try:
                stop_hr = getattr(container, "stop_config_hot_reload", None)
                if callable(stop_hr):
                    stop_hr()
            except Exception:
                logger.exception("headless_production.stop_config_hot_reload_failed")

        self._unsubscribe_config_events(container)
        self._stop_observability(container)

        try:
            self._write_status(
                container=container,
                slo_status=self._slo_status,
                phase="stopped",
                restart_policy=restart_policy,
                extra={"shutdown_reason": phase_reason, "exit_code": exit_code},
            )
        except Exception:
            logger.debug("headless_production.status_stopped_write_failed", exc_info=True)

        telemetry.on_shutdown(status=status, exit_code=exit_code, reason=phase_reason)
        telemetry.end(status=status, exit_code=exit_code)
        return exit_code

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
