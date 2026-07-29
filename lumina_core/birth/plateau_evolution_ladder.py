"""Plateau evolution ladder tables + step API (Starship Seal II thin extract).

Keeps ladder physics out of the plateau detection god-surface while
``plateau_escalator`` remains the compatibility re-export + state host.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.plateau_evolution_ladder")


class EvolutionAction(str, Enum):
    DETECT = "detect"
    EXPAND_DATA = "expand_data"
    POLICY_ROLLBACK = "policy_rollback"
    INTRA_EASY_ONLY = "intra_easy_only"
    FRESH_POLICY = "fresh_policy_keep_buffer"
    ORACLE_DISTILL = "oracle_distill"
    PHOENIX_RESET = "phoenix_reset"
    TERMINAL = "terminal_stall"


EVOLUTION_STEP_ACTIONS: tuple[EvolutionAction, ...] = (
    EvolutionAction.EXPAND_DATA,
    EvolutionAction.POLICY_ROLLBACK,
    EvolutionAction.INTRA_EASY_ONLY,
    EvolutionAction.FRESH_POLICY,
    EvolutionAction.ORACLE_DISTILL,
    EvolutionAction.PHOENIX_RESET,
)

# Stage3 mixed — quality & selectivity before nuclear fresh policy.
STAGE3_EVOLUTION_STEP_ACTIONS: tuple[EvolutionAction, ...] = (
    EvolutionAction.ORACLE_DISTILL,
    EvolutionAction.INTRA_EASY_ONLY,
    EvolutionAction.POLICY_ROLLBACK,
    EvolutionAction.EXPAND_DATA,
    EvolutionAction.FRESH_POLICY,
    EvolutionAction.PHOENIX_RESET,
)

ACTION_LABELS: dict[EvolutionAction, str] = {
    EvolutionAction.DETECT: "Plateau detected",
    EvolutionAction.EXPAND_DATA: "Expand historical data window",
    EvolutionAction.POLICY_ROLLBACK: "Rollback policy to best winrate snapshot",
    EvolutionAction.INTRA_EASY_ONLY: "Easy-only / stage skill explore (stage-aware)",
    EvolutionAction.FRESH_POLICY: "Fresh policy init (keep buffer/oracle)",
    EvolutionAction.ORACLE_DISTILL: "Oracle distillation (top buffer trajectories)",
    EvolutionAction.PHOENIX_RESET: "Phoenix reset (fresh policy + oracle buffer)",
    EvolutionAction.TERMINAL: "Evolution exhausted — terminal stall",
}


def evolution_actions_for_stage(stage: CurriculumStage | None = None) -> tuple[EvolutionAction, ...]:
    """Stage-aware evolution ladder (Stage3 prioritizes skill quality over fresh weights)."""
    if stage == CurriculumStage.STAGE3_MIXED:
        return STAGE3_EVOLUTION_STEP_ACTIONS
    return EVOLUTION_STEP_ACTIONS


def evolution_ladder_exhausted(
    state: Any,
    stage: CurriculumStage | None = None,
    *,
    max_steps: int | None = None,
) -> bool:
    """True when all real evolution actions have been applied (or Starship max_steps)."""
    ladder_len = len(evolution_actions_for_stage(stage))
    if max_steps is not None:
        ladder_len = min(ladder_len, max(1, int(max_steps)))
    return int(getattr(state, "evolution_step", 0) or 0) >= ladder_len


def evolution_actions_completed(
    state: Any,
    stage: CurriculumStage | None = None,
    *,
    max_steps: int | None = None,
) -> int:
    ladder_len = len(evolution_actions_for_stage(stage))
    if max_steps is not None:
        ladder_len = min(ladder_len, max(1, int(max_steps)))
    return min(int(getattr(state, "evolution_step", 0) or 0), ladder_len)


def evolution_phantom_steps(
    state: Any,
    stage: CurriculumStage | None = None,
    *,
    max_steps: int | None = None,
) -> int:
    ladder_len = len(evolution_actions_for_stage(stage))
    if max_steps is not None:
        ladder_len = min(ladder_len, max(1, int(max_steps)))
    return max(0, int(getattr(state, "evolution_step", 0) or 0) - ladder_len)


def action_for_step(
    step: int,
    stage: CurriculumStage | None = None,
) -> EvolutionAction:
    actions = evolution_actions_for_stage(stage)
    if step <= 0:
        return EvolutionAction.DETECT
    if step > len(actions):
        return EvolutionAction.TERMINAL
    return actions[step - 1]


def begin_evolution_step(
    state: Any,
    *,
    stage_trades: int,
    stage_wins: int,
    stage: CurriculumStage | None = None,
    max_steps: int | None = None,
) -> EvolutionAction:
    if evolution_ladder_exhausted(state, stage=stage, max_steps=max_steps):
        return EvolutionAction.TERMINAL
    next_step = int(getattr(state, "evolution_step", 0) or 0) + 1
    if max_steps is not None and next_step > max(1, int(max_steps)):
        state.evolution_step = max(1, int(max_steps))
        return EvolutionAction.TERMINAL
    next_action = action_for_step(next_step, stage=stage)
    if next_action == EvolutionAction.TERMINAL:
        state.evolution_step = len(evolution_actions_for_stage(stage))
        return EvolutionAction.TERMINAL
    state.evolution_step = next_step
    state.evolution_rollouts_this_step = 0
    state.winrate_at_step_start = float(stage_wins) / float(max(1, stage_trades))
    action = action_for_step(state.evolution_step, stage=stage)
    logger.info(
        "birth.plateau.evolution_step step=%s action=%s winrate=%.2f%% stage=%s",
        state.evolution_step,
        action.value,
        state.winrate_at_step_start * 100.0,
        getattr(stage, "value", stage),
    )
    return action
