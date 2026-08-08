"""Pure / side-effect-light swarm helpers for stage-loop iteration (no hang-sensitive control flow)."""
from __future__ import annotations

from typing import Any


def swarm_hard_stop_result(
    *,
    total_trades: int,
    ppo_steps: int,
    training_mode: str,
    reason_code: str = "swarm_no_tournament_lift",
) -> dict[str, Any]:
    """Terminal payload when post-reject champion freeze blocks further training."""
    return {
        "status": "stage_stalled",
        "failure_reason": "swarm_reject_hard_stop",
        "swarm_fail_reason_code": str(reason_code or "swarm_no_tournament_lift"),
        "total_trades": int(total_trades),
        "ppo_steps": int(ppo_steps),
        "training_mode": training_mode,
    }


def swarm_hard_stop_progress_message() -> str:
    return (
        "Swarm tournament rejected (post re-tournament) — champion frozen. "
        "No further training until accept champion or wipe."
    )


def swarm_frozen_window_missing_message(*, empty: bool = False) -> str:
    if empty:
        return (
            "Swarm tournament aborted — empty frozen window. "
            "Champion frozen; accept champion or wipe."
        )
    return (
        "Swarm tournament aborted — frozen tick windows missing. "
        "Champion frozen; accept champion or wipe."
    )


def compute_rollout_chunk_target(
    *,
    stage_trades: int,
    required: int,
    rollout_chunk_trades: int,
) -> int:
    """Pure chunk size for next rollout (bounded remaining trades)."""
    chunk = max(1, int(rollout_chunk_trades))
    if int(stage_trades) >= int(required):
        return chunk
    remaining = max(1, int(required) - int(stage_trades))
    return min(remaining, chunk)


def heartbeat_progress_message(
    *,
    stage_value: str,
    stage_trades: int,
    required: int,
    patterns_mined: int,
) -> str:
    return (
        f"Curriculum {stage_value}: heartbeat · {int(stage_trades):,} / "
        f"{int(required):,} trades · patronen {int(patterns_mined):,}"
    )
