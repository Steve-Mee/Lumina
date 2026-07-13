"""Mode-aware safe-boundary policy for in-process and process-level restarts."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.evolution.promotion_readiness import _check_reconciler, _reconciler_status_path
from lumina_core.runtime.production_config import load_production_section

logger = logging.getLogger("lumina.runtime.safe_restart")

SAFE_RESTART_EXIT_CODE = 42
PREFLIGHT_FAIL_EXIT_CODE = 2


@dataclass(slots=True)
class SafeRestartDecision:
    allowed: bool
    deferred: bool
    reasons: tuple[str, ...] = ()
    message: str = ""


@dataclass(slots=True)
class DeferredRestartState:
    age_s: float
    should_alert: bool
    should_escalate: bool
    reasons: tuple[str, ...] = ()


@dataclass(slots=True)
class SafeRestartPolicy:
    mode: str
    prod_cfg: dict[str, Any] = field(default_factory=dict)
    _last_recovery_at: float = field(default=0.0, repr=False)
    _restart_requested: bool = field(default=False, repr=False)
    _restart_reason: str = field(default="", repr=False)
    _restart_requested_at: float = field(default=0.0, repr=False)
    _deferred_alert_sent: bool = field(default=False, repr=False)
    _deferred_escalation_sent: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if not self.prod_cfg:
            self.prod_cfg = load_production_section()

    @staticmethod
    def _norm_mode(mode: str) -> str:
        m = str(mode or "").strip().lower()
        if m in {"live"}:
            return "real"
        return m if m else "sim"

    def _slo_cfg(self) -> dict[str, Any]:
        slo = self.prod_cfg.get("slo")
        return slo if isinstance(slo, dict) else {}

    def _has_open_positions(self, container: Any) -> bool:
        engine = getattr(container, "engine", None)
        pos_state = getattr(engine, "position_state", None) if engine is not None else None
        if pos_state is not None:
            for attr in ("live_qty", "sim_qty", "paper_qty"):
                qty = int(getattr(pos_state, attr, 0) or 0)
                if qty != 0:
                    return True
            has_open = getattr(pos_state, "has_open_position", None)
            if callable(has_open) and has_open():
                return True

        broker = getattr(container, "broker", None)
        get_positions = getattr(broker, "get_positions", None) if broker is not None else None
        if callable(get_positions):
            try:
                positions = get_positions()
                if positions:
                    return True
            except Exception:
                logger.debug("safe_restart.get_positions_failed", exc_info=True)
        return False

    def _reconciler_clean(self) -> tuple[bool, str | None]:
        ok, reason = _check_reconciler(status_path=_reconciler_status_path())
        slo = self._slo_cfg()
        max_pending = int(slo.get("reconcile_pending_max", 0) or 0)
        if not ok:
            return False, reason
        try:
            path = _reconciler_status_path()
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                pending = int(data.get("pending_count", 0) or 0)
                if pending > max_pending:
                    return False, f"reconciler_pending:{pending}>{max_pending}"
        except Exception as exc:
            return False, f"reconciler_read_error:{exc}"
        return True, None

    def _session_gap_ok(self) -> tuple[bool, str | None]:
        try:
            from lumina_core.risk.session_guard import SessionGuard

            guard = SessionGuard()
            if not guard.is_trading_session():
                return True, None
            return False, "inside_trading_session"
        except Exception as exc:
            return False, f"session_guard_error:{type(exc).__name__}"

    def in_process_restart_allowed(self, *, daemon_name: str) -> bool:
        mode = self._norm_mode(self.mode)
        if mode == "real" and daemon_name == "supervisor-loop":
            return False
        return True

    def evaluate_process_restart(self, container: Any) -> SafeRestartDecision:
        mode = self._norm_mode(self.mode)
        reasons: list[str] = []

        cooldown_s = float(self._slo_cfg().get("supervisor_tick_stale_s", 120) or 120)
        if self._last_recovery_at and (time.time() - self._last_recovery_at) < cooldown_s:
            reasons.append(f"recovery_cooldown:{cooldown_s}s")

        reconciled, recon_reason = self._reconciler_clean()
        if not reconciled and recon_reason:
            reasons.append(recon_reason)

        if self._has_open_positions(container):
            reasons.append("open_positions")

        if mode == "real":
            session_ok, session_reason = self._session_gap_ok()
            if not session_ok and session_reason:
                reasons.append(session_reason)

        if reasons:
            return SafeRestartDecision(
                allowed=False,
                deferred=True,
                reasons=tuple(reasons),
                message="Process restart deferred until safe boundary",
            )
        return SafeRestartDecision(
            allowed=True,
            deferred=False,
            message="Safe to restart process",
        )

    def request_process_restart(self, reason: str) -> None:
        if not self._restart_requested:
            self._restart_requested_at = time.time()
        self._restart_requested = True
        self._restart_reason = str(reason)

    def restart_requested(self) -> bool:
        return self._restart_requested

    def restart_reason(self) -> str:
        return self._restart_reason

    def deferred_restart_age_s(self) -> float | None:
        if not self._restart_requested or not self._restart_requested_at:
            return None
        return time.time() - self._restart_requested_at

    def evaluate_deferred_restart(self, container: Any) -> DeferredRestartState:
        decision = self.evaluate_process_restart(container)
        age_s = self.deferred_restart_age_s() or 0.0
        alert_s = float(self.prod_cfg.get("deferred_restart_alert_s", 300) or 300)
        max_s = float(self._slo_cfg().get("deferred_restart_max_s", 3600) or 3600)

        should_alert = (
            self._restart_requested
            and decision.deferred
            and age_s >= alert_s
            and not self._deferred_alert_sent
        )
        should_escalate = (
            self._restart_requested
            and decision.deferred
            and age_s >= max_s
            and not self._deferred_escalation_sent
        )

        return DeferredRestartState(
            age_s=age_s,
            should_alert=should_alert,
            should_escalate=should_escalate,
            reasons=decision.reasons,
        )

    def mark_deferred_alert_sent(self) -> None:
        self._deferred_alert_sent = True

    def mark_deferred_escalation_sent(self) -> None:
        self._deferred_escalation_sent = True

    def mark_recovery_attempt(self) -> None:
        self._last_recovery_at = time.time()

    def execute_safe_restart(self, container: Any) -> int | None:
        """Save state and return exit code if restart is allowed, else None."""
        decision = self.evaluate_process_restart(container)
        if not decision.allowed:
            logger.info(
                "safe_restart.deferred reasons=%s",
                ",".join(decision.reasons),
            )
            return None
        engine = getattr(container, "engine", None)
        if engine is not None:
            try:
                engine.save_state()
            except Exception:
                logger.exception("safe_restart.save_state_failed")
                return None
        exit_code = int(self.prod_cfg.get("safe_restart_exit_code", SAFE_RESTART_EXIT_CODE) or SAFE_RESTART_EXIT_CODE)
        logger.warning(
            "safe_restart.executing reason=%s exit_code=%d",
            self._restart_reason or "scheduled",
            exit_code,
        )
        return exit_code

    def write_deferred_status(self, container: Any, path: Path | None = None) -> None:
        out = path or Path("state/safe_restart_deferred.json")
        decision = self.evaluate_process_restart(container)
        age_s = self.deferred_restart_age_s()
        payload = {
            "deferred": decision.deferred,
            "allowed": decision.allowed,
            "reasons": list(decision.reasons),
            "restart_requested": self._restart_requested,
            "restart_reason": self._restart_reason,
            "deferred_restart_age_s": round(age_s, 1) if age_s is not None else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
