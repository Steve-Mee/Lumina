"""Stage 1 intra easy→hard curriculum tests (ADR-0020)."""

from __future__ import annotations

import random

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    Stage1IntraCurriculumState,
    sample_intra_stage1_pool,
    split_stage1_trend_ticks,
    stage1_intra_state_from_metrics,
    stage1_trend_difficulty_score,
    update_stage1_intra_state,
)


def _trend_tick(
    *,
    strength: float,
    duration: float = 0.5,
    adx: float = 0.5,
) -> dict:
    return {
        "regime": "TREND_UP",
        "trend_regime_strength": strength,
        "trend_duration_norm": duration,
        "trend_adx_14": adx,
    }


@pytest.mark.unit
def test_stage1_difficulty_score_orders_strong_before_weak() -> None:
    strong = stage1_trend_difficulty_score(_trend_tick(strength=0.9, duration=0.9, adx=0.8))
    weak = stage1_trend_difficulty_score(_trend_tick(strength=0.18, duration=0.1, adx=0.1))
    assert strong > weak


@pytest.mark.unit
def test_split_stage1_trend_ticks_assigns_easy_and_hard_buckets() -> None:
    ticks = [
        _trend_tick(strength=0.9, duration=0.9, adx=0.8),
        _trend_tick(strength=0.85, duration=0.85, adx=0.75),
        _trend_tick(strength=0.18, duration=0.1, adx=0.1),
        _trend_tick(strength=0.15, duration=0.08, adx=0.08),
    ]
    easy_pool, hard_pool, meta = split_stage1_trend_ticks(ticks, easy_percentile=0.40, hard_percentile=0.40)
    assert meta["easy_count"] >= 1
    assert meta["hard_count"] >= 1
    assert all(t.get("_intra_difficulty") == "easy" for t in easy_pool)
    assert all(t.get("_intra_difficulty") == "hard" for t in hard_pool)


@pytest.mark.unit
def test_sample_intra_stage1_pool_respects_hard_pct() -> None:
    easy = [_trend_tick(strength=0.9) for _ in range(20)]
    hard = [_trend_tick(strength=0.1) for _ in range(20)]
    for t in easy:
        t["_intra_difficulty"] = "easy"
    for t in hard:
        t["_intra_difficulty"] = "hard"
    state = Stage1IntraCurriculumState(hard_pct=0.15)
    rng = random.Random(42)
    pool = sample_intra_stage1_pool(
        easy, hard, state, pool_size=200, rng=rng, window_len=5
    )
    hard_in_pool = sum(1 for t in pool if t.get("_intra_difficulty") == "hard")
    ratio = hard_in_pool / len(pool)
    assert 0.08 <= ratio <= 0.22


@pytest.mark.unit
def test_update_stage1_intra_state_ramps_after_stable_easy_winrate() -> None:
    cfg = BirthCurriculumConfig(
        intra_easy_winrate_target=0.50,
        intra_easy_stability_window=3,
        intra_hard_pct_step=0.05,
        intra_max_hard_pct=0.70,
        intra_initial_hard_pct=0.15,
    )
    state = Stage1IntraCurriculumState(hard_pct=cfg.intra_initial_hard_pct)
    for _ in range(3):
        update_stage1_intra_state(state, chunk_easy_trades=10, chunk_easy_wins=6, cfg=cfg)
    assert state.hard_pct == pytest.approx(0.20)
    assert state.easy_winrate_history == []


@pytest.mark.unit
def test_stage1_intra_state_from_metrics_restores_checkpoint() -> None:
    metrics = {
        "intra_stage1_hard_pct": 0.35,
        "intra_stage1_easy_trades": 120,
        "intra_stage1_easy_wins": 70,
        "intra_stage1_easy_winrate_history": [0.55, 0.52, 0.58],
    }
    state = stage1_intra_state_from_metrics(metrics, default_hard_pct=0.15)
    assert state.hard_pct == pytest.approx(0.35)
    assert state.easy_trades == 120
    assert state.easy_wins == 70
    assert state.easy_winrate_history == [0.55, 0.52, 0.58]
