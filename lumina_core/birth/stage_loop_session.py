"""Stage loop session — composition root + StageLoopSession class.

Recovery/progress/plateau/meta/data-ops live in mixin modules.
run() body: ``stage_loop_session_runner`` (Wave B PR-B4).
"""
from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_evolution_handler import PlateauEvolutionMixin
from lumina_core.birth.stage_loop_data_ops import StageLoopDataOpsMixin
from lumina_core.birth.stage_loop_iteration import StageLoopIterationMixin
from lumina_core.birth.stage_loop_meta import StageLoopMetaMixin
from lumina_core.birth.stage_loop_progress import StageLoopProgressMixin
from lumina_core.birth.stage_loop_recovery_mixin import StageLoopRecoveryMixin
from lumina_core.birth.stage_loop_session_runner import StageLoopSessionRunnerMixin


class StageLoopSession(
    PlateauEvolutionMixin,
    StageLoopRecoveryMixin,
    StageLoopProgressMixin,
    StageLoopMetaMixin,
    StageLoopDataOpsMixin,
    StageLoopIterationMixin,
    StageLoopSessionRunnerMixin,
):
    """Mutable stage-research session."""

    def __init__(
        self,
        host: Any,
        *,
        stage: CurriculumStage,
        stage_index: int,
        stage_ticks: list[dict[str, Any]],
        train_ticks: list[dict[str, Any]],
        holdout_ticks: list[dict[str, Any]],
        target: int,
        stage_progress_pct: float,
        training_mode: str,
        ppo_steps_per_update: int,
        polish_ppo_timesteps: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> None:
        self.host = host
        self.stage = stage
        self.stage_index = stage_index
        self.stage_ticks = stage_ticks
        self.train_ticks = train_ticks
        self.holdout_ticks = holdout_ticks
        self.target = target
        self.stage_progress_pct = stage_progress_pct
        self.training_mode = training_mode
        self.ppo_steps_per_update = ppo_steps_per_update
        self.polish_ppo_timesteps = polish_ppo_timesteps
        self.trade_budget_cap = trade_budget_cap
        self.prefer_real = prefer_real
        self.start_price = start_price


def run_stage_research_loop(
    host: Any,
    *,
    stage: CurriculumStage,
    stage_index: int,
    stage_ticks: list[dict[str, Any]],
    train_ticks: list[dict[str, Any]],
    holdout_ticks: list[dict[str, Any]],
    target: int,
    stage_progress_pct: float,
    training_mode: str,
    ppo_steps_per_update: int,
    polish_ppo_timesteps: int,
    trade_budget_cap: int,
    prefer_real: bool,
    start_price: float,
) -> dict[str, Any] | None:
    """BRO stage loop entry — delegates to StageLoopSession."""
    return StageLoopSession(
        host,
        stage=stage,
        stage_index=stage_index,
        stage_ticks=stage_ticks,
        train_ticks=train_ticks,
        holdout_ticks=holdout_ticks,
        target=target,
        stage_progress_pct=stage_progress_pct,
        training_mode=training_mode,
        ppo_steps_per_update=ppo_steps_per_update,
        polish_ppo_timesteps=polish_ppo_timesteps,
        trade_budget_cap=trade_budget_cap,
        prefer_real=prefer_real,
        start_price=start_price,
    ).run()
