"""H6: Compress recovery theater into one operator-facing ladder.

Birth recovery historically fans out across adaptation tiers, stall remediation,
plateau evolution, phoenix loops, swarm brakes, and terminal stalls — each
emitting parallel progress fields. Operators see activity (theater) without a
single answer to: *what is active, is it productive, what is next?*

This module is pure and fail-closed: it never starts recovery, only compresses
state into ``recovery_compress_v1`` for progress/status surfaces.
"""

from __future__ import annotations

from typing import Any, Literal

RecoverySurface = Literal[
    "idle",
    "adaptation",
    "stall_remediation",
    "plateau",
    "phoenix",
    "swarm_block",
    "certificate",
    "needs_attention",
    "terminal_stall",
]

# Highest priority first — one active surface only
_PRIORITY: tuple[RecoverySurface, ...] = (
    "terminal_stall",
    "needs_attention",
    "certificate",
    "swarm_block",
    "phoenix",
    "plateau",
    "stall_remediation",
    "adaptation",
    "idle",
)

_PHASE_CERTIFICATE = frozenset({"certificate_failed", "certificate_remediation"})
_PHASE_PHOENIX = frozenset({"phoenix_cycle", "phoenix_resume", "phoenix_novelty"})
_PHASE_STALL = frozenset({"stage_stalled", "terminal_stall"})
# Track A / T11: champion hard-stop is one sacred surface (not parallel theater)
_PHASE_SWARM_HARD_STOP = frozenset({"swarm_reject_hard_stop", "swarm_no_lift_hard_stop"})


