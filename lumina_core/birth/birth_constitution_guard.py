"""Birth-specific constitution checks during SIM (ADR-0013)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lumina_bible.bible_engine import BibleEngine, DEFAULT_BIBLE

from lumina_core.agent_orchestration.schemas import ConstitutionViolation
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.constitution_guard")


@dataclass(slots=True)
class BirthConstitutionGuard:
    violations: int = 0
    violation_reasons: list[str] = field(default_factory=list)
    _news_cfg: dict[str, Any] = field(default_factory=dict)
    event_bus: Any | None = None
    mode: str = "birth"

    def __post_init__(self) -> None:
        try:
            engine = BibleEngine()
            layer = engine.evolvable_layer
            news = layer.get("news_avoidance") if isinstance(layer, dict) else {}
            self._news_cfg = news if isinstance(news, dict) else DEFAULT_BIBLE["evolvable_layer"]["news_avoidance"]
        except Exception:
            self._news_cfg = DEFAULT_BIBLE["evolvable_layer"]["news_avoidance"]

    def check_entry(
        self,
        *,
        tick: dict[str, Any],
        side: int,
        stop_pct: float,
        equity: float,
    ) -> tuple[bool, str]:
        if side == 0:
            return True, ""

        if float(tick.get("news_window_active", 0.0) or 0.0) > 0.5:
            self._record("news_window_entry_blocked")
            return False, "news_window"

        if stop_pct <= 0.0 or stop_pct > 0.02:
            self._record("invalid_stop_pct")
            return False, "invalid_stop"

        risk_usd = float(equity) * float(stop_pct)
        max_risk = float(equity) * 0.01
        if risk_usd > max_risk:
            self._record("risk_exceeds_1pct")
            return False, "risk_cap"

        return True, ""

    def _record(self, reason: str) -> None:
        self.violations += 1
        if len(self.violation_reasons) < 50:
            self.violation_reasons.append(reason)
        self._publish_violation(reason)

    def _publish_violation(self, reason: str) -> None:
        if self.event_bus is None:
            return
        try:
            payload = ConstitutionViolation(
                principle_name="birth_constitution_guard",
                severity="warning",
                description=reason,
                detail=f"reason={reason}",
                mode=self.mode,
            ).model_dump(mode="json")
            self.event_bus.publish_validated(
                topic="safety.constitution.violation",
                producer="birth.constitution_guard",
                payload=payload,
                metadata={"reason": reason, "mode": self.mode},
            )
        except Exception:
            logger.exception("Failed to publish birth ConstitutionViolation (non-fatal)")

    def reset(self) -> None:
        self.violations = 0
        self.violation_reasons.clear()
