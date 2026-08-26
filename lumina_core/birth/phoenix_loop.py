"""Phoenix rebirth loop — targeted reset with preserved cache/DNA after remediation exhaust."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.phoenix_loop")

PHOENIX_CYCLE_REASON = "phoenix_cycle"
# Backward-compatible alias consumed by engine/tests during migration.
LEGACY_HUMAN_GATE_REASON = "stall_remediation_exhausted"


class PhoenixNoveltyAction(str, Enum):
    EXPAND_DATA = "expand_data"
    POLICY_SWARM = "policy_swarm"
    REWARD_SWEEP = "reward_sweep"
    SOFT_GATE = "soft_gate"
    WIDEN_HORIZON = "widen_horizon"


PHOENIX_NOVELTY_SEQUENCE: tuple[PhoenixNoveltyAction, ...] = (
    PhoenixNoveltyAction.EXPAND_DATA,
    PhoenixNoveltyAction.REWARD_SWEEP,
    PhoenixNoveltyAction.EXPAND_DATA,
    PhoenixNoveltyAction.WIDEN_HORIZON,
)


@dataclass(slots=True)
class PhoenixLoopState:
    active: bool = False
    phoenix_count: int = 0
    last_action: str = ""
    last_cycle_at: float = 0.0
    preserve_tick_cache: bool = True
    preserve_partial_dna: bool = True
    preserve_best_policy: bool = True
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_metrics(self) -> dict[str, Any]:
        return {
            "phoenix_loop_active": self.active,
            "phoenix_count": int(self.phoenix_count),
            "phoenix_last_action": str(self.last_action),
            "phoenix_last_cycle_at": float(self.last_cycle_at),
            "phoenix_history": list(self.history)[-16:],
        }

    @classmethod
    def from_metrics(cls, metrics: dict[str, Any] | None) -> PhoenixLoopState:
        if not isinstance(metrics, dict):
            return cls()
        history = metrics.get("phoenix_history")
        return cls(
            active=bool(metrics.get("phoenix_loop_active", False)),
            phoenix_count=int(metrics.get("phoenix_count", 0) or 0),
            last_action=str(metrics.get("phoenix_last_action", "") or ""),
            last_cycle_at=float(metrics.get("phoenix_last_cycle_at", 0) or 0),
            history=[dict(x) for x in history if isinstance(x, dict)]
            if isinstance(history, list)
            else [],
        )


def can_start_phoenix(state: PhoenixLoopState, *, cfg: BirthCurriculumConfig) -> bool:
    if not cfg.phoenix_loop_enabled:
        return False
    return state.phoenix_count < max(1, int(cfg.phoenix_max_cycles))


def select_phoenix_novelty(
    state: PhoenixLoopState,
    *,
    cfg: BirthCurriculumConfig,
    circuit_breaker: bool = False,
) -> PhoenixNoveltyAction:
    if circuit_breaker:
        return PhoenixNoveltyAction.EXPAND_DATA
    idx = state.phoenix_count % len(PHOENIX_NOVELTY_SEQUENCE)
    return PHOENIX_NOVELTY_SEQUENCE[idx]


def begin_phoenix_cycle(
    state: PhoenixLoopState,
    *,
    novelty: PhoenixNoveltyAction,
    stall_reason: str,
) -> None:
    state.active = True
    state.phoenix_count += 1
    state.last_action = novelty.value
    state.last_cycle_at = time.time()
    state.history.append(
        {
            "timestamp": state.last_cycle_at,
            "action": novelty.value,
            "stall_reason": str(stall_reason or ""),
            "cycle": int(state.phoenix_count),
        }
    )
    logger.warning(
        "birth.phoenix.cycle_started count=%s action=%s reason=%s",
        state.phoenix_count,
        novelty.value,
        stall_reason,
    )


def build_phoenix_checkpoint_patch(
    *,
    novelty: PhoenixNoveltyAction,
    curriculum_stage: str,
    cfg: BirthCurriculumConfig,
) -> dict[str, Any]:
    """Checkpoint hints consumed by engine resume path."""
    metrics: dict[str, Any] = {
        "phoenix_cycle": True,
        "phoenix_novelty": novelty.value,
        "pending_data_expand": novelty in {
            PhoenixNoveltyAction.EXPAND_DATA,
            PhoenixNoveltyAction.WIDEN_HORIZON,
        },
        "pending_policy_swarm": novelty == PhoenixNoveltyAction.POLICY_SWARM,
        "pending_reward_sweep": novelty == PhoenixNoveltyAction.REWARD_SWEEP,
        "soft_gate_active": novelty == PhoenixNoveltyAction.SOFT_GATE,
    }
    if novelty == PhoenixNoveltyAction.SOFT_GATE:
        metrics["soft_gate_winrate_threshold"] = float(cfg.stage1_winrate_pass_floor)
    if novelty == PhoenixNoveltyAction.WIDEN_HORIZON:
        metrics["force_max_data_horizon"] = True
    return {
        "curriculum_stage": str(curriculum_stage or ""),
        "phase": "phoenix_cycle",
        "stage_metrics": metrics,
        "terminal_stall_reason": PHOENIX_CYCLE_REASON,
    }


def best_policy_snapshot_path(workspace_root: Path | str, curriculum_stage: str) -> Path:
    stage = str(curriculum_stage or "unknown").strip().lower()
    return Path(workspace_root) / "lumina_agents" / "ppo" / f"birth_best_{stage}.zip"