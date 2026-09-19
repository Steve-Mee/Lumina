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
        "retry_stage",
        "retry_stage_or_wipe",
        "expand_data_or_wipe_birth",
        "expand_data_or_wipe_genesis",
    }
)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def occupancy_from_loop(loop: Any) -> float | None:
    tot = int(getattr(loop, "stage_range_total_signals", 0) or 0)
    if tot <= 0:
        return None
    flat = int(getattr(loop, "stage_range_flat_bars", 0) or 0)
    return float(max(0, flat)) / float(tot)


def build_loop_terminal_freeze(loop: Any, stall_reason: str) -> dict[str, Any]:
    """Freeze payload from a live stage-loop host. Never invent ticks."""
    swarm = getattr(loop, "swarm_state", None)
    return build_terminal_freeze(
        reason=stall_reason,
        curriculum_stage=str(getattr(getattr(loop, "stage", None), "value", "") or ""),
        stages_passed=list(getattr(getattr(loop, "host", None), "_stages_passed", []) or []),
        evolution_step=int(getattr(getattr(loop, "plateau_state", None), "evolution_step", 0) or 0),
        stage_trades=int(getattr(loop, "stage_trades", 0) or 0),
        stage_wins=int(getattr(loop, "stage_wins", 0) or 0),
        swarm_rejected_no_lift=bool(
            getattr(loop, "swarm_rejected_no_lift", False)
            or getattr(swarm, "rejected_no_lift", False)
        ),
        swarm_champion_accepted=bool(
            getattr(loop, "swarm_champion_accepted", False)
            or getattr(swarm, "champion_accepted", False)
        ),
        best_edgescore_policy_path=str(getattr(loop, "best_edgescore_policy_path", "") or ""),
        best_policy_path=str(
            getattr(getattr(loop, "plateau_state", None), "best_policy_path", "") or ""
        ),
        expansion_step=int(getattr(loop, "expansion_step", 0) or 0),
        expansion_exhausted=bool(getattr(loop, "data_exhausted", False)),
        occupancy=occupancy_from_loop(loop),
        occupancy_exam_armed=bool(
            getattr(getattr(loop, "occupancy_exam_window", None), "armed", False)
        ),
        retries_this_stage=int(getattr(loop, "retries_this_stage", 0) or 0),
        max_stage_retries=int(getattr(getattr(loop, "cur_cfg", None), "max_stage_retries", 3) or 3),
    )


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
    expansion_step: int = 0,
    expansion_exhausted: bool = False,
    occupancy: float | None = None,
    occupancy_exam_armed: bool | None = None,
    retries_this_stage: int = 0,
    max_stage_retries: int = 3,
) -> dict[str, Any]:
    reject = bool(swarm_rejected_no_lift) and not bool(swarm_champion_accepted)
    action = str(next_action or "").strip()
    if not action:
        from lumina_core.birth.foundation_occupancy_envelope import (
            occupancy_fencepost_blocks_expand,
        )

        fencepost = occupancy_fencepost_blocks_expand(
            occupancy=occupancy,
            occupancy_exam_armed=occupancy_exam_armed,
        )
        ladder_open = (not bool(expansion_exhausted)) and int(expansion_step or 0) < 2
        if fencepost:
            retries = max(0, int(retries_this_stage or 0))
            cap = max(1, int(max_stage_retries or 3))
            action = "retry_stage_or_wipe" if retries >= cap else "retry_stage"
        elif reject and ladder_open:
            action = "expand_data_or_accept_or_wipe"
        elif reject:
            action = "accept_champion_or_wipe"
        else:
            action = "expand_data_or_wipe_birth"
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
        "expansion_step": max(0, int(expansion_step or 0)),
        "expansion_exhausted": bool(expansion_exhausted),
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
    next_action = str(freeze.get("next_action") or "expand_data_or_wipe_birth")
    reason = str(freeze.get("reason") or "stage_stalled")
    auto_retry = next_action == "retry_stage"
    return {
        "needs_attention": not auto_retry,
        "retryable": bool(auto_retry),
        "autonomous_recovery_pending": bool(auto_retry),
        "recommended_recovery_action": "retry_stage" if auto_retry else "",
        "terminal_stall_reason": reason,
        "terminal_freeze": dict(freeze),
        "curriculum_stage": str(freeze.get("curriculum_stage") or ""),
        "stages_passed": list(freeze.get("stages_passed") or []),
        "evolution_step": int(freeze.get("evolution_step") or 0),
        "attention_reason_code": reason,
        "attention_summary": (
            "Occupancy fencepost — autonomous retry_stage (sample reset)."
            if auto_retry
            else f"Terminal freeze: {reason} — Twin/operator next_action={next_action}"
        ),
        "attention_recommended_actions": (
            ["retry_stage", "wipe_and_retry"]
            if "retry_stage" in next_action
            else ["expand_data", "accept_champion", "wipe_and_retry"]
            if "expand" in next_action and "accept" in next_action
            else ["accept_champion", "wipe_and_retry"]
            if "accept" in next_action
            else ["expand_data", "wipe_and_retry", "human_review"]
        ),
    }


__all__ = [
    "TERMINAL_FREEZE_SCHEMA",
    "build_loop_terminal_freeze",
    "build_terminal_freeze",
    "extract_terminal_freeze",
    "freeze_attention_fields",
    "freeze_blocks_curriculum_grind",
    "freeze_is_active",
    "mark_freeze_resolved",
    "occupancy_from_loop",
    "restore_identity_from_freeze",
    "utcnow_iso",
]
