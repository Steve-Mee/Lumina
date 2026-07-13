"""In-process never-stop recovery for production headless runtime."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from lumina_core.runtime.daemon_registry import RuntimeDaemonRegistry
from lumina_core.runtime.production_config import load_production_section
from lumina_core.runtime.safe_restart_policy import SafeRestartPolicy
from lumina_core.threading_utils import start_daemon

logger = logging.getLogger("lumina.runtime.recovery")

_DEFAULT_BACKOFF_S = 5.0
_MAX_BACKOFF_S = 120.0


@dataclass(slots=True)
class RecoveryTickResult:
    dead_daemons: tuple[str, ...] = ()
    restarted: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    escalated: bool = False
    message: str = ""


@dataclass(slots=True)
class NeverStopRecovery:
    mode: str
    container: Any
    restart_policy: SafeRestartPolicy
    prod_cfg: dict[str, Any] = field(default_factory=dict)
    max_attempts: int = 3
    _attempt_timestamps: deque[float] = field(default_factory=deque, repr=False)
    _daemon_backoff_until: dict[str, float] = field(default_factory=dict, repr=False)
    _daemon_fail_counts: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.prod_cfg:
            object.__setattr__(self, "prod_cfg", load_production_section())
        if self.max_attempts == 3:
            object.__setattr__(
                self,
                "max_attempts",
                int(self.prod_cfg.get("max_in_process_recovery_attempts", 3) or 3),
            )

    def _record_attempt(self) -> None:
        now = time.time()
        self._attempt_timestamps.append(now)
        cutoff = now - 3600.0
        while self._attempt_timestamps and self._attempt_timestamps[0] < cutoff:
            self._attempt_timestamps.popleft()

    def _attempts_in_window(self) -> int:
        return len(self._attempt_timestamps)

    def _backoff_remaining(self, name: str) -> float:
        until = self._daemon_backoff_until.get(name, 0.0)
        return max(0.0, until - time.time())

    def _schedule_backoff(self, name: str) -> None:
        fails = self._daemon_fail_counts.get(name, 0) + 1
        self._daemon_fail_counts[name] = fails
        delay = min(_MAX_BACKOFF_S, _DEFAULT_BACKOFF_S * (2 ** (fails - 1)))
        self._daemon_backoff_until[name] = time.time() + delay

    def _clear_backoff(self, name: str) -> None:
        self._daemon_backoff_until.pop(name, None)
        self._daemon_fail_counts.pop(name, None)

    def _restart_reconciler(self) -> bool:
        reconciler = getattr(self.container, "trade_reconciler", None)
        if reconciler is None:
            return False
        try:
            stop = getattr(reconciler, "stop", None)
            if callable(stop):
                stop()
            start = getattr(reconciler, "start", None)
            if callable(start):
                start_daemon(start, name="trade-reconciler", register=True, target_factory=start)
                return True
        except Exception:
            logger.exception("never_stop.reconciler_restart_failed")
        return False

    def _restart_daemon(self, name: str) -> bool:
        registry = RuntimeDaemonRegistry.get()
        if not self.restart_policy.in_process_restart_allowed(daemon_name=name):
            logger.warning("never_stop.in_process_restart_blocked daemon=%s mode=%s", name, self.mode)
            return False

        if name == "trade-reconciler":
            return self._restart_reconciler()

        def _start_fn(target: Callable[[], None], thread_name: str | None):
            return start_daemon(target, name=thread_name, register=True, target_factory=target)

        restarted = registry.restart_daemon(name, start_fn=_start_fn)
        if restarted:
            logger.warning("never_stop.daemon_restarted daemon=%s", name)
        return restarted

    def tick(
        self,
        *,
        telemetry_emit: Callable[[str], None] | None = None,
        telemetry: Any | None = None,
    ) -> RecoveryTickResult:
        registry = RuntimeDaemonRegistry.get()
        dead = tuple(registry.dead_daemons())
        if not dead:
            return RecoveryTickResult(message="all daemons alive")

        restarted: list[str] = []
        blocked: list[str] = []
        failed: list[str] = []

        for name in dead:
            remaining = self._backoff_remaining(name)
            if remaining > 0:
                blocked.append(name)
                continue

            if not self.restart_policy.in_process_restart_allowed(daemon_name=name):
                blocked.append(name)
                self._record_attempt()
                if telemetry is not None:
                    on_blocked = getattr(telemetry, "on_daemon_restart_failed", None)
                    if callable(on_blocked):
                        on_blocked(name)
                    elif telemetry_emit is not None:
                        telemetry_emit(f"runtime.recovery.daemon_blocked:{name}")
                continue

            if self._restart_daemon(name):
                restarted.append(name)
                self._clear_backoff(name)
                self._record_attempt()
                self.restart_policy.mark_recovery_attempt()
                if telemetry_emit is not None:
                    telemetry_emit(f"runtime.recovery.daemon_restarted:{name}")
            else:
                failed.append(name)
                self._schedule_backoff(name)
                self._record_attempt()
                if telemetry is not None:
                    on_failed = getattr(telemetry, "on_daemon_restart_failed", None)
                    if callable(on_failed):
                        on_failed(name)
                    elif telemetry_emit is not None:
                        telemetry_emit(f"runtime.recovery.daemon_restart_failed:{name}")

        escalated = False
        if self._attempts_in_window() >= self.max_attempts:
            escalated = True
            self.restart_policy.request_process_restart(
                f"in_process_recovery_exhausted:{','.join(dead)}"
            )
            if telemetry_emit is not None:
                telemetry_emit("runtime.recovery.escalated")

        return RecoveryTickResult(
            dead_daemons=dead,
            restarted=tuple(restarted),
            blocked=tuple(blocked),
            failed=tuple(failed),
            escalated=escalated,
            message="recovery tick complete",
        )