def compress_recovery(
    *,
    phase: str | None = None,
    wall_behavior: str | None = None,
    adaptation_tier: int = 0,
    max_adaptation_tiers: int = 3,
    retries_this_stage: int = 0,
    max_stage_retries: int = 3,
    escalation_level: int = 0,
    plateau_active: bool = False,
    plateau_full_recovery_cycles: int = 0,
    plateau_evolution_step: int = 0,
    plateau_noop_count: int = 0,
    remediation_active: bool = False,
    remediation_step: int = 0,
    remediation_cycle: int = 0,
    remediation_max_steps: int = 4,
    remediation_max_cycles: int = 2,
    remediation_exhausted: bool = False,
    phoenix_enabled: bool = False,
    phoenix_cycles: int = 0,
    autonomous_recovery_count: int = 0,
    swarm_active: bool = False,
    swarm_rejected_no_lift: bool = False,
    needs_attention: bool = False,
    terminal_stall_reason: str | None = None,
    trade_budget_remaining: int | None = None,
    strong_recovery_mode: bool = False,
    provisional_graduation: bool = False,
    stage_blocker_metric: str | None = None,
    volume_gate_status: str | None = None,
    autonomous_recovery_successes: int = 0,
) -> dict[str, Any]:
    """Return a single compressed recovery status (schema recovery_compress_v1)."""
    ph = str(phase or "").strip().lower()
    layers: list[str] = []

    terminal = bool(terminal_stall_reason) or ph in _PHASE_STALL and remediation_exhausted
    if terminal or (ph in _PHASE_STALL and trade_budget_remaining == 0):
        layers.append("terminal_stall")
        terminal = True
    # Hard-stop phase implies operator attention (champion sacred).
    # C2 / ADR-0024: honest terminal stall must never be silent — force needs_attention
    # when terminalized (e.g. plateau_evolution_exhausted) so unattended Birth pages.
    attention = bool(needs_attention) or ph in _PHASE_SWARM_HARD_STOP or terminal
    if attention:
        layers.append("needs_attention")
    if ph in _PHASE_CERTIFICATE:
        layers.append("certificate")
    if (
        swarm_rejected_no_lift
        or ph in _PHASE_SWARM_HARD_STOP
        or (swarm_active and plateau_active and plateau_full_recovery_cycles > 0)
    ):
        layers.append("swarm_block")
    # Suppress phoenix/plateau ladder theater while champion freeze is active
    champion_freeze = bool(swarm_rejected_no_lift) or ph in _PHASE_SWARM_HARD_STOP
    if not champion_freeze:
        if ph in _PHASE_PHOENIX or (strong_recovery_mode and phoenix_enabled and not plateau_active):
            layers.append("phoenix")
        if plateau_active:
            layers.append("plateau")
        if remediation_active and not remediation_exhausted:
            layers.append("stall_remediation")
        # Adaptation theater only when adaptive wall is on and tier/retries moved
        adaptive = str(wall_behavior or "").strip().lower() == "adaptive"
        if adaptive and (adaptation_tier > 0 or retries_this_stage > 0 or escalation_level > 0):
            layers.append("adaptation")
    else:
        # Still report frozen layers as context only if already active (not as active pick below swarm)
        if plateau_active:
            layers.append("plateau")

    # Priority pick
    active: RecoverySurface = "idle"
    for surface in _PRIORITY:
        if surface == "idle":
            continue
        if surface in layers:
            active = surface
            break
    if not layers and ph in _PHASE_STALL:
        active = "terminal_stall"
        layers.append("terminal_stall")

    theater, theater_reasons = _theater_signals(
        active=active,
        plateau_full_recovery_cycles=plateau_full_recovery_cycles,
        plateau_noop_count=plateau_noop_count,
        swarm_rejected_no_lift=swarm_rejected_no_lift,
        remediation_exhausted=remediation_exhausted,
        remediation_active=remediation_active,
        adaptation_tier=adaptation_tier,
        max_adaptation_tiers=max_adaptation_tiers,
        phase=ph,
        stage_blocker_metric=stage_blocker_metric,
        volume_gate_status=volume_gate_status,
        plateau_evolution_step=plateau_evolution_step,
        autonomous_recovery_successes=autonomous_recovery_successes,
    )
    productive = _is_productive(
        active=active,
        theater=theater,
        remediation_exhausted=remediation_exhausted,
        needs_attention=attention,
        trade_budget_remaining=trade_budget_remaining,
        adaptation_tier=adaptation_tier,
        max_adaptation_tiers=max_adaptation_tiers,
        retries_this_stage=retries_this_stage,
        max_stage_retries=max_stage_retries,
        stage_blocker_metric=stage_blocker_metric,
        volume_gate_status=volume_gate_status,
    )
    # C2: terminal / plateau_evolution_exhausted must page (never silent stall hours)
    stall_reason = str(terminal_stall_reason or "").strip()
    if not productive and (
        terminal
        or stall_reason == "plateau_evolution_exhausted"
        or active == "terminal_stall"
    ):
        attention = True
        if "needs_attention" not in layers:
            layers.append("needs_attention")

    next_action = _next_action(
        active=active,
        theater=theater,
        productive=productive,
        needs_attention=attention,
        swarm_rejected_no_lift=bool(swarm_rejected_no_lift) or ph in _PHASE_SWARM_HARD_STOP,
        remediation_exhausted=remediation_exhausted,
        provisional_graduation=provisional_graduation,
        trade_budget_remaining=trade_budget_remaining,
        champion_freeze=champion_freeze,
    )

    return {
        "schema": "recovery_compress_v1",
        "active": active,
        "layers": layers,  # all concurrent layers (compressed view of theater fan-out)
        "productive": productive,
        "theater": theater,
        "theater_reasons": theater_reasons,
        "next_action": next_action,
        "escalation": {
            "level": int(escalation_level),
            "adaptation_tier": int(adaptation_tier),
            "max_adaptation_tiers": int(max_adaptation_tiers),
            "retries_this_stage": int(retries_this_stage),
            "max_stage_retries": int(max_stage_retries),
            "plateau_evolution_step": int(plateau_evolution_step),
            "plateau_full_recovery_cycles": int(plateau_full_recovery_cycles),
            "remediation_step": int(remediation_step),
            "remediation_cycle": int(remediation_cycle),
            "phoenix_cycles": int(phoenix_cycles),
            "autonomous_recovery_count": int(autonomous_recovery_count),
        },
        "flags": {
            "plateau_active": bool(plateau_active),
            "remediation_active": bool(remediation_active),
            "remediation_exhausted": bool(remediation_exhausted),
            "swarm_active": bool(swarm_active),
            "swarm_rejected_no_lift": bool(swarm_rejected_no_lift) or ph in _PHASE_SWARM_HARD_STOP,
            "needs_attention": attention,
            "champion_freeze": champion_freeze,
            "strong_recovery_mode": bool(strong_recovery_mode),
            "provisional_graduation": bool(provisional_graduation),
            "terminal_stall_reason": str(terminal_stall_reason or "") or None,
            "trade_budget_remaining": trade_budget_remaining,
            "phase": ph or None,
        },
        "policy": {
            "single_active_surface": True,
            "parallel_layers_reported_not_executed": True,
            "theater_means_spin_without_lift": True,
            "champion_freeze_suppresses_ladder_theater": True,
        },
    }


