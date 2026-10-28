"""Raptor v14: stage3 ladder order + failure key + action_for_step."""

from __future__ import annotations

import pytest

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    STAGE3_EVOLUTION_STEP_ACTIONS,
    action_for_step,
    evolution_actions_for_stage,
    maybe_update_best_winrate,
    PlateauState,
)
from lumina_core.birth.config import BirthCurriculumConfig


@pytest.mark.unit
def test_stage3_ladder_oracle_before_fresh() -> None:
    actions = evolution_actions_for_stage(CurriculumStage.STAGE3_MIXED)
    assert actions[0] == EvolutionAction.ORACLE_DISTILL
    assert EvolutionAction.FRESH_POLICY in actions
    assert actions.index(EvolutionAction.ORACLE_DISTILL) < actions.index(
        EvolutionAction.FRESH_POLICY
    )
    assert action_for_step(1, stage=CurriculumStage.STAGE3_MIXED) == EvolutionAction.ORACLE_DISTILL
    assert action_for_step(5, stage=CurriculumStage.STAGE3_MIXED) == EvolutionAction.FRESH_POLICY


@pytest.mark.unit
def test_stage1_ladder_unchanged_order() -> None:
    assert action_for_step(1, stage=CurriculumStage.STAGE1_TREND) == EvolutionAction.EXPAND_DATA
    assert action_for_step(4, stage=CurriculumStage.STAGE1_TREND) == EvolutionAction.FRESH_POLICY


@pytest.mark.unit
def test_stage3_actions_length_matches() -> None:
    assert len(STAGE3_EVOLUTION_STEP_ACTIONS) == 6


@pytest.mark.unit
def test_maybe_update_best_rolling() -> None:
    cfg = BirthCurriculumConfig(plateau_save_best_policy=True, plateau_best_policy_min_trades=100)
    state = PlateauState()
    assert maybe_update_best_winrate(
        state,
        stage_trades=500,
        stage_wins=150,
        policy_path="/tmp/life.zip",
        cfg=cfg,
        rolling_winrate=0.40,
        rolling_source="true_window",
    )
    assert state.best_winrate == pytest.approx(0.30)
    assert state.best_rolling_winrate == pytest.approx(0.40)
    assert state.best_rolling_policy_path == "/tmp/life.zip"
