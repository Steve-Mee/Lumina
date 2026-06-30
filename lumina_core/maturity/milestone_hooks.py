"""Thin event hooks for maturation milestones (ADR-0027)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.maturation_progress import record_maturation_milestone

logger = get_logger("lumina.maturity.hooks")


def try_record_milestone(
    workspace_root: Path | str,
    milestone_id: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Best-effort milestone recording + Telegram maturation alert; never raises."""
    try:
        record_maturation_milestone(workspace_root, milestone_id, metadata=metadata)
    except Exception as exc:
        logger.debug("maturity.hook_failed id=%s err=%s", milestone_id, exc)
        return
    try:
        from lumina_core.notifications.operator_notifier import notify_maturation

        notify_maturation(milestone_id, workspace_root=workspace_root, metadata=metadata)
    except Exception as exc:
        logger.debug("maturity.telegram_failed id=%s err=%s", milestone_id, exc)


def hook_birth_started(
    workspace_root: Path | str,
    *,
    training_mode: str = "",
    trade_budget: int = 0,
    resumed: bool = False,
) -> None:
    try_record_milestone(
        workspace_root,
        "birth_started",
        metadata={
            "training_mode": training_mode,
            "trade_budget": trade_budget,
            "resumed": resumed,
        },
    )


def hook_birth_certificate_issued(
    workspace_root: Path | str,
    *,
    cumulative_trades: int = 0,
    stages_passed: list[str] | None = None,
) -> None:
    try_record_milestone(
        workspace_root,
        "birth_certificate_issued",
        metadata={
            "cumulative_trades": cumulative_trades,
            "stages_passed": list(stages_passed or []),
        },
    )
    try_record_milestone(workspace_root, "deck_unlocked")


def hook_evolution_proof_passed(
    workspace_root: Path | str,
    *,
    oos_winrate: float = 0.0,
    lift: float | None = None,
) -> None:
    try_record_milestone(
        workspace_root,
        "evolution_proof_passed",
        metadata={"oos_winrate": oos_winrate, "lift": lift},
    )


def hook_sim_real_guard_stable(
    workspace_root: Path | str,
    *,
    consecutive_green_days: int = 0,
    source: str = "sim_stability_checker",
) -> None:
    try_record_milestone(
        workspace_root,
        "sim_real_guard_stable",
        metadata={
            "consecutive_green_days": consecutive_green_days,
            "source": source,
        },
    )


def hook_shadow_validation_passed(
    workspace_root: Path | str,
    *,
    shadow_status: str = "",
    dna_hash: str = "",
) -> None:
    try_record_milestone(
        workspace_root,
        "shadow_validation_passed",
        metadata={"shadow_status": shadow_status, "dna_hash": dna_hash},
    )


def hook_promotion_gate_passed(
    workspace_root: Path | str,
    *,
    mode: str = "",
    dna_hash: str = "",
) -> None:
    try_record_milestone(
        workspace_root,
        "promotion_gate_passed",
        metadata={"mode": mode, "dna_hash": dna_hash},
    )


def hook_human_real_approval(workspace_root: Path | str, *, source: str = "command_deck") -> None:
    try_record_milestone(workspace_root, "human_real_approval", metadata={"source": source})


def hook_real_trading_live(workspace_root: Path | str, *, mode: str = "real") -> None:
    try_record_milestone(workspace_root, "real_trading_live", metadata={"mode": mode})