def _theater_signals(
    *,
    active: str,
    plateau_full_recovery_cycles: int,
    plateau_noop_count: int,
    swarm_rejected_no_lift: bool,
    remediation_exhausted: bool,
    remediation_active: bool,
    adaptation_tier: int,
    max_adaptation_tiers: int,
    phase: str,
    stage_blocker_metric: str | None = None,
    volume_gate_status: str | None = None,
    plateau_evolution_step: int = 0,
    autonomous_recovery_successes: int = 0,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if swarm_rejected_no_lift:
        reasons.append("swarm_no_lift_brake")
    if plateau_full_recovery_cycles >= 2:
        reasons.append("plateau_multi_cycle_no_clear_exit")
    if plateau_noop_count >= 3:
        reasons.append("plateau_evolution_noop_thrash")
    if remediation_exhausted and (remediation_active or active in {"plateau", "stall_remediation", "phoenix"}):
        reasons.append("remediation_exhausted_still_recovering")
    if max_adaptation_tiers > 0 and adaptation_tier >= max_adaptation_tiers - 1 and phase in _PHASE_STALL:
        reasons.append("adaptation_tiers_exhausted")
    # Recovery attempt counters without pass-metric restore = theater (forensic 2026-08-07).
    blocker = str(stage_blocker_metric or "").strip()
    vol_passed = str(volume_gate_status or "").strip().upper() == "PASSED"
    if (
        blocker
        and vol_passed
        and (
            int(plateau_evolution_step) >= 2
            or int(autonomous_recovery_successes) >= 1
            or int(plateau_full_recovery_cycles) >= 1
        )
    ):
        reasons.append("pass_metric_not_restored")
    if active == "terminal_stall":
        # Terminal is not theater — it's honesty
        return False, reasons
    return (len(reasons) > 0), reasons


def _is_productive(
    *,
    active: str,
    theater: bool,
    remediation_exhausted: bool,
    needs_attention: bool,
    trade_budget_remaining: int | None,
    adaptation_tier: int,
    max_adaptation_tiers: int,
    retries_this_stage: int,
    max_stage_retries: int,
    stage_blocker_metric: str | None = None,
    volume_gate_status: str | None = None,
) -> bool:
    if active in {"idle"}:
        return False
    if active in {"terminal_stall", "needs_attention", "certificate"}:
        return False
    if theater:
        return False
    if remediation_exhausted and active in {"stall_remediation", "phoenix", "plateau"}:
        return False
    if needs_attention:
        return False
    if trade_budget_remaining is not None and trade_budget_remaining <= 0:
        return False
    # Productive means path can still heal pass metrics — not attempt-counter vanity.
    blocker = str(stage_blocker_metric or "").strip()
    vol_passed = str(volume_gate_status or "").strip().upper() == "PASSED"
    if blocker and vol_passed and active in {"plateau", "stall_remediation", "phoenix", "adaptation"}:
        # Early recovery (no theater yet) still productive; theater already returned False.
        pass
    if active == "adaptation":
        tier_room = adaptation_tier < max(0, max_adaptation_tiers - 1)
        retry_room = retries_this_stage < max(1, max_stage_retries)
        return tier_room or retry_room
    return active in {"adaptation", "stall_remediation", "plateau", "phoenix", "swarm_block"}


def _next_action(
    *,
    active: str,
    theater: bool,
    productive: bool,
    needs_attention: bool,
    swarm_rejected_no_lift: bool,
    remediation_exhausted: bool,
    provisional_graduation: bool,
    trade_budget_remaining: int | None,
    champion_freeze: bool = False,
) -> str:
    if active == "idle":
        return "none"
    if active == "certificate":
        return "continue_learning_or_wipe"
    if active == "terminal_stall" or (
        trade_budget_remaining is not None and trade_budget_remaining <= 0
    ):
        return "expand_data_or_wipe_genesis"
    # Champion freeze is sacred: accept/wipe only (Track A / T11)
    if champion_freeze or (
        (swarm_rejected_no_lift or active == "swarm_block") and needs_attention
    ):
        return "accept_champion_or_wipe"
    if needs_attention or active == "needs_attention":
        return "human_review_telegram"
    if swarm_rejected_no_lift or active == "swarm_block":
        return "run_swarm_tournament_before_phoenix"
    if remediation_exhausted or theater:
        return "stop_auto_recovery_expand_or_manual"
    if provisional_graduation:
        return "accept_provisional_or_expand_retry"
    if productive:
        return "let_engine_recover"
    return "review_blocker_then_retry"


def recovery_from_progress(
    progress: dict[str, Any] | None,
    *,
    recompute: bool = False,
) -> dict[str, Any]:
    """Build compressed recovery from an existing progress/scorecard dict."""
    p = progress if isinstance(progress, dict) else {}
    # Prefer already-compressed payload if present and valid (unless recompute)
    existing = p.get("recovery")
    if (
        not recompute
        and isinstance(existing, dict)
        and existing.get("schema") == "recovery_compress_v1"
    ):
        return existing

    rem_step = int(p.get("stall_remediation_step", 0) or 0)
    rem_cycle = int(p.get("stall_remediation_cycle", 0) or 0)
    rem_max_steps = int(p.get("stall_remediation_max_steps", 4) or 4)
    rem_max_cycles = int(p.get("stall_remediation_max_cycles", 2) or 2)
    rem_active = rem_step > 0 or rem_cycle > 0 or bool(p.get("stall_remediation_active"))
    rem_exhausted = bool(p.get("stall_remediation_exhausted")) or (
        rem_cycle >= rem_max_cycles and rem_step >= rem_max_steps and rem_max_cycles > 0
    )

    budget = p.get("trade_budget_remaining")
    if budget is None and p.get("trade_budget_cap") is not None:
        try:
            budget = max(0, int(p.get("trade_budget_cap") or 0) - int(p.get("cumulative_trades") or 0))
        except (TypeError, ValueError):
            budget = None
    else:
        try:
            budget = int(budget) if budget is not None else None
        except (TypeError, ValueError):
            budget = None

    return compress_recovery(
        phase=str(p.get("phase") or p.get("stage") or ""),
        wall_behavior=str(p.get("wall_behavior") or ""),
        adaptation_tier=int(p.get("adaptation_tier", 0) or 0),
        max_adaptation_tiers=int(p.get("max_adaptation_tiers", 3) or 3),
        retries_this_stage=int(p.get("retries_this_stage", 0) or 0),
        max_stage_retries=int(p.get("max_stage_retries", 3) or 3),
        escalation_level=int(p.get("escalation_level", 0) or 0),
        plateau_active=bool(p.get("plateau_active")),
        plateau_full_recovery_cycles=int(p.get("plateau_full_recovery_cycles", 0) or 0),
        plateau_evolution_step=int(p.get("plateau_evolution_step", 0) or 0),
        plateau_noop_count=int(p.get("plateau_evolution_noop_count", 0) or 0),
        remediation_active=rem_active,
        remediation_step=rem_step,
        remediation_cycle=rem_cycle,
        remediation_max_steps=rem_max_steps,
        remediation_max_cycles=rem_max_cycles,
        remediation_exhausted=rem_exhausted,
        phoenix_enabled=bool(p.get("phoenix_loop_enabled", True)),
        phoenix_cycles=int(p.get("phoenix_cycles", p.get("phoenix_cycle_count", 0)) or 0),
        autonomous_recovery_count=int(p.get("autonomous_recovery_count", 0) or 0),
        swarm_active=bool(p.get("swarm_active") or p.get("policy_swarm_active")),
        swarm_rejected_no_lift=bool(
            p.get("swarm_rejected_no_lift") or p.get("policy_swarm_rejected_no_lift")
        ),
        needs_attention=bool(p.get("needs_attention")),
        terminal_stall_reason=str(p.get("terminal_stall_reason") or "") or None,
        trade_budget_remaining=budget,
        strong_recovery_mode=bool(p.get("strong_recovery_mode")),
        provisional_graduation=bool(p.get("provisional_graduation") or p.get("provisional_pass")),
        stage_blocker_metric=str(p.get("stage_blocker_metric") or "") or None,
        volume_gate_status=str(p.get("volume_gate_status") or "") or None,
        autonomous_recovery_successes=int(
            p.get("autonomous_recovery_successes", p.get("autonomous_recovery_count", 0)) or 0
        ),
    )


def build_recovery_theater_ops_report(
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """T11: Ops report — single recovery surface + residual theater inventory."""
    compressed = recovery_from_progress(progress, recompute=True)
    active = str(compressed.get("active") or "idle")
    layers = list(compressed.get("layers") or [])
    residual_surfaces = [s for s in layers if s != active]
    return {
        "schema": "recovery_theater_ops_v1",
        "ok": True,
        "active": active,
        "layers": layers,
        "residual_parallel_layers": residual_surfaces,
        "next_action": compressed.get("next_action"),
        "theater": bool(compressed.get("theater")),
        "theater_reasons": list(compressed.get("theater_reasons") or []),
        "productive": bool(compressed.get("productive")),
        "flags": compressed.get("flags") or {},
        "policy": {
            **dict(compressed.get("policy") or {}),
            "ssot": "recovery_compress_v1",
            "progress_key": "recovery",
            "api": "GET birth status embeds recovery_from_progress",
        },
        "delete_targets": [
            "dual closed-loop via stage_loop (use handler_hooks only)",
            "vanity tournament edgescore naming (prefer tournament_*)",
            "parallel plateau ladder while champion freeze active",
        ],
        "commands": {
            "status": "python scripts/validation/recovery_theater_gate.py",
            "champion_freeze": "python scripts/validation/champion_freeze_gate.py",
            "champion_freeze_ops": (
                "python scripts/validation/champion_freeze_ops.py --workspace . status"
            ),
            "checklist": "docs/birth-stage2-certified-reentry-checklist.md",
        },
        "recovery": compressed,
    }


__all__ = [
    "RecoverySurface",
    "build_recovery_theater_ops_report",
    "compress_recovery",
    "recovery_from_progress",
]
