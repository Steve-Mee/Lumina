"""Telemetry bridge for production headless runtime."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

logger = logging.getLogger("lumina.runtime.telemetry")

M_UPTIME = "lumina_uptime_seconds"
M_HEARTBEAT_TOTAL = "lumina_headless_heartbeat_total"
M_SLO_EVAL_TOTAL = "lumina_headless_slo_eval_total"
M_RECOVERY_TICK_TOTAL = "lumina_headless_recovery_tick_total"


def _try_emit_launcher_event(name: str, **payload: Any) -> None:
    try:
        from lumina_launcher.telemetry.hooks import emit_launcher_event

        emit_launcher_event(name, **payload)
    except Exception:
        logger.debug("headless_telemetry.launcher_event_skipped name=%s", name, exc_info=True)


class HeadlessTelemetry:
    """Bridge ObservabilityService metrics with launcher JSONL events."""

    def __init__(self, *, mode: str, container: Any | None = None, started_at: float | None = None) -> None:
        self.mode = str(mode or "sim").strip().lower()
        self.container = container
        self._started = False
        self._started_at = started_at if started_at is not None else time.time()
        self._alert_count = 0

    @property
    def observability(self) -> Any | None:
        if self.container is None:
            return None
        return getattr(self.container, "observability_service", None)

    @property
    def alert_count(self) -> int:
        return self._alert_count

    def _collector(self) -> Any | None:
        obs = self.observability
        if obs is None:
            return None
        return getattr(obs, "collector", None)

    def _inc_counter(self, name: str, *, help_: str = "") -> None:
        collector = self._collector()
        if collector is None:
            return
        inc = getattr(collector, "inc", None)
        if callable(inc):
            try:
                inc(name, help_=help_)
            except TypeError:
                try:
                    inc(name)
                except Exception:
                    logger.debug("headless_telemetry.counter_failed name=%s", name, exc_info=True)
            except Exception:
                logger.debug("headless_telemetry.counter_failed name=%s", name, exc_info=True)

    def _set_gauge(self, name: str, value: float, *, help_: str = "") -> None:
        collector = self._collector()
        if collector is None:
            return
        set_fn = getattr(collector, "set", None)
        if callable(set_fn):
            try:
                set_fn(name, float(value), help_=help_)
            except TypeError:
                try:
                    set_fn(name, float(value))
                except Exception:
                    logger.debug("headless_telemetry.gauge_failed name=%s", name, exc_info=True)
            except Exception:
                logger.debug("headless_telemetry.gauge_failed name=%s", name, exc_info=True)

    def begin(self, *, run_id: str = "") -> None:
        self._started = True
        _try_emit_launcher_event(
            "runtime.headless.begin",
            mode=self.mode,
            run_id=run_id or None,
        )
        logger.info("runtime.headless.begin mode=%s", self.mode)

    def end(self, *, status: str = "ok", exit_code: int = 0) -> None:
        _try_emit_launcher_event(
            "runtime.headless.end",
            mode=self.mode,
            status=status,
            exit_code=exit_code,
            alert_count=self._alert_count,
        )

    def emit(self, event: str, **payload: Any) -> None:
        _try_emit_launcher_event(event, mode=self.mode, **payload)
        logger.info("runtime.telemetry event=%s payload=%s", event, payload)

    def alert(self, message: str, *, alert_type: str = "runtime", data: dict[str, Any] | None = None) -> None:
        self._alert_count += 1
        obs = self.observability
        if obs is not None:
            send = getattr(obs, "send_alert", None)
            if callable(send):
                try:
                    send(alert_type, message, data=data or {})
                    return
                except TypeError:
                    try:
                        send(alert_type, message)
                        return
                    except Exception:
                        logger.debug("headless_telemetry.alert_failed", exc_info=True)
                except Exception:
                    logger.debug("headless_telemetry.alert_failed", exc_info=True)
        self.emit(f"runtime.alert.{alert_type}", message=message, data=data or {})

    def record_uptime_tick(self) -> None:
        uptime = round(time.time() - self._started_at, 1)
        self._set_gauge(M_UPTIME, uptime, help_="Headless production process uptime in seconds")
        self._inc_counter(
            M_HEARTBEAT_TOTAL,
            help_="Total headless production heartbeat ticks",
        )

    def record_slo_eval_tick(self) -> None:
        self._inc_counter(M_SLO_EVAL_TOTAL, help_="Total headless SLO evaluation ticks")

    def record_recovery_tick(self) -> None:
        self._inc_counter(M_RECOVERY_TICK_TOTAL, help_="Total headless recovery ticks")

    def on_preflight_failed(self, reasons: tuple[str, ...]) -> None:
        self.alert(
            f"Runtime preflight failed: {'; '.join(reasons)}",
            alert_type="preflight_failed",
            data={"reasons": list(reasons)},
        )
        self.emit("runtime.preflight.failed", reasons=list(reasons))

    def on_slo_breach(self, breaches: tuple[str, ...]) -> None:
        self.alert(
            f"Runtime SLO breach: {'; '.join(breaches)}",
            alert_type="slo_breach",
            data={"breaches": list(breaches)},
        )
        self.emit("runtime.slo.breach", breaches=list(breaches))

    def on_recovery_escalated(self, reason: str) -> None:
        self.alert(f"Recovery escalated: {reason}", alert_type="recovery_escalated")
        self.emit("runtime.recovery.escalated", reason=reason)

    def on_safe_restart_scheduled(self, reason: str) -> None:
        self.emit("runtime.restart.scheduled", reason=reason)

    def on_restart_deferred(self, reasons: tuple[str, ...], *, age_s: float) -> None:
        self.alert(
            f"Process restart deferred ({age_s:.0f}s): {'; '.join(reasons)}",
            alert_type="restart_deferred",
            data={"reasons": list(reasons), "age_s": age_s},
        )
        self.emit("runtime.restart.deferred", reasons=list(reasons), age_s=age_s)

    def on_reconciliation_issue(self, issues: tuple[str, ...]) -> None:
        if not issues:
            return
        self.alert(
            f"Reconciliation issues: {'; '.join(issues)}",
            alert_type="reconciliation_issue",
            data={"issues": list(issues)},
        )
        self.emit("runtime.reconciliation.issue", issues=list(issues))

    def on_position_drift(self, drift: str) -> None:
        self.alert(
            f"Position drift detected: {drift}",
            alert_type="position_drift",
            data={"drift": drift},
        )
        self.emit("runtime.reconciliation.position_drift", drift=drift)

    def on_daemon_restart_failed(self, daemon_name: str) -> None:
        self.alert(
            f"Daemon restart failed: {daemon_name}",
            alert_type="daemon_restart_failed",
            data={"daemon": daemon_name},
        )
        self.emit("runtime.recovery.daemon_restart_failed", daemon=daemon_name)

    def event_sink(self) -> Callable[[str], None]:
        return lambda event: self.emit(event)

    def smoke_summary(self) -> dict[str, Any]:
        return {
            "alert_count": self._alert_count,
            "uptime_s": round(time.time() - self._started_at, 1),
            "mode": self.mode,
        }
