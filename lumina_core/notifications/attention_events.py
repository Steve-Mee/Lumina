"""Attention-worthy event taxonomy for operator notifications (ADR-0024)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AttentionSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    INFO = "info"


class AttentionCategory(str, Enum):
    BIRTH = "birth"
    REAL = "real"
    EVOLUTION = "evolution"
    OPS = "ops"


@dataclass(frozen=True, slots=True)
class AttentionEvent:
    category: AttentionCategory
    severity: AttentionSeverity
    reason_code: str
    title: str
    summary: str
    recommended_actions: tuple[str, ...] = ()
    context: dict[str, Any] = field(default_factory=dict)
    retryable: bool = True
    dedupe_key: str = ""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.dedupe_key:
            object.__setattr__(self, "dedupe_key", f"{self.category.value}:{self.reason_code}")

    def telegram_body(self) -> str:
        lines = [
            self.summary,
        ]
        if self.context:
            ctx_parts: list[str] = []
            for key in (
                "curriculum_stage",
                "stage_trades",
                "winrate",
                "terminal_stall_reason",
                "failure_reason",
            ):
                if key in self.context and self.context[key] is not None:
                    ctx_parts.append(f"{key}: {self.context[key]}")
            if ctx_parts:
                lines.append("\n".join(ctx_parts))
        if self.recommended_actions:
            lines.append("Actions:")
            lines.extend(f"• {action}" for action in self.recommended_actions)
        return "\n".join(lines)


def birth_stage_stalled_event(
    *,
    curriculum_stage: str,
    stall_reason: str,
    blocker_detail: str,
    stage_trades: int = 0,
    winrate: float | None = None,
    retryable: bool = True,
    phase2_active: bool = False,
) -> AttentionEvent:
    actions: list[str] = []
    if stall_reason == "plateau_evolution_exhausted":
        if phase2_active:
            actions.append("Phase-2 auto-remediation is running — monitor progress in Lumina.")
        else:
            actions.append("Open Lumina → Review genesis settings (data window, reward).")
            actions.append("Then: Expand & retry or Retry stage (checkpoint preserved).")
            actions.append("Forensics: python scripts/birth_stage_forensics.py")
    else:
        actions.append("Open Lumina → Retry stage or Expand & retry.")
    return AttentionEvent(
        category=AttentionCategory.BIRTH,
        severity=AttentionSeverity.HIGH,
        reason_code=stall_reason if stall_reason else "stage_stalled",
        title="Birth stage stalled",
        summary=blocker_detail or f"Stage {curriculum_stage} stalled.",
        recommended_actions=tuple(actions),
        context={
            "curriculum_stage": curriculum_stage,
            "stage_trades": stage_trades,
            "winrate": f"{winrate:.1%}" if winrate is not None else None,
            "terminal_stall_reason": stall_reason,
        },
        retryable=retryable,
        dedupe_key=f"birth:stall:{curriculum_stage}:{stall_reason}",
    )


def birth_certificate_failed_event(
    *,
    failure_reasons: list[str],
    retryable: bool = True,
) -> AttentionEvent:
    detail = "; ".join(str(r) for r in failure_reasons[:5]) or "OOS certificate thresholds not met."
    return AttentionEvent(
        category=AttentionCategory.BIRTH,
        severity=AttentionSeverity.HIGH,
        reason_code="certificate_failed",
        title="Birth certificate failed",
        summary=detail,
        recommended_actions=(
            "Open Lumina → Continue learning or Reuse data & retry.",
            "Review OOS metrics before REAL mode.",
        ),
        context={"failure_reason": detail},
        retryable=retryable,
        dedupe_key="birth:certificate_failed",
    )


def birth_history_unavailable_event(*, detail: str = "") -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.BIRTH,
        severity=AttentionSeverity.MEDIUM,
        reason_code="history_unavailable",
        title="Birth history unavailable",
        summary=detail or "Historical data expansion exhausted or unavailable.",
        recommended_actions=(
            "Check data sources and config max_real_days.",
            "Retry when market data is available.",
        ),
        dedupe_key="birth:history_unavailable",
    )


def birth_interrupted_event(*, detail: str = "") -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.BIRTH,
        severity=AttentionSeverity.MEDIUM,
        reason_code="birth_interrupted",
        title="Birth training interrupted",
        summary=detail or "Birth phase stopped before completion.",
        recommended_actions=("Open Lumina → Resume from checkpoint.",),
        dedupe_key="birth:interrupted",
    )


def birth_error_event(*, detail: str) -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.BIRTH,
        severity=AttentionSeverity.HIGH,
        reason_code="birth_error",
        title="Birth training error",
        summary=detail,
        recommended_actions=("Check logs and retry from checkpoint.",),
        dedupe_key="birth:error",
    )


def curriculum_integrity_blocked_event(*, reasons: list[str]) -> AttentionEvent:
    detail = "; ".join(reasons) or "Curriculum integrity check failed."
    return AttentionEvent(
        category=AttentionCategory.BIRTH,
        severity=AttentionSeverity.CRITICAL,
        reason_code="curriculum_integrity_blocked",
        title="Birth curriculum integrity blocked",
        summary=detail,
        recommended_actions=(
            "Do not auto-resume — review stage pass receipts.",
            "Run: python scripts/birth_stage_forensics.py",
        ),
        retryable=False,
        dedupe_key="birth:integrity_blocked",
    )


def birth_champion_freeze_event(
    *,
    summary: str,
    stage_trades: int = 0,
    winrate: float | None = None,
    blocker_detail: str = "",
    reason_code: str = "swarm_no_tournament_lift",
) -> AttentionEvent:
    """Sacred OR5 fork — same questions in app popup and Telegram."""
    detail = summary or "Swarm no-lift — champion frozen."
    if blocker_detail:
        detail = f"{detail}\n{blocker_detail}"
    return AttentionEvent(
        category=AttentionCategory.BIRTH,
        severity=AttentionSeverity.CRITICAL,
        reason_code=str(reason_code or "swarm_no_tournament_lift"),
        title="Champion freeze — accept or wipe",
        summary=detail,
        recommended_actions=(
            "accept_champion",
            "wipe_and_retry",
            "Telegram: reply ACCEPT | ACCEPT_NO_START | WIPE | WIPE_FULL",
            "Checklist: docs/birth-stage2-certified-reentry-checklist.md",
        ),
        context={
            "stage_trades": stage_trades,
            "winrate": f"{winrate:.1%}" if winrate is not None else None,
            "terminal_stall_reason": "swarm_reject_hard_stop",
            "telegram_commands": "ACCEPT | ACCEPT_NO_START | WIPE | WIPE_FULL",
        },
        retryable=True,
        dedupe_key=f"birth:champion_freeze:{reason_code or 'swarm_no_tournament_lift'}",
    )


def real_safe_mode_event(*, detail: str = "") -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.REAL,
        severity=AttentionSeverity.CRITICAL,
        reason_code="real_safe_mode",
        title="REAL safe mode active",
        summary=detail or "Telemetry lost — REAL trading blocked.",
        recommended_actions=("Restore NinjaTrader / data feed connection.",),
        dedupe_key="real:safe_mode",
    )


def real_kill_switch_event(*, detail: str = "") -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.REAL,
        severity=AttentionSeverity.CRITICAL,
        reason_code="real_kill_switch",
        title="Kill switch activated",
        summary=detail or "Risk fortress kill switch is active.",
        recommended_actions=("Review Risk Citadel before resuming.",),
        dedupe_key="real:kill_switch",
    )


def real_daily_loss_event(*, detail: str = "") -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.REAL,
        severity=AttentionSeverity.CRITICAL,
        reason_code="real_daily_loss",
        title="Daily loss limit reached",
        summary=detail or "Daily loss cap triggered.",
        recommended_actions=("Review positions and risk settings.",),
        dedupe_key="real:daily_loss",
    )


def real_websocket_down_event(*, detail: str = "") -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.REAL,
        severity=AttentionSeverity.HIGH,
        reason_code="real_websocket_down",
        title="Market data websocket down",
        summary=detail or "WebSocket connection lost.",
        recommended_actions=("Check broker/data connection.",),
        dedupe_key="real:websocket_down",
    )


def evolution_approval_pending_event(*, dna_id: str = "", detail: str = "") -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.EVOLUTION,
        severity=AttentionSeverity.MEDIUM,
        reason_code="evolution_approval_pending",
        title="Evolution approval pending",
        summary=detail or f"DNA proposal {dna_id or ''} awaiting review.".strip(),
        recommended_actions=("Reply APPROVE or VETO via Telegram, or use Lumina deck.",),
        dedupe_key=f"evolution:approval:{dna_id or 'pending'}",
    )


def constitution_violation_event(*, detail: str = "") -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.REAL,
        severity=AttentionSeverity.CRITICAL,
        reason_code="constitution_violation",
        title="Constitution violation",
        summary=detail or "Trading constitution rule violated.",
        recommended_actions=("Review violation log — REAL promotion blocked.",),
        dedupe_key="real:constitution_violation",
    )


def backend_unreachable_event(*, detail: str = "") -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.OPS,
        severity=AttentionSeverity.HIGH,
        reason_code="backend_unreachable",
        title="Lumina backend unreachable",
        summary=detail or "FastAPI backend is not responding.",
        recommended_actions=("Start Lumina backend / check launcher.",),
        dedupe_key="ops:backend_unreachable",
    )


def setup_incomplete_event(*, detail: str = "") -> AttentionEvent:
    return AttentionEvent(
        category=AttentionCategory.OPS,
        severity=AttentionSeverity.MEDIUM,
        reason_code="setup_incomplete",
        title="Setup incomplete",
        summary=detail or "Onboarding wizard not finished.",
        recommended_actions=("Complete Lumina setup wizard.",),
        dedupe_key="ops:setup_incomplete",
    )


def evolution_proof_failed_attention_event(*, reasons: list[str]) -> AttentionEvent:
    detail = "; ".join(str(r) for r in reasons[:5]) or "Evolution Proof gate not passed."
    return AttentionEvent(
        category=AttentionCategory.BIRTH,
        severity=AttentionSeverity.HIGH,
        reason_code="evolution_proof_failed",
        title="Evolution Proof failed",
        summary=detail,
        recommended_actions=(
            "REAL remains blocked until Evolution Proof passes.",
            "Review OOS metrics and birth certificate in Lumina.",
        ),
        context={"failure_reason": detail},
        retryable=True,
        dedupe_key="birth:evolution_proof_failed",
    )


def real_trading_blocked_event(*, blockers: list[str], source: str = "command_deck") -> AttentionEvent:
    detail = "; ".join(blockers[:6]) or "Maturation ladder incomplete."
    return AttentionEvent(
        category=AttentionCategory.REAL,
        severity=AttentionSeverity.HIGH,
        reason_code="real_trading_blocked",
        title="REAL mode blocked",
        summary=detail,
        recommended_actions=(
            "Complete Apprenticeship (SIM stability) and Proving Ground (promotion gate).",
            "Check GET /api/maturity/progress for blockers.",
        ),
        context={"blockers": detail, "source": source},
        dedupe_key=f"real:blocked:{source}",
    )
