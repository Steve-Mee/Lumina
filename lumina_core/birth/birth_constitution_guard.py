"""Birth-specific constitution checks during SIM (ADR-0013).

Soft blocks (entry rejected by the guard) are NOT graduation violations.
Hard violations are breaches that would count against stage pass / certificate.
Raptor v6: blocked ≠ violated.

P1 (flight forensics): hard-clip stop/target into the 1% risk band *before*
the soft path so the policy learns the action that actually executes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from lumina_bible.bible_engine import BibleEngine, DEFAULT_BIBLE

from lumina_core.agent_orchestration.schemas import ConstitutionViolation
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.constitution_guard")

_BIBLE: dict[str, Any] = cast(dict[str, Any], DEFAULT_BIBLE)

# Capital-preservation band for birth SIM entries (fraction of equity).
BIRTH_MAX_RISK_STOP_PCT = 0.01
# Floor must match birth_trade_geometry micro-scale (1-min MES ~0.05–0.12%).
# Legacy 0.001 (0.1%) silently re-widened calibrated oracle/SIM stops and
# poisoned expectancy transfer (forensics 2026-08 foundation audit).
BIRTH_MIN_STOP_PCT = 0.0004
BIRTH_MAX_STOP_PCT = 0.02
BIRTH_MAX_TARGET_PCT = 0.05

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

# Soft event-bus publish throttle (first N + every N thereafter).
_SOFT_PUBLISH_FIRST = 3
_SOFT_PUBLISH_EVERY = 500


def clip_birth_risk_params(
    stop_pct: float,
    target_pct: float,
    *,
    max_risk_stop_pct: float = BIRTH_MAX_RISK_STOP_PCT,
) -> tuple[float, float, bool]:
    """Hard-clip stop into the 1% risk band; scale target to preserve RR.

    Returns ``(stop_pct, target_pct, was_clipped)``. Invalid (≤0) stop is left
    unchanged so ``check_entry`` can still soft-block ``invalid_stop``.
    """
    raw_stop = float(stop_pct)
    raw_target = float(target_pct)
    if raw_stop <= 0.0:
        return raw_stop, raw_target, False
    cap = max(BIRTH_MIN_STOP_PCT, min(BIRTH_MAX_STOP_PCT, float(max_risk_stop_pct)))
    clipped_stop = max(BIRTH_MIN_STOP_PCT, min(cap, raw_stop))
    was_clipped = abs(clipped_stop - raw_stop) > 1e-12
    if was_clipped and raw_stop > 0.0:
        rr = max(0.25, min(10.0, raw_target / raw_stop)) if raw_target > 0.0 else 2.0
        clipped_target = max(BIRTH_MIN_STOP_PCT, min(BIRTH_MAX_TARGET_PCT, clipped_stop * rr))
    else:
        clipped_target = max(BIRTH_MIN_STOP_PCT, min(BIRTH_MAX_TARGET_PCT, raw_target if raw_target > 0.0 else clipped_stop * 2.0))
    return clipped_stop, clipped_target, was_clipped


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
    - ``soft_block_reason_counts``: histogram for ops forensics (risk vs news vs invalid).
    """

    violations: int = 0
    soft_blocks: int = 0
    violation_reasons: list[str] = field(default_factory=list)
    soft_block_reasons: list[str] = field(default_factory=list)
    soft_block_reason_counts: dict[str, int] = field(default_factory=dict)
    clips_applied: int = 0
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
        auto_clip: bool = True,
        qty: int = 1,
    ) -> tuple[bool, str]:
        """Return (allowed, reason).

        Default ``auto_clip=True``: hard-clip stop into the 1% risk band before
        evaluation so birth SIM never soft-vetoes legal-after-clip actions.
        Live forensics showed clips=0 + 100% risk_exceeds when clip was optional.
        Callers that need the clipped stop/target for execution must use
        :meth:`prepare_entry` (preferred gym path).
        """
        if side == 0:
            return True, ""

        if float(tick.get("news_window_active", 0.0) or 0.0) > 0.5:
            self._record_soft("news_window_entry_blocked")
            return False, "news_window"

        effective_stop = float(stop_pct)
        if auto_clip and effective_stop > 0.0:
            clipped, _, was_clipped = clip_birth_risk_params(
                effective_stop, max(effective_stop * 2.0, BIRTH_MIN_STOP_PCT)
            )
            if was_clipped:
                self.clips_applied += 1
            effective_stop = clipped

        if effective_stop <= 0.0 or effective_stop > BIRTH_MAX_STOP_PCT + 1e-12:
            self._record_soft("invalid_stop_pct")
            return False, "invalid_stop"

        # Fraction-of-equity risk only. Non-positive equity must not invert the
        # inequality (negative equity made every entry soft-block forever and
        # froze Stage-2 under-activity with FORCE_OPEN count↑ / FORCE_HOLD=0).
        equity_for_risk = float(equity)
        if equity_for_risk <= 0.0:
            equity_for_risk = 1.0

        # Dollar risk = qty × stop × price × pv vs 1% of equity.
        # Size must not silently walk around the 1% band.
        qty_n = max(1, int(qty))
        px = 0.0
        if isinstance(tick, dict):
            px = float(tick.get("close") or tick.get("last") or 0.0)
        max_risk = equity_for_risk * BIRTH_MAX_RISK_STOP_PCT
        if px > 0.0:
            risk_usd = abs(float(effective_stop)) * abs(px) * float(qty_n) * 5.0
        else:
            # Empty tick: fallback stop_pct × qty vs 1% (no invented price).
            if float(effective_stop) * float(qty_n) > BIRTH_MAX_RISK_STOP_PCT + 1e-12:
                self._record_soft("risk_exceeds_1pct")
                return False, "risk_cap"
            return True, ""
        if risk_usd > max_risk + 1e-9:
            self._record_soft("risk_exceeds_1pct")
            return False, "risk_cap"

        return True, ""

    def prepare_entry(
        self,
        *,
        tick: dict[str, Any],
        side: int,
        stop_pct: float,
        target_pct: float,
        equity: float,
        qty: int = 1,
    ) -> tuple[bool, str, float, float]:
        """Clip risk params then check. Returns (allowed, reason, stop, target).

        Preferred birth-SIM path: the policy learns the action that executes.
        """
        if side == 0:
            return True, "", float(stop_pct), float(target_pct)

        clipped_stop, clipped_target, was_clipped = clip_birth_risk_params(
            float(stop_pct), float(target_pct)
        )
        if was_clipped:
            self.clips_applied += 1
        allowed, reason = self.check_entry(
            tick=tick,
            side=side,
            stop_pct=clipped_stop,
            equity=equity,
            auto_clip=False,
            qty=qty,
        )
        return allowed, reason, clipped_stop, clipped_target

    def soft_block_histogram(self) -> dict[str, int]:
        """Normalized reason histogram for progress/scorecard."""
        return {str(k): int(v) for k, v in sorted(self.soft_block_reason_counts.items())}

    def record_hard_violation(self, reason: str) -> None:
        """Explicit hard breach (counts toward stage pass / certificate)."""
        self.violations += 1
        if len(self.violation_reasons) < 50:
            self.violation_reasons.append(reason)
        self._publish_violation(reason, severity="critical")

    def _record_soft(self, reason: str) -> None:
        """Entry blocked by guard — constitution held; do not fail graduation."""
        self.soft_blocks += 1
        key = str(reason or "unknown")
        self.soft_block_reason_counts[key] = int(self.soft_block_reason_counts.get(key, 0) or 0) + 1
        if len(self.soft_block_reasons) < 50:
            self.soft_block_reasons.append(reason)
        # Throttle event-bus spam: first few + every N (log still rate-limited downstream).
        if self.soft_blocks <= _SOFT_PUBLISH_FIRST or self.soft_blocks % _SOFT_PUBLISH_EVERY == 0:
            self._publish_violation(reason, severity="warning")
            if self.soft_blocks >= _SOFT_PUBLISH_EVERY and self.soft_blocks % _SOFT_PUBLISH_EVERY == 0:
                logger.info(
                    "birth.constitution.soft_block_rate count=%s last_reason=%s hist=%s clips=%s",
                    self.soft_blocks,
                    reason,
                    self.soft_block_histogram(),
                    self.clips_applied,
                )

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
        self.soft_block_reason_counts.clear()
        self.clips_applied = 0
