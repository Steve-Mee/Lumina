"""Honest Birth exit refusal when holdout B cannot host Awakening n_B≥500.

Stage gates may pass on a short tape. That is not a freeze and not Awakening.
Continue must reload the 365-day sport and retrain. Do not wipe.
"""
from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_holdout_capacity import thin_holdout_reason
from lumina_core.birth.progress import write_birth_progress
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.holdout_capacity")

CAPACITY_REFUSAL_STAGE = "holdout_capacity_refused"
CAPACITY_REFUSAL_PHASE = "holdout_capacity_refused"
CAPACITY_ATTENTION_CODE = "holdout_capacity_below_n_b_min"
# Same-tape resume can gain a weekend. A real sport change is much larger.
TAPE_GROWTH_DAY_SLACK = 7


def capacity_refusal_message(reason: str) -> str:
    """Operator copy. English. Stage pass is not Birth exit."""
    detail = str(reason or CAPACITY_ATTENTION_CODE).strip()
    return (
        "This tape cannot host Awakening. "
        f"{detail}. "
        "Stage passes were not frozen. "
        "Continue loads 365 days and retrains from stage 1. Do not wipe."
    )


def manifest_holdout_tick_count(manifest: dict[str, Any] | None) -> int | None:
    """Explicit cache count only. A missing key is unknown, not a thin tape."""
    raw = dict(manifest or {})
    if "holdout_tick_count" not in raw:
        return None
    try:
        return int(raw.get("holdout_tick_count") or 0)
    except (TypeError, ValueError):
        return None


def explicit_manifest_capacity_reason(
    manifest: dict[str, Any] | None,
    *,
    hold_bars: int = 120,
) -> str | None:
    ticks = manifest_holdout_tick_count(manifest)
    if ticks is None:
        return None
    return thin_holdout_reason(int(ticks), int(hold_bars))


def persist_holdout_capacity_refusal(
    workspace_root: Any,
    *,
    reason: str,
    cumulative_trades: int = 0,
    target_trades: int = 0,
    ppo_steps: int = 0,
    birth_start_time: float = 0.0,
) -> None:
    """Terminal progress. Not an active stage, so orphan reconcile must not clobber it."""
    text = capacity_refusal_message(reason)
    write_birth_progress(
        workspace_root,
        stage=CAPACITY_REFUSAL_STAGE,
        phase=CAPACITY_REFUSAL_PHASE,
        message=text,
        progress_pct=0.0,
        cumulative_trades=int(cumulative_trades),
        target_trades=int(target_trades),
        ppo_steps=int(ppo_steps),
        birth_start_time=float(birth_start_time),
        needs_attention=True,
        attention_reason_code=CAPACITY_ATTENTION_CODE,
        attention_summary=text,
        failure_reason=str(reason),
        user_initiated_stop=False,
        stage_pass_now=False,
        is_advancing=False,
        sub_phase="holdout_capacity_refused",
        sub_phase_label="Holdout cannot host Awakening",
        progress_truth={
            "kind": "holdout_capacity",
            "stage_index": 5,
            "stage_count": 5,
            "stage_pass_now": False,
            "blocker": CAPACITY_ATTENTION_CODE,
            "pct_is_not_complete": True,
        },
    )
    logger.error("birth.holdout_capacity.refused reason=%s", reason)


def void_receipts_for_grown_tape(host: Any) -> bool:
    """Drop stage receipts when the loaded tape is a longer exam than the one that passed.

    Keeping a 90-day receipt on a 365-day tape would skip the new exam.
    """
    manifest = getattr(host, "_data_manifest", None) or {}
    try:
        actual = int(manifest.get("actual_calendar_days") or manifest.get("days_loaded") or 0)
    except (TypeError, ValueError):
        actual = 0
    receipts = list(getattr(host, "_stage_pass_receipts", []) or [])
    if actual <= 0 or not receipts:
        return False
    exam_days = 0
    for rec in receipts:
        try:
            exam_days = max(exam_days, int(getattr(rec, "unique_calendar_days", 0) or 0))
        except (TypeError, ValueError):
            continue
    if exam_days <= 0 or actual <= exam_days + TAPE_GROWTH_DAY_SLACK:
        return False
    logger.warning(
        "birth.receipts.voided_tape_grew exam_days=%s actual_days=%s stages=%s",
        exam_days,
        actual,
        list(getattr(host, "_stages_passed", []) or []),
    )
    host._stages_passed = []
    host._stage_pass_receipts = []
    host._pending_stage_pass_receipt = None
    return True


def refuse_thin_holdout(host: Any, split: Any, *, target_trades: int) -> dict[str, Any] | None:
    """Return a foundation_incomplete payload when this split cannot host n_B≥500."""
    holdout = list(getattr(split, "holdout", []) or [])
    hold_bars = 120
    geo = getattr(host, "trade_geometry", None) or getattr(host, "_trade_geometry", None)
    if geo is not None:
        try:
            hold_bars = int(getattr(geo, "hold_bars", 120) or 120)
        except (TypeError, ValueError):
            hold_bars = 120
    reason = thin_holdout_reason(len(holdout), hold_bars)
    if not reason:
        return None
    persist_holdout_capacity_refusal(
        host.workspace_root,
        reason=reason,
        cumulative_trades=int(getattr(host, "cumulative_trades", 0) or 0),
        target_trades=int(target_trades),
        ppo_steps=int(getattr(host, "ppo_steps", 0) or 0),
        birth_start_time=float(getattr(host, "birth_start_time", 0) or 0),
    )
    return {
        "status": "foundation_incomplete",
        "failure_reason": reason,
        "total_trades": int(getattr(host, "cumulative_trades", 0) or 0),
        "ppo_steps": int(getattr(host, "ppo_steps", 0) or 0),
        "training_mode": str(getattr(host, "training_mode", "") or ""),
    }


__all__ = [
    "CAPACITY_ATTENTION_CODE",
    "CAPACITY_REFUSAL_PHASE",
    "CAPACITY_REFUSAL_STAGE",
    "TAPE_GROWTH_DAY_SLACK",
    "capacity_refusal_message",
    "explicit_manifest_capacity_reason",
    "manifest_holdout_tick_count",
    "persist_holdout_capacity_refusal",
    "refuse_thin_holdout",
    "void_receipts_for_grown_tape",
]
