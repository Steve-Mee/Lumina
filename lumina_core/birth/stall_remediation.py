"""Phase-2 stall remediation ladder after plateau evolution exhaust (ADR-0024)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stall_remediation")

HUMAN_GATE_REASON = "stall_remediation_exhausted"


class StallRemediationAction(str, Enum):
    EXPAND_AND_RETRY = "expand_and_retry"
    BUFFER_CURATE_ORACLE = "buffer_curate_oracle"
    REGIME_DIVERSE_SLICE = "regime_diverse_slice"
    META_SWEEP = "meta_sweep"
    ORACLE_DISTILL = "oracle_distill"


REMEDIATION_STEP_ACTIONS: tuple[StallRemediationAction, ...] = (
    StallRemediationAction.EXPAND_AND_RETRY,
    StallRemediationAction.BUFFER_CURATE_ORACLE,
    StallRemediationAction.REGIME_DIVERSE_SLICE,
    StallRemediationAction.META_SWEEP,
    StallRemediationAction.ORACLE_DISTILL,
)

ACTION_LABELS: dict[StallRemediationAction, str] = {
    StallRemediationAction.EXPAND_AND_RETRY: "Expand data window and retry",
    StallRemediationAction.BUFFER_CURATE_ORACLE: "Curate buffer + aggressive oracle re-mine",
    StallRemediationAction.REGIME_DIVERSE_SLICE: "Regime-diverse train slice",
    StallRemediationAction.META_SWEEP: "Meta reward/explore sweep",
    StallRemediationAction.ORACLE_DISTILL: "Oracle distillation (top buffer trajectories)",
}


@dataclass(slots=True)
class StallRemediationState:
    active: bool = False
    remediation_cycle: int = 0
    remediation_step: int = 0
    remediation_rollouts_this_step: int = 0
    remediation_history: list[dict[str, Any]] = field(default_factory=list)
    winrate_at_step_start: float = 0.0
    meta_sweep_index: int = 0

    def to_metrics(self) -> dict[str, Any]:
        return {
            "stall_remediation_active": self.active,
            "stall_remediation_cycle": int(self.remediation_cycle),
            "stall_remediation_step": int(self.remediation_step),
            "stall_remediation_rollouts_this_step": int(self.remediation_rollouts_this_step),
            "stall_remediation_history": list(self.remediation_history),
            "stall_remediation_winrate_at_step_start": round(float(self.winrate_at_step_start), 6),
            "stall_remediation_meta_sweep_index": int(self.meta_sweep_index),
        }

    @classmethod
    def from_metrics(cls, metrics: dict[str, Any] | None) -> StallRemediationState:
        if not isinstance(metrics, dict):
            return cls()
        history = metrics.get("stall_remediation_history")
        return cls(
            active=bool(metrics.get("stall_remediation_active", False)),
            remediation_cycle=int(metrics.get("stall_remediation_cycle", 0) or 0),
            remediation_step=int(metrics.get("stall_remediation_step", 0) or 0),
            remediation_rollouts_this_step=int(
                metrics.get("stall_remediation_rollouts_this_step", 0) or 0
            ),
            remediation_history=[dict(x) for x in history if isinstance(x, dict)]
            if isinstance(history, list)
            else [],
            winrate_at_step_start=float(
                metrics.get("stall_remediation_winrate_at_step_start", 0) or 0
            ),
            meta_sweep_index=int(metrics.get("stall_remediation_meta_sweep_index", 0) or 0),
        )


def can_start_remediation(state: StallRemediationState, *, cfg: BirthCurriculumConfig) -> bool:
    max_cycles = max(1, int(cfg.stall_remediation_max_cycles))
    return state.remediation_cycle < max_cycles and not state.active


def should_run_remediation_instead_of_human_gate(
    state: StallRemediationState,
    *,
    cfg: BirthCurriculumConfig,
    plateau_exhausted: bool,
) -> bool:
    if not cfg.stall_remediation_enabled or not plateau_exhausted:
        return False
    return can_start_remediation(state, cfg=cfg) or state.active


def is_remediation_exhausted(state: StallRemediationState, *, cfg: BirthCurriculumConfig) -> bool:
    if not state.active:
        return False
    return state.remediation_step >= int(cfg.stall_remediation_max_steps)


def begin_remediation_cycle(
    state: StallRemediationState,
    *,
    stage_trades: int,
    stage_wins: int,
) -> None:
    state.active = True
    state.remediation_cycle += 1
    state.remediation_step = 0
    state.remediation_rollouts_this_step = 0
    state.meta_sweep_index = 0
    state.winrate_at_step_start = float(stage_wins) / float(max(1, stage_trades))
    logger.warning(
        "birth.stall_remediation.cycle_started cycle=%s winrate=%.2f%%",
        state.remediation_cycle,
        state.winrate_at_step_start * 100.0,
    )


def action_for_step(step: int) -> StallRemediationAction | None:
    if step <= 0 or step > len(REMEDIATION_STEP_ACTIONS):
        return None
    return REMEDIATION_STEP_ACTIONS[step - 1]


def begin_remediation_step(
    state: StallRemediationState,
    *,
    stage_trades: int,
    stage_wins: int,
) -> StallRemediationAction | None:
    state.remediation_step += 1
    state.remediation_rollouts_this_step = 0
    state.winrate_at_step_start = float(stage_wins) / float(max(1, stage_trades))
    action = action_for_step(state.remediation_step)
    logger.info(
        "birth.stall_remediation.step step=%s action=%s",
        state.remediation_step,
        action.value if action else "none",
    )
    return action


def should_advance_remediation_step(
    state: StallRemediationState,
    *,
    cfg: BirthCurriculumConfig,
    current_winrate: float,
) -> bool:
    if not state.active:
        return False
    if state.remediation_rollouts_this_step < int(cfg.stall_remediation_rollouts_per_step):
        return False
    if current_winrate > state.winrate_at_step_start + float(cfg.velocity_stall_epsilon):
        return False
    return True


def record_remediation_outcome(
    state: StallRemediationState,
    *,
    action: StallRemediationAction | None,
    stage_trades: int,
    stage_wins: int,
    detail: str = "",
) -> None:
    winrate = float(stage_wins) / float(max(1, stage_trades))
    state.remediation_history.append(
        {
            "timestamp": time.time(),
            "step": int(state.remediation_step),
            "action": action.value if action else "",
            "winrate": round(winrate, 6),
            "trades": int(stage_trades),
            "detail": str(detail or ""),
        }
    )


def increment_remediation_rollout(state: StallRemediationState) -> None:
    if state.active:
        state.remediation_rollouts_this_step += 1


def curate_buffer_bottom_half(buffer: Any) -> int:
    """Remove worst half of buffer trajectories by reward. Returns removed count."""
    trajectories = getattr(buffer, "trajectories", None)
    if not isinstance(trajectories, list) or len(trajectories) < 4:
        return 0
    priorities = getattr(buffer, "priorities", None)
    indexed = [(i, float(trajectories[i].get("reward", 0) or 0)) for i in range(len(trajectories))]
    indexed.sort(key=lambda item: item[1])
    remove_count = len(indexed) // 2
    remove_indices = {item[0] for item in indexed[:remove_count]}
    new_trajectories = [t for i, t in enumerate(trajectories) if i not in remove_indices]
    new_priorities: list[Any] = []
    if isinstance(priorities, list) and len(priorities) == len(trajectories):
        new_priorities = [p for i, p in enumerate(priorities) if i not in remove_indices]
    removed = len(trajectories) - len(new_trajectories)
    trajectories[:] = new_trajectories
    if new_priorities:
        priorities[:] = new_priorities
    return removed


def curate_buffer_top_quartile(buffer: Any, *, keep_pct: float = 0.25) -> int:
    """Keep only top fraction of buffer trajectories by reward. Returns removed count."""
    trajectories = getattr(buffer, "trajectories", None)
    if not isinstance(trajectories, list) or len(trajectories) < 4:
        return 0
    priorities = getattr(buffer, "priorities", None)
    indexed = [(i, float(trajectories[i].get("reward", 0) or 0)) for i in range(len(trajectories))]
    indexed.sort(key=lambda item: item[1], reverse=True)
    keep_count = max(1, int(round(len(indexed) * max(0.05, min(0.50, keep_pct)))))
    keep_indices = {item[0] for item in indexed[:keep_count]}
    new_trajectories = [t for i, t in enumerate(trajectories) if i in keep_indices]
    new_priorities: list[Any] = []
    if isinstance(priorities, list) and len(priorities) == len(trajectories):
        new_priorities = [p for i, p in enumerate(priorities) if i in keep_indices]
    removed = len(trajectories) - len(new_trajectories)
    trajectories[:] = new_trajectories
    if new_priorities:
        priorities[:] = new_priorities
    return removed
