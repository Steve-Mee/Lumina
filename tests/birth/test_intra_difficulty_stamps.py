"""Contiguous windows stamp _intra_difficulty for easy_trades telemetry."""

from __future__ import annotations

import random

import pytest

from lumina_core.birth.curriculum_intra import sample_contiguous_intra_windows


def _series(n: int = 400) -> list[dict]:
    out = []
    px = 5000.0
    for i in range(n):
        px += 0.2
        out.append(
            {
                "bar_index": i,
                "last": px,
                "close": px,
                "regime": "NEUTRAL",
                "_intra_difficulty": "easy" if i % 4 else "hard",
            }
        )
    return out


@pytest.mark.unit
def test_contiguous_windows_stamp_easy_hard() -> None:
    series = _series(400)
    easy = [t for t in series if t["_intra_difficulty"] == "easy"]
    hard = [t for t in series if t["_intra_difficulty"] == "hard"]
    pool = sample_contiguous_intra_windows(
        easy,
        hard,
        hard_pct=0.25,
        pool_size=300,
        rng=random.Random(3),
        window_len=50,
        chrono_source=series,
    )
    assert len(pool) >= 50
    diffs = {str(t.get("_intra_difficulty")) for t in pool}
    assert "easy" in diffs or "hard" in diffs
    easy_n = sum(1 for t in pool if t.get("_intra_difficulty") == "easy")
    assert easy_n > 0
