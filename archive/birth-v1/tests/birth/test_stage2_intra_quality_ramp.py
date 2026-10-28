"""Stage-2 intra hard ramp requires quality WR, not flat-only."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum_intra import (
    Stage2IntraCurriculumState,
    stage2_range_quality_score,
    update_stage2_intra_state,
)


@pytest.mark.unit
def test_flat_alone_does_not_ramp_hard() -> None:
    cfg = BirthCurriculumConfig(
        intra_stage2_easy_stability_window=2,
        intra_stage2_easy_flat_target=0.40,
        intra_stage2_hard_pct_step=0.05,
        intra_stage2_easy_winrate_target=0.38,
    )
    state = Stage2IntraCurriculumState(hard_pct=0.15)
    update_stage2_intra_state(
        state,
        chunk_flat_bars=40,
        chunk_range_signals=100,
        cfg=cfg,
        chunk_easy_trades=0,
        chunk_easy_wins=0,
    )
    update_stage2_intra_state(
        state,
        chunk_flat_bars=45,
        chunk_range_signals=100,
        cfg=cfg,
        chunk_easy_trades=0,
        chunk_easy_wins=0,
    )
    assert state.hard_pct == pytest.approx(0.15)


@pytest.mark.unit
def test_quality_wr_and_flat_ramps_hard() -> None:
    cfg = BirthCurriculumConfig(
        intra_stage2_easy_stability_window=2,
        intra_stage2_easy_flat_target=0.40,
        intra_stage2_hard_pct_step=0.05,
        intra_stage2_max_hard_pct=0.70,
        intra_stage2_easy_winrate_target=0.38,
    )
    state = Stage2IntraCurriculumState(hard_pct=0.15)
    for _ in range(2):
        update_stage2_intra_state(
            state,
            chunk_flat_bars=45,
            chunk_range_signals=100,
            cfg=cfg,
            chunk_easy_trades=20,
            chunk_easy_wins=10,  # 50% WR
        )
    assert state.hard_pct == pytest.approx(0.20)


@pytest.mark.unit
def test_easy_quality_collapse_deramps_hard() -> None:
    """P2: truthful reverse curriculum when easy WR collapses."""
    cfg = BirthCurriculumConfig(
        intra_stage2_easy_stability_window=2,
        intra_stage2_easy_flat_target=0.40,
        intra_stage2_hard_pct_step=0.05,
        intra_stage2_initial_hard_pct=0.15,
        intra_stage2_easy_winrate_target=0.38,
    )
    state = Stage2IntraCurriculumState(hard_pct=0.40)
    for _ in range(2):
        update_stage2_intra_state(
            state,
            chunk_flat_bars=45,
            chunk_range_signals=100,
            cfg=cfg,
            chunk_easy_trades=20,
            chunk_easy_wins=4,  # 20% WR << 0.38 * 0.90
        )
    assert state.hard_pct == pytest.approx(0.35)


@pytest.mark.unit
def test_quality_score_prefers_fade_setup() -> None:
    calm = {
        "trend_adx_14": 0.05,
        "trend_regime_strength": 0.05,
        "trend_atr_norm": 0.0001,
        "trend_slope_5": 0.0,
        "trend_slope_30": 0.0,
        "imbalance": 1.0,
    }
    fade = {
        **calm,
        "trend_slope_5": -0.02,
        "trend_slope_30": 0.0,
        "imbalance": 1.3,
    }
    assert stage2_range_quality_score(fade) >= stage2_range_quality_score(calm)
