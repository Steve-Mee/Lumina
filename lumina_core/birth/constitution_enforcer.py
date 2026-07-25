"""ConstitutionEnforcer (single responsibility).

Subscribes to safety.constitution.violation events.
For birth mode: immediately forces fail-closed behavior by publishing
a birth.curriculum.aborted event and (optionally) raising a hard terminal signal
that callers must respect.

This is intentionally separate from CurriculumOrchestrator so that
constitution enforcement has its own clear ownership and test surface.
"""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import (
    BirthCurriculumStageAborted,
    ConstitutionViolation,
)

logger = logging.getLogger("lumina.birth.constitution_enforcer")

TOPIC_VIOLATION = "safety.constitution.violation"
TOPIC_ABORTED = "birth.curriculum.aborted"


# Soft severities: count for audit / stage metrics, do NOT abort the training loop.
# Hard severities: single fail-closed abort that callers must honor (host stop).
_SOFT_SEVERITIES = frozenset({"warning", "info", "soft"})
_HARD_SEVERITIES = frozenset({"critical", "fatal", "error", "hard"})


class ConstitutionEnforcer:
    """Dedicated fail-closed constitution handler for the birth bounded context."""

    def __init__(self, event_bus: EventBus) -> None:
        if event_bus is None:
            raise ValueError("ConstitutionEnforcer requires EventBus")
        self.bus = event_bus
        self._token: str | None = None
        self._violations: list[dict[str, Any]] = []
        self._hard_aborted: bool = False
        self._soft_logged: int = 0

    def attach(self) -> str:
        if self._token is None:
            self._token = self.bus.subscribe(TOPIC_VIOLATION, self._on_violation)
        return self._token or ""

    def detach(self) -> None:
        if self._token:
            try:
                self.bus.unsubscribe(self._token)
            except Exception:
                pass
            self._token = None

    def _on_violation(self, event: DomainEvent) -> None:
        try:
            v = event.typed_payload(ConstitutionViolation)
        except Exception:
            v = ConstitutionViolation(
                principle_name="unknown",
                severity="critical",
                description=str(event.payload),
                mode="birth",
            )

        if str(v.mode or "").lower() != "birth":
            return

        self._violations.append(v.model_dump(mode="json"))
        severity = str(v.severity or "critical").strip().lower()

        # Training feedback (e.g. invalid_stop_pct warning) must not spam ABORT theater.
        # Hard abort only on explicit hard severities. Certificate still uses guard counts.
        if severity not in _HARD_SEVERITIES:
            self._soft_logged += 1
            if self._soft_logged <= 3 or self._soft_logged % 100 == 0:
                logger.warning(
                    "birth.constitution.soft_violation principle=%s severity=%s count=%s detail=%s",
                    v.principle_name,
                    severity,
                    len(self._violations),
                    (v.description or "")[:120],
                )
            return

        # Hard fail-closed: abort at most once until reset (no 3000-line spam).
        if self._hard_aborted:
            return
        self._hard_aborted = True

        abort = BirthCurriculumStageAborted(
            stage=None,
            reason="constitution_violation",
            detail={
                "principle_name": v.principle_name,
                "severity": v.severity,
                "description": v.description,
                "detail": v.detail,
            },
            violations=len(self._violations),
        )
        self.bus.publish_validated(
            topic=TOPIC_ABORTED,
            producer="birth.constitution_enforcer",
            payload=abort.model_dump(mode="json"),
        )
        logger.critical(
            "CONSTITUTION FAIL-CLOSED: %s (severity=%s) — birth curriculum aborted (violations=%s)",
            v.principle_name,
            v.severity,
            len(self._violations),
        )

    def violation_count(self) -> int:
        return len(self._violations)

    def is_hard_aborted(self) -> bool:
        return self._hard_aborted

    def reset_abort_state(self) -> None:
        """Allow a new hard abort after intentional stage/curriculum reset."""
        self._hard_aborted = False


__all__ = ["ConstitutionEnforcer"]
