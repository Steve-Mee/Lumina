"""Batch tick enrichment performance and progress callback."""

from __future__ import annotations

import time

import pytest

from lumina_core.birth.tick_enricher import enrich_ticks_for_sim


def _sample_ticks(n: int) -> list[dict[str, float | str | int]]:
    return [
        {
            "last": 5000.0 + i * 0.01,
            "close": 5000.0 + i * 0.01,
            "high": 5000.0 + i * 0.01 + 0.5,
            "low": 5000.0 + i * 0.01 - 0.5,
            "volume": 100,
            "source": "real",
            "bid": 5000.0 + i * 0.01 - 0.125,
            "ask": 5000.0 + i * 0.01 + 0.125,
        }
        for i in range(n)
    ]


@pytest.mark.unit
def test_enrich_ticks_progress_callback_fires() -> None:
    seen: list[tuple[int, int]] = []

    enrich_ticks_for_sim(_sample_ticks(500), on_progress=lambda done, total: seen.append((done, total)))

    assert seen
    assert seen[-1][0] == seen[-1][1]


@pytest.mark.unit
def test_enrich_ticks_5k_completes_within_budget() -> None:
    ticks = _sample_ticks(5000)
    started = time.perf_counter()
    enrich_ticks_for_sim(ticks)
    elapsed = time.perf_counter() - started
    assert elapsed < 30.0
