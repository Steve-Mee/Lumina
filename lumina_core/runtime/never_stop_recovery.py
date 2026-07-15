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
_STALL_SIGNAL_SUPERVISOR = "supervisor-loop"
_STALL_SIGNAL_RECONCILER = "trade-reconciler"


@dataclass(slots=True)
class RecoveryTickResult:
    dead_daemons: tuple[str, ...] = ()
    stalled_daemons: tuple[str, ...] = ()
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
    _stall_hit_counts: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.prod_cfg:
            object.__setattr__(self, "prod_cfg", load_production_section())
        if self.max_attempts == 3:
            object.__setattr__(
                self,
                "max_attempts",
                int(self.prod_cfg.get("max_in_process_recovery_attempts", 3) or 3),
            )

    def update_prod_cfg(self, prod_cfg: dict[str, Any]) -> None:
        object.__setattr__(self, "prod_cfg", dict(prod_cfg or {}))
        object.__setattr__(
            self,
            "max_attempts",
            int(self.prod_cfg.get("max_in_process_recovery_attempts", self.max_attempts) or self.max_attempts),
        )

    def _stall_consecutive_threshold(self) -> int:
        return max(1, int(self.prod_cfg.get("stall_consecutive_ticks", 2) or 2))

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

    def _derive_stalled(
        self,
        *,
        dead: set[str],
        stall_signals: tuple[str, ...] | list[str] | None,
    ) -> list[str]:
        """Map external stall signals to daemon names that are alive but not progressing."""
        if not stall_signals:
            # Clear consecutive counters when no stalls reported.
            self._stall_hit_counts.clear()
            return []

        registry = RuntimeDaemonRegistry.get()
        threshold = self._stall_consecutive_threshold()
        candidates: list[str] = []
        signal_set = {str(s).strip().lower() for s in stall_signals if str(s).strip()}

        mapping = {
            "supervisor_tick_stale": _STALL_SIGNAL_SUPERVISOR,
            "supervisor_tick_missing": _STALL_SIGNAL_SUPERVISOR,
            "supervisor-loop": _STALL_SIGNAL_SUPERVISOR,
            "reconciler_status_stale": _STALL_SIGNAL_RECONCILER,
            "reconciler_status_missing": _STALL_SIGNAL_RECONCILER,
            "trade-reconciler": _STALL_SIGNAL_RECONCILER,
        }
        for sig in signal_set:
            for key, daemon in mapping.items():
                if sig == key or sig.startswith(f"{key}:"):
                    candidates.append(daemon)

        stalled: list[str] = []
        seen: set[str] = set()
        for name in candidates:
            if name in seen or name in dead:
                continue
            seen.add(name)
            # Only treat as stalled if registered and still alive (stuck).
            if name in registry.names() and registry.is_alive(name):
                hits = self._stall_hit_counts.get(name, 0) + 1
                self._stall_hit_counts[name] = hits
                if hits >= threshold:
                    stalled.append(name)
            elif name not in registry.names():
                # Unregistered but signalled — still count for process escalation path.
                hits = self._stall_hit_counts.get(name, 0) + 1
                self._stall_hit_counts[name] = hits
                if hits >= threshold:
                    stalled.append(name)

        # Decay counters for daemons not in this tick's candidate set.
        for name in list(self._stall_hit_counts.keys()):
            if name not in seen:
                self._stall_hit_counts.pop(name, None)

        return stalled

    def _handle_one(
        self,
        name: str,
        *,
        restarted: list[str],
        blocked: list[str],
        failed: list[str],
        telemetry_emit: Callable[[str], None] | None,
        telemetry: Any | None,
        force_process_restart_on_block: bool = False,
    ) -> None:
        remaining = self._backoff_remaining(name)
        if remaining > 0:
            blocked.append(name)
            return

        if not self.restart_policy.in_process_restart_allowed(daemon_name=name):
            blocked.append(name)
            self._record_attempt()
            if force_process_restart_on_block or name == _STALL_SIGNAL_SUPERVISOR:
                self.restart_policy.request_process_restart(f"stall_or_dead_blocked:{name}")
            if telemetry is not None:
                on_blocked = getattr(telemetry, "on_daemon_restart_failed", None)
                if callable(on_blocked):
                    on_blocked(name)
                elif telemetry_emit is not None:
                    telemetry_emit(f"runtime.recovery.daemon_blocked:{name}")
            return

        if self._restart_daemon(name):
            restarted.append(name)
            self._clear_backoff(name)
            self._stall_hit_counts.pop(name, None)
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

    def tick(
        self,
        *,
        telemetry_emit: Callable[[str], None] | None = None,
        telemetry: Any | None = None,
        stall_signals: tuple[str, ...] | list[str] | None = None,
    ) -> RecoveryTickResult:
        registry = RuntimeDaemonRegistry.get()
        dead = tuple(registry.dead_daemons())
        stalled = tuple(self._derive_stalled(dead=set(dead), stall_signals=stall_signals))

        if not dead and not stalled:
            return RecoveryTickResult(message="all daemons alive")

        restarted: list[str] = []
        blocked: list[str] = []
        failed: list[str] = []

        # Prefer dead restarts; then soft-stall recovery for alive-but-stuck.
        handled: set[str] = set()
        for name in dead:
            handled.add(name)
            self._handle_one(
                name,
                restarted=restarted,
                blocked=blocked,
                failed=failed,
                telemetry_emit=telemetry_emit,
                telemetry=telemetry,
                force_process_restart_on_block=True,
            )

        if stalled:
            if telemetry is not None:
                on_stalled = getattr(telemetry, "on_stalled_daemons", None)
                if callable(on_stalled):
                    on_stalled(stalled)
            for name in stalled:
                if name in handled:
                    continue
                handled.add(name)
                # Soft stall: for reconciler try in-process restart; for supervisor REAL → process restart.
                self._handle_one(
                    name,
                    restarted=restarted,
                    blocked=blocked,
                    failed=failed,
                    telemetry_emit=telemetry_emit,
                    telemetry=telemetry,
                    force_process_restart_on_block=True,
                )

        escalated = False
        if self._attempts_in_window() >= self.max_attempts:
            escalated = True
            reason_bits = list(dead) + [f"stall:{s}" for s in stalled]
            self.restart_policy.request_process_restart(
                f"in_process_recovery_exhausted:{','.join(reason_bits) or 'unknown'}"
            )
            if telemetry_emit is not None:
                telemetry_emit("runtime.recovery.escalated")

        return RecoveryTickResult(
            dead_daemons=dead,
            stalled_daemons=stalled,
            restarted=tuple(restarted),
            blocked=tuple(blocked),
            failed=tuple(failed),
            escalated=escalated,
            message="recovery tick complete" if (dead or stalled) else "all daemons alive",
        )
