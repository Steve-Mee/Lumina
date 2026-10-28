"""Contiguous intra windows — no IID bar shuffle for SIM path continuity."""

from __future__ import annotations

import random

import pytest

from lumina_core.birth.curriculum_intra import (
    Stage1IntraCurriculumState,
    sample_contiguous_intra_windows,
    sample_intra_stage1_pool,
)


def _chrono_series(n: int = 500) -> list[dict]:
    out = []
    px = 5000.0
    for i in range(n):
        px += 0.25 if i % 3 else -0.2
        out.append(
            {
                "bar_index": i,
                "last": px,
                "close": px,
                "regime": "NEUTRAL",
                "_intra_difficulty": "easy" if i % 5 else "hard",
            }
        )
    return out


@pytest.mark.unit
def test_sample_windows_preserve_bar_order_inside_window() -> None:
    series = _chrono_series(400)
    easy = [t for t in series if t["_intra_difficulty"] == "easy"]
    hard = [t for t in series if t["_intra_difficulty"] == "hard"]
    rng = random.Random(7)
    pool = sample_contiguous_intra_windows(
        easy,
        hard,
        hard_pct=0.3,
        pool_size=512,
        rng=rng,
        window_len=64,
        chrono_source=series,
    )
    assert len(pool) >= 64
    # Within each window of 64, bar_index must be non-decreasing contiguous.
    for start in range(0, len(pool) - 63, 64):
        window = pool[start : start + 64]
        idxs = [int(t["bar_index"]) for t in window]
        assert idxs == list(range(idxs[0], idxs[0] + len(idxs))), idxs[:5]


@pytest.mark.unit
def test_sample_intra_stage1_uses_contiguous_api() -> None:
    series = _chrono_series(300)
    easy = series[:150]
    hard = series[150:]
    # Tag for membership
    for t in easy:
        t["_intra_difficulty"] = "easy"
    for t in hard:
        t["_intra_difficulty"] = "hard"
    state = Stage1IntraCurriculumState(hard_pct=0.2)
    pool = sample_intra_stage1_pool(
        easy,
        hard,
        state,
        pool_size=200,
        rng=random.Random(1),
        window_len=50,
        chrono_source=series,
    )
    assert len(pool) >= 50
    # Full pool is not a pure random permutation of all bars (local order exists).
    mono_runs = 0
    for i in range(1, min(len(pool), 100)):
        if pool[i]["bar_index"] == pool[i - 1]["bar_index"] + 1:
            mono_runs += 1
    assert mono_runs >= 20
