"""Birth-specific constitution checks during SIM (ADR-0013).

Soft blocks (entry rejected by the guard) are NOT graduation violations.
Hard violations are breaches that would count against stage pass / certificate.
Raptor v6: blocked ≠ violated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from lumina_bible.bible_engine import BibleEngine, DEFAULT_BIBLE

from lumina_core.agent_orchestration.schemas import ConstitutionViolation
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.constitution_guard")

_BIBLE: dict[str, Any] = cast(dict[str, Any], DEFAULT_BIBLE)

# Entry rejections — constitution held; do not fail stage graduation.
_SOFT_BLOCK_REASONS = frozenset(
    {
        "news_window_entry_blocked",
        "invalid_stop_pct",
        "risk_exceeds_1pct",
        "news_window",
        "invalid_stop",
        "risk_cap",
    }
)


def _default_news_avoidance_cfg() -> dict[str, Any]:
    layer = _BIBLE.get("evolvable_layer", {})
    if isinstance(layer, dict):
        news = layer.get("news_avoidance", {})
        if isinstance(news, dict):
            return news
    return {}


@dataclass(slots=True)
class BirthConstitutionGuard:
    """Guard for birth SIM entries.

    - ``violations``: hard breaches used by stage pass / certificate (must stay 0).
    - ``soft_blocks``: successful rejections (training signal / HUD only).
    """

    violations: int = 0
    soft_blocks: int = 0
    violation_reasons: list[str] = field(default_factory=list)
    soft_block_reasons: list[str] = field(default_factory=list)
    _news_cfg: dict[str, Any] = field(default_factory=dict)
    event_bus: Any | None = None
    mode: str = "birth"

    def __post_init__(self) -> None:
        try:
            engine = BibleEngine()
            layer = engine.evolvable_layer
            news = layer.get("news_avoidance") if isinstance(layer, dict) else {}
            self._news_cfg = news if isinstance(news, dict) else _default_news_avoidance_cfg()
        except Exception:
            self._news_cfg = _default_news_avoidance_cfg()

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
            self._record_soft("news_window_entry_blocked")
            return False, "news_window"

        if stop_pct <= 0.0 or stop_pct > 0.02:
            self._record_soft("invalid_stop_pct")
            return False, "invalid_stop"

        risk_usd = float(equity) * float(stop_pct)
        max_risk = float(equity) * 0.01
        if risk_usd > max_risk:
            self._record_soft("risk_exceeds_1pct")
            return False, "risk_cap"

        return True, ""

    def record_hard_violation(self, reason: str) -> None:
        """Explicit hard breach (counts toward stage pass / certificate)."""
        self.violations += 1
        if len(self.violation_reasons) < 50:
            self.violation_reasons.append(reason)
        self._publish_violation(reason, severity="critical")

    def _record_soft(self, reason: str) -> None:
        """Entry blocked by guard — constitution held; do not fail graduation."""
        self.soft_blocks += 1
        if len(self.soft_block_reasons) < 50:
            self.soft_block_reasons.append(reason)
        self._publish_violation(reason, severity="warning")

    def _record(self, reason: str) -> None:
        """Backward-compatible alias: soft block for known entry rejections."""
        if reason in _SOFT_BLOCK_REASONS or any(
            reason.startswith(r) for r in ("news_window", "invalid_stop", "risk_")
        ):
            self._record_soft(reason)
            return
        self.record_hard_violation(reason)

    def _publish_violation(self, reason: str, *, severity: str = "warning") -> None:
        if self.event_bus is None:
            return
        try:
            payload = ConstitutionViolation(
                principle_name="birth_constitution_guard",
                severity=severity,
                description=reason,
                detail=f"reason={reason}",
                mode=self.mode,
            ).model_dump(mode="json")
            self.event_bus.publish_validated(
                topic="safety.constitution.violation",
                producer="birth.constitution_guard",
                payload=payload,
                metadata={"reason": reason, "mode": self.mode, "severity": severity},
            )
        except Exception:
            logger.exception("Failed to publish birth ConstitutionViolation (non-fatal)")

    def reset(self) -> None:
        self.violations = 0
        self.soft_blocks = 0
        self.violation_reasons.clear()
        self.soft_block_reasons.clear()
