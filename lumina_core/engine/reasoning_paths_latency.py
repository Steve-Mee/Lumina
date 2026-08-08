"""Fast-path / SLA / consensus path helpers mixed into ReasoningService."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from lumina_core.order_gatekeeper import session_guard_allows_trading
from lumina_core.risk.regime_detector import RegimeSnapshot
from .errors import format_error_code
from lumina_core.logging_utils import correlation_id, get_logger, record_reasoning_latency_monitoring

logger = get_logger("lumina.reasoning.service")


class ReasoningPathsLatencyMixin:
    """Latency SLA, fast-path toggles, inference routing, and consensus paths."""

    __slots__ = ()
    _sla_breach_streak: int

    def _set_fast_path_only(self, enabled: bool, reason: str) -> None:
        app = self._app()
        current = bool(getattr(app, "FAST_PATH_ONLY", False))
        if current == enabled:
            return
        setattr(app, "FAST_PATH_ONLY", enabled)
        state = "enabled" if enabled else "disabled"
        app.logger.warning(f"FAST_PATH_ONLY {state} (reasoning): {reason}")
        try:
            logger.info(
                "reasoning.fast_path_toggle",
                extra={"event_data": {"event": "reasoning.fast_path_toggle", "enabled": enabled, "reason": reason}},
            )
        except Exception:
            pass

    def _record_latency(self, elapsed_ms: float, source: str) -> None:
        app = self._app()
        if elapsed_ms > self.latency_sla_ms:
            self._sla_breach_streak += 1
            self._sla_recovery_streak = 0
            if self._sla_breach_streak >= 2:
                try:
                    logger.warning(
                        "reasoning.sla_breach",
                        extra={
                            "event_data": {
                                "event": "reasoning.sla_breach",
                                "source": source,
                                "elapsed_ms": elapsed_ms,
                                "sla_ms": self.latency_sla_ms,
                                "streak": self._sla_breach_streak,
                            }
                        },
                    )
                except Exception:
                    pass
                self._set_fast_path_only(
                    True,
                    f"{source} latency {elapsed_ms:.1f}ms above SLA {self.latency_sla_ms:.1f}ms",
                )
        else:
            self._sla_recovery_streak += 1
            self._sla_breach_streak = 0
            if self._sla_recovery_streak >= 4:
                self._set_fast_path_only(False, f"{source} latency recovered ({elapsed_ms:.1f}ms)")

        setattr(app, "REASONING_LATENCY_MS", round(float(elapsed_ms), 2))
        try:
            record_reasoning_latency_monitoring(
                source=source,
                elapsed_ms=float(elapsed_ms),
                sla_ms=float(self.latency_sla_ms),
                breach_streak=int(self._sla_breach_streak),
                fast_path_only=bool(getattr(app, "FAST_PATH_ONLY", False)),
                daily_pnl=float(getattr(self.engine, "realized_pnl_today", 0.0) or 0.0),
            )
        except Exception:
            pass

    def _fast_path_only_enabled(self) -> bool:
        app = self._app()
        return bool(getattr(app, "FAST_PATH_ONLY", False))

    def _session_trading_allowed(self) -> tuple[bool, str]:
        allowed, reason = session_guard_allows_trading(self.engine)
        return bool(allowed), str(reason)

    @staticmethod
    def _route_agent_styles(agent_styles: dict[str, str], snapshot: RegimeSnapshot) -> dict[str, str]:
        ordered_names = [name for name in snapshot.adaptive_policy.agent_route if name in agent_styles]
        if not ordered_names:
            ordered_names = list(agent_styles.keys())
        if snapshot.adaptive_policy.high_risk and "risk" in agent_styles and "risk" not in ordered_names:
            ordered_names.insert(0, "risk")
        if snapshot.adaptive_policy.high_risk:
            ordered_names = ordered_names[: max(1, min(2, len(ordered_names)))]
        return {name: agent_styles[name] for name in ordered_names}


