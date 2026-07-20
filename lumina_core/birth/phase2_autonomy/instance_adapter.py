"""In-process instance adaptation proposals (no OS process spawn).

Phase 2 foundation defines "dynamic spawn without restart" as:
- refresh birth handler cfg
- request plateau / phoenix recovery paths already present in adaptation engine
- never broker / REAL / multi-process
"""

from __future__ import annotations

from typing import Any

from lumina_core.birth.phase2_autonomy.contracts import Phase2InstanceAdaptProposal

ALLOWED_ACTIONS = frozenset(
    {
        "refresh_handler_cfg",
        "spawn_plateau",
        "spawn_phoenix_reset",
        "noop",
    }
)

_FORBIDDEN_ACTION_TOKENS = frozenset(
    {
        "broker",
        "real",
        "order",
        "capital",
        "live_session",
        "process_fork",
        "os_spawn",
        "multiprocess",
    }
)


def propose_instance_adapt(
    *,
    adaptation_tier: int = 0,
    retries_this_stage: int = 0,
    plateau_active: bool = False,
    phoenix_eligible: bool = False,
    learning_health: str = "flat",
    stall_reason: str = "",
    cfg: Any | None = None,
) -> Phase2InstanceAdaptProposal:
    """Propose a single in-process adapt action based on recovery context.

    Pure function — no side effects.
    """
    health = str(learning_health or "flat").strip().lower()
    stall = str(stall_reason or "").strip().lower()
    tier = int(adaptation_tier or 0)
    retries = int(retries_this_stage or 0)

    # Prefer reusing existing spawn signals when stuck deep in recovery.
    if not plateau_active and (tier >= 2 or retries >= 2 or "plateau" in stall):
        return Phase2InstanceAdaptProposal(
            action="spawn_plateau",
            spawn_plateau=True,
            refresh_handler_cfg=True,
            rationale=f"tier={tier};retries={retries};health={health};enter_plateau",
            risk_touching=False,
        )

    if phoenix_eligible and (
        "phoenix" in stall
        or "exhausted" in stall
        or (tier >= 3 and health in {"declining", "flat"})
    ):
        return Phase2InstanceAdaptProposal(
            action="spawn_phoenix_reset",
            spawn_phoenix_reset=True,
            refresh_handler_cfg=True,
            rationale=f"tier={tier};health={health};phoenix_path",
            risk_touching=False,
        )

    if tier >= 1 or retries >= 1 or health in {"declining", "flat"}:
        return Phase2InstanceAdaptProposal(
            action="refresh_handler_cfg",
            refresh_handler_cfg=True,
            rationale=f"tier={tier};retries={retries};health={health};cfg_refresh",
            risk_touching=False,
        )

    return Phase2InstanceAdaptProposal(
        action="noop",
        rationale="no_instance_adapt_needed",
        risk_touching=False,
    )


def validate_instance_proposal(proposal: Phase2InstanceAdaptProposal) -> list[str]:
    """Return violation tokens if action is not allowlisted / touches risk surfaces."""
    violations: list[str] = []
    action = str(proposal.action or "").strip().lower()
    if not action:
        violations.append("empty_action")
        return violations
    if proposal.risk_touching:
        violations.append("risk_touching")
    for token in _FORBIDDEN_ACTION_TOKENS:
        if token in action:
            violations.append(f"forbidden_surface:{token}")
    if action not in ALLOWED_ACTIONS:
        violations.append(f"action_not_allowed:{action}")
    return violations


def materialize_instance_adapt_payload(
    proposal: Phase2InstanceAdaptProposal,
) -> dict[str, Any]:
    """Host-facing payload for stage loop / registry (no process spawn)."""
    return {
        "action": proposal.action,
        "refresh_handler_cfg": bool(proposal.refresh_handler_cfg),
        "spawn_plateau": bool(proposal.spawn_plateau),
        "spawn_phoenix_reset": bool(proposal.spawn_phoenix_reset),
        "rationale": proposal.rationale,
        "process_restart_required": False,
        "os_spawn": False,
    }


__all__ = [
    "ALLOWED_ACTIONS",
    "materialize_instance_adapt_payload",
    "propose_instance_adapt",
    "validate_instance_proposal",
]
