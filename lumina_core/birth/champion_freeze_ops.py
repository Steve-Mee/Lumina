"""OR5 operator surface: champion freeze decision card + accept/wipe ops helpers.

Pure decision card from progress/checkpoint (no train). Mutating paths live in
``scripts/validation/champion_freeze_ops.py`` via BirthService — this module
never starts Birth, arms REAL, or wipes state.
"""

from __future__ import annotations

from typing import Any

from lumina_core.birth.recovery_compress import recovery_from_progress
from lumina_core.birth.starship_swarm_gates import (
    build_champion_freeze_verification_report,
    is_champion_freeze_active,
)

CHECKLIST_DOC = "docs/birth-stage2-certified-reentry-checklist.md"
OPS_CLI = "python scripts/validation/champion_freeze_ops.py"


def build_champion_freeze_decision_card(
    *,
    progress: dict[str, Any] | None = None,
    checkpoint_metrics: dict[str, Any] | None = None,
    workspace: str | None = None,
) -> dict[str, Any]:
    """Build operator decision card for accept vs wipe (read-only)."""
    prog = dict(progress or {})
    metrics = dict(checkpoint_metrics or {})
    report = build_champion_freeze_verification_report(
        progress=prog,
        checkpoint_metrics=metrics,
    )
    recovery = recovery_from_progress(prog, recompute=True)
    freeze = bool(report.get("freeze_active"))
    accepted = bool(report.get("champion_accepted"))
    next_action = str(recovery.get("next_action") or "none")

    stages_passed = list(prog.get("stages_passed") or [])
    stage1_ok = "stage1_trend" in stages_passed or any(
        "stage1" in str(s).lower() for s in stages_passed
    )

    if freeze and not accepted:
        decision = "accept_champion_or_wipe"
        guidance = (
            "Sacred hard-stop: do not train, resume, or auto-recover. "
            "Choose accept_champion (keep champion, clear freeze) or wipe "
            "(clear training artifacts, re-enter Birth via checklist)."
        )
    elif accepted:
        decision = "freeze_resolved_accepted"
        guidance = (
            "Champion accepted — freeze cleared. Follow Stage 2 certified "
            f"re-entry checklist before claiming Stage 2 pass: {CHECKLIST_DOC}"
        )
    else:
        decision = "no_freeze"
        guidance = "No champion freeze active. No accept/wipe required for OR5."

    return {
        "schema": "champion_freeze_decision_card_v1",
        "workspace": workspace,
        "freeze_active": freeze,
        "champion_accepted": accepted,
        "rejected_no_lift": bool(report.get("rejected_no_lift")),
        "decision": decision,
        "guidance": guidance,
        "phase": str(prog.get("phase") or metrics.get("phase") or report.get("phase") or ""),
        "sub_phase": str(prog.get("sub_phase") or ""),
        "stage": str(prog.get("stage") or ""),
        "curriculum_index": prog.get("curriculum_index"),
        "stages_passed": stages_passed,
        "stage1_certified_receipt": stage1_ok,
        "cumulative_trades": int(prog.get("cumulative_trades") or prog.get("trades_done") or 0),
        "trade_budget_remaining": prog.get("trade_budget_remaining"),
        "stage_blocker_metric": prog.get("stage_blocker_metric"),
        "stage_blocker_value": prog.get("stage_blocker_value"),
        "pass_reason": prog.get("pass_reason"),
        "stage_winrate": prog.get("stage_winrate") or prog.get("live_winrate"),
        "edgescore": prog.get("edgescore"),
        "volume_gate_status": prog.get("volume_gate_status"),
        "best_policy_path": prog.get("best_policy_path"),
        "recovery": {
            "active": recovery.get("active"),
            "theater": recovery.get("theater"),
            "theater_reasons": list(recovery.get("theater_reasons") or []),
            "productive": recovery.get("productive"),
            "next_action": next_action,
            "flags": recovery.get("flags") or {},
        },
        "report": report,
        "commands": {
            "status": f"{OPS_CLI} --workspace . status",
            "accept": f"{OPS_CLI} --workspace . accept --confirm",
            "accept_no_start": f"{OPS_CLI} --workspace . accept --confirm --no-start",
            "wipe_keep_cache": (
                f"{OPS_CLI} --workspace . wipe --confirm --keep-tick-cache"
            ),
            "wipe_full": f"{OPS_CLI} --workspace . wipe --confirm",
            "telegram": "ACCEPT | ACCEPT_NO_START | WIPE | WIPE_FULL | STATUS",
            "gate": "python scripts/validation/champion_freeze_gate.py --workspace . --no-pytest",
            "checklist": CHECKLIST_DOC,
        },
        "forbidden": [
            "train_through_freeze",
            "auto_resume_under_freeze",
            "silent_champion_overwrite",
            "auto_REAL",
            "hollow_perfect_birth_declare",
        ],
        "ok": True,
    }


def freeze_active_from_workspace_payloads(
    *,
    progress: dict[str, Any] | None,
    checkpoint_metrics: dict[str, Any] | None,
) -> bool:
    """Convenience: freeze predicate only."""
    return is_champion_freeze_active(
        progress=progress or {},
        checkpoint_metrics=checkpoint_metrics or {},
    )


__all__ = [
    "CHECKLIST_DOC",
    "OPS_CLI",
    "build_champion_freeze_decision_card",
    "freeze_active_from_workspace_payloads",
]
