"""Stage 2 intra easy→hard range patience curriculum."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    Stage2IntraCurriculumState,
    split_stage2_range_ticks,
    update_stage2_intra_state,
)


def _range_ticks(n: int, *, adx: float) -> list[dict]:
    return [
        {
            "timestamp": f"2026-01-01T{i:04d}:00Z",
            "last": 5000.0 + i * 0.1,
            "regime": "RANGING",
            "trend_adx_14": adx,
            "trend_regime_strength": 0.1 if adx < 15 else 0.8,
            "trend_atr_norm": 0.2,
        }
        for i in range(n)
    ]


@pytest.mark.unit
def test_split_stage2_range_ticks_produces_easy_and_hard() -> None:
    ticks = _range_ticks(200, adx=10.0) + _range_ticks(200, adx=35.0)
    easy, hard, meta = split_stage2_range_ticks(ticks)
    assert len(easy) >= 50
    assert len(hard) >= 50
    assert meta["total"] == 400


@pytest.mark.unit
def test_update_stage2_intra_state_ramps_hard_pct() -> None:
    cfg = BirthCurriculumConfig(
        intra_stage2_easy_flat_target=0.40,
        intra_stage2_easy_stability_window=2,
        intra_stage2_hard_pct_step=0.10,
        intra_stage2_max_hard_pct=0.70,
        intra_stage2_easy_winrate_target=0.38,
    )
    state = Stage2IntraCurriculumState(hard_pct=0.15)
    # Flat-in-band + easy quality WR ≥ 38% required before hard ramp.
    update_stage2_intra_state(
        state,
        chunk_flat_bars=50,
        chunk_range_signals=100,
        cfg=cfg,
        chunk_easy_trades=20,
        chunk_easy_wins=10,
    )
    update_stage2_intra_state(
        state,
        chunk_flat_bars=45,
        chunk_range_signals=100,
        cfg=cfg,
        chunk_easy_trades=20,
        chunk_easy_wins=10,
    )
    assert state.hard_pct == pytest.approx(0.25)
