"""Atomic terminal freeze SSOT for Birth (post-mortem 2026-08-10).

After plateau ladder / swarm no-lift exhaustion the organism freezes one honest
narrative: stage identity, stages_passed, evolution step, next_action.
Resume must restore this freeze — never rewrite hollow stage1/trades=0.

Twin (not silent auto-resume) owns expand / accept_champion; wipe is never auto.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

TERMINAL_FREEZE_SCHEMA = "terminal_freeze_v1"
_RESOLVED_ACTIONS = frozenset(
    {
        "expand_data",
        "expand_and_retry",
        "widen_horizon",
        "accept_champion",
        "wipe_and_retry",
        "wipe_genesis",
    }
)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_terminal_freeze(
    *,
    reason: str,
    curriculum_stage: str,
    stages_passed: list[str],
    evolution_step: int = 0,
    stage_trades: int = 0,
    stage_wins: int = 0,
    swarm_rejected_no_lift: bool = False,
    swarm_champion_accepted: bool = False,
    next_action: str | None = None,
    best_edgescore_policy_path: str = "",
    best_policy_path: str = "",
) -> dict[str, Any]:
    reject = bool(swarm_rejected_no_lift) and not bool(swarm_champion_accepted)
    action = str(next_action or "").strip()
    if not action:
        action = "accept_champion_or_wipe" if reject else "expand_data_or_wipe_genesis"
    return {
        "schema": TERMINAL_FREEZE_SCHEMA,
        "reason": str(reason or "stage_stalled"),
        "curriculum_stage": str(curriculum_stage or ""),
        "stages_passed": list(stages_passed or []),
        "evolution_step": max(0, int(evolution_step or 0)),
        "stage_trades": max(0, int(stage_trades or 0)),
        "stage_wins": max(0, int(stage_wins or 0)),
        "swarm_rejected_no_lift": bool(swarm_rejected_no_lift),
        "swarm_champion_accepted": bool(swarm_champion_accepted),
        "next_action": action,
        "best_edgescore_policy_path": str(best_edgescore_policy_path or ""),
        "best_policy_path": str(best_policy_path or ""),
        "frozen_at": utcnow_iso(),
        "resolved": False,
        "resolved_action": "",
        "resolved_by": "",
    }


def extract_terminal_freeze(
    *sources: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Find the newest terminal_freeze dict from progress / checkpoint / metrics."""
    found: dict[str, Any] | None = None
    for src in sources:
        if not isinstance(src, Mapping):
            continue
        raw = src.get("terminal_freeze")
        if isinstance(raw, dict) and raw.get("schema") == TERMINAL_FREEZE_SCHEMA:
            found = dict(raw)
            continue
        metrics = src.get("stage_metrics")
        if isinstance(metrics, Mapping):
            raw_m = metrics.get("terminal_freeze")
            if isinstance(raw_m, dict) and raw_m.get("schema") == TERMINAL_FREEZE_SCHEMA:
                found = dict(raw_m)
    return found


def freeze_is_active(freeze: Mapping[str, Any] | None) -> bool:
    if not isinstance(freeze, Mapping):
        return False
    if str(freeze.get("schema") or "") != TERMINAL_FREEZE_SCHEMA:
        return False
    if bool(freeze.get("resolved")):
        return False
    reason = str(freeze.get("reason") or "").strip().lower()
    return bool(reason)


def mark_freeze_resolved(
    freeze: Mapping[str, Any],
    *,
    action: str,
    resolved_by: str = "twin",
) -> dict[str, Any]:
    out = dict(freeze)
    out["resolved"] = True
    out["resolved_action"] = str(action or "")
    out["resolved_by"] = str(resolved_by or "twin")
    out["resolved_at"] = utcnow_iso()
    return out


def freeze_blocks_curriculum_grind(freeze: Mapping[str, Any] | None) -> bool:
    """Active unresolved freeze must not re-enter stage training grind."""
    return freeze_is_active(freeze)


def restore_identity_from_freeze(
    *,
    stages_passed: list[str],
    curriculum_stage: str,
    freeze: Mapping[str, Any] | None,
) -> tuple[list[str], str]:
    """Prefer freeze identity when live lists were hollowed (post-restart rewrite)."""
    if not freeze_is_active(freeze):
        return list(stages_passed or []), str(curriculum_stage or "")
    frozen_stages = [str(s) for s in (freeze.get("stages_passed") or []) if str(s).strip()]
    frozen_stage = str(freeze.get("curriculum_stage") or "").strip()
    out_stages = list(stages_passed or [])
    out_stage = str(curriculum_stage or "").strip()
    if frozen_stages and (not out_stages or len(frozen_stages) > len(out_stages)):
        out_stages = frozen_stages
    if frozen_stage and (
        not out_stage
        or (out_stage == "stage1_trend" and frozen_stage != "stage1_trend")
    ):
        out_stage = frozen_stage
    return out_stages, out_stage


def freeze_attention_fields(freeze: Mapping[str, Any]) -> dict[str, Any]:
    """Progress fields that keep freeze honest across resume."""
    if not freeze_is_active(freeze):
        return {}
    next_action = str(freeze.get("next_action") or "expand_data_or_wipe_genesis")
    reason = str(freeze.get("reason") or "stage_stalled")
    return {
        "needs_attention": True,
        "retryable": False,
        "terminal_stall_reason": reason,
        "terminal_freeze": dict(freeze),
        "curriculum_stage": str(freeze.get("curriculum_stage") or ""),
        "stages_passed": list(freeze.get("stages_passed") or []),
        "evolution_step": int(freeze.get("evolution_step") or 0),
        "attention_reason_code": reason,
        "attention_summary": (
            f"Terminal freeze: {reason} — Twin/operator next_action={next_action}"
        ),
        "attention_recommended_actions": (
            ["accept_champion", "wipe_and_retry"]
            if "accept" in next_action
            else ["expand_data", "wipe_and_retry", "human_review"]
        ),
    }


__all__ = [
    "TERMINAL_FREEZE_SCHEMA",
    "build_terminal_freeze",
    "extract_terminal_freeze",
    "freeze_attention_fields",
    "freeze_blocks_curriculum_grind",
    "freeze_is_active",
    "mark_freeze_resolved",
    "restore_identity_from_freeze",
    "utcnow_iso",
]
