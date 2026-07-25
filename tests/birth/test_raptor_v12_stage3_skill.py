"""Raptor v12: rolling milestones + stage3 evolution skill substitute."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    rolling_winrate_last_n_trades,
)
from lumina_core.birth.plateau_evolution_handler import PlateauEvolutionMixin


@pytest.mark.unit
def test_rolling_uses_milestones_not_lifetime() -> None:
    # 2000 trades, 620 wins lifetime 31%. Last 500: +200 wins → 40% rolling.
    wins_at = {1500: 420}  # wins before last 500
    roll = rolling_winrate_last_n_trades(
        stage_trades=2000,
        stage_wins=620,
        wins_at_trade=wins_at,
        window=500,
    )
    assert roll == pytest.approx(0.40, abs=0.001)


@pytest.mark.unit
def test_rolling_without_milestones_falls_back_to_lifetime() -> None:
    roll = rolling_winrate_last_n_trades(
        stage_trades=2000,
        stage_wins=620,
        wins_at_trade={},
        window=500,
    )
    assert roll == pytest.approx(620 / 2000, abs=0.001)


class _FakeEvo(PlateauEvolutionMixin):
    def __init__(self, stage: CurriculumStage) -> None:
        self.stage = stage
        self.intra_state = None
        self.intra_s2_state = None
        self.active_stage_ticks: list = []
        self.stage_trades = 2100
        self.stage_wins = 650
        self.strong_recovery_mode = False
        self.strong_recovery_attempts = 0
        self.cur_cfg = BirthCurriculumConfig(exploration_steps=256)
        self.host = SimpleNamespace()
        self.plateau_state = SimpleNamespace()

    def _rebuild_intra_pools(self, ticks):  # type: ignore[no-untyped-def]
        return None


@pytest.mark.unit
def test_intra_easy_only_stage3_applies_skill_explore() -> None:
    fake = _FakeEvo(CurriculumStage.STAGE3_MIXED)
    detail, applied = fake._apply_plateau_evolution_action(EvolutionAction.INTRA_EASY_ONLY)
    assert applied is True
    assert "stage3" in detail.lower()
    assert "not stage1" not in detail.lower()
    assert fake.strong_recovery_mode is True
    assert fake.cur_cfg.exploration_steps >= 256 * 4


@pytest.mark.unit
def test_intra_easy_only_stage1_uses_intra_pool() -> None:
    fake = _FakeEvo(CurriculumStage.STAGE1_TREND)
    fake.intra_state = SimpleNamespace(
        hard_pct=0.5,
        easy_trades=10,
        easy_wins=3,
        easy_winrate_history=[0.3],
    )
    detail, applied = fake._apply_plateau_evolution_action(EvolutionAction.INTRA_EASY_ONLY)
    assert applied is True
    assert "stage1" in detail.lower()
    assert fake.intra_state.hard_pct == 0.0
