"""Plateau/recovery milestone event builders (M5 extract)."""
from __future__ import annotations


from lumina_core.notifications.milestone_event_types import (
    MilestoneCategory,
    MilestoneEvent,
)

def plateau_evolution_step_event(
    *,
    step: int,
    max_steps: int,
    action: str,
    detail: str,
    winrate: float,
) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id=f"plateau_evolution_step_{step}",
        category=MilestoneCategory.BIRTH,
        title=f"Plateau evolution {step}/{max_steps}",
        summary=f"{action}: {detail}. Winrate {winrate:.1%}.",
        context={
            "evolution_step": step,
            "max_steps": max_steps,
            "action": action,
            "winrate": f"{winrate:.1%}",
        },
        dedupe_key=f"plateau_evolution:{step}:{action}",
    )


def plateau_evolution_forced_advance_event(
    *,
    step: int,
    max_steps: int,
    action: str,
    winrate: float,
) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id=f"plateau_evolution_forced_advance_{step}",
        category=MilestoneCategory.BIRTH,
        title=f"Forced evolution advance {step}/{max_steps}",
        summary=f"Time-box triggered {action}. Winrate {winrate:.1%}.",
        context={"evolution_step": step, "action": action, "winrate": f"{winrate:.1%}"},
        dedupe_key=f"plateau_evolution:forced:{step}",
    )


def plateau_entered_event(
    *,
    stage_trades: int,
    winrate: float,
    pass_target: float | None = None,
    pass_label: str | None = None,
) -> MilestoneEvent:
    if pass_label:
        target_txt = str(pass_label)
        target_ctx = str(pass_label)
    elif pass_target is not None and 0.0 < float(pass_target) < 1.0:
        target_txt = f"target {float(pass_target):.0%}"
        target_ctx = f"{float(pass_target):.0%}"
    else:
        target_txt = "process-R / net RR / settlement (WR is not a pass gate)"
        target_ctx = "foundation_process"
    return MilestoneEvent(
        milestone_id="plateau_entered",
        category=MilestoneCategory.BIRTH,
        title="Learning plateau detected",
        summary=(
            f"Plateau entered at {stage_trades:,} trades, winrate {winrate:.1%} "
            f"({target_txt}). Evolution ladder starting."
        ),
        context={
            "trades": int(stage_trades),
            "winrate": f"{winrate:.1%}",
            "pass_target": target_ctx,
        },
    )


def hold_trap_detected_event(*, hold_ratio: float, winrate: float) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id="hold_trap_detected",
        category=MilestoneCategory.BIRTH,
        title="Hold trap detected",
        summary=f"Hold ratio {hold_ratio:.0%} with winrate {winrate:.1%}. Forcing explore boost.",
        context={"hold_ratio": f"{hold_ratio:.0%}", "winrate": f"{winrate:.1%}"},
    )


def stall_remediation_step_event(
    *,
    cycle: int,
    step: int,
    max_steps: int,
    action: str,
    detail: str,
    winrate: float,
) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id=f"stall_remediation_c{cycle}_s{step}",
        category=MilestoneCategory.BIRTH,
        title=f"Stall remediation {cycle}/{step}",
        summary=f"{action}: {detail}. Winrate {winrate:.1%}.",
        context={
            "cycle": cycle,
            "step": step,
            "max_steps": max_steps,
            "action": action,
            "winrate": f"{winrate:.1%}",
        },
        dedupe_key=f"stall_remediation:{cycle}:{step}:{action}",
    )


def stall_remediation_cycle_event(*, cycle: int, max_cycles: int) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id=f"stall_remediation_cycle_{cycle}",
        category=MilestoneCategory.BIRTH,
        title=f"Stall remediation cycle {cycle}/{max_cycles}",
        summary=f"Starting remediation cycle {cycle} of {max_cycles}.",
        context={"cycle": cycle, "max_cycles": max_cycles},
        dedupe_key=f"stall_remediation:cycle:{cycle}",
    )


def phoenix_reset_event(*, cycle: int, winrate: float, detail: str) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id=f"phoenix_reset_{cycle}",
        category=MilestoneCategory.BIRTH,
        title="Phoenix reset",
        summary=f"Phoenix reset (cycle {cycle}): {detail}. Winrate {winrate:.1%}.",
        context={"cycle": cycle, "winrate": f"{winrate:.1%}", "detail": detail},
        dedupe_key=f"phoenix_reset:{cycle}",
    )


def best_policy_updated_event(
    *,
    winrate: float,
    stage_trades: int,
    policy_path: str,
) -> MilestoneEvent:
    return MilestoneEvent(
        milestone_id="best_policy_updated",
        category=MilestoneCategory.BIRTH,
        title="Best policy snapshot saved",
        summary=f"New best winrate {winrate:.1%} at {stage_trades:,} trades.",
        context={
            "winrate": f"{winrate:.1%}",
            "trades": int(stage_trades),
            "policy_path": policy_path,
        },
        dedupe_key=f"best_policy:{stage_trades}:{round(winrate, 4)}",
    )


