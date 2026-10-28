"""Raptor v13: true rolling WR from rollout chunks (not lifetime collapse)."""

from __future__ import annotations

import pytest

from lumina_core.birth.plateau_escalator import (
    prune_rolling_trade_chunks,
    rolling_winrate_from_chunks,
    rolling_winrate_last_n_trades,
)


@pytest.mark.unit
def test_chunks_true_window_differs_from_lifetime() -> None:
    # 100 trades @ 20% then 500 @ 40% → lifetime ~36.7%, rolling last 500 = 40%.
    chunks: list[tuple[int, int]] = [(100, 20)] + [(50, 20)] * 10
    lifetime = (20 + 200) / 600
    wr, source, covered = rolling_winrate_from_chunks(
        chunks, window=500, lifetime_wr=lifetime
    )
    assert source == "true_window"
    assert covered == 500
    assert wr == pytest.approx(0.40, abs=0.001)
    assert wr != pytest.approx(lifetime, abs=0.01)


@pytest.mark.unit
def test_empty_chunks_lifetime_fallback() -> None:
    wr, source, covered = rolling_winrate_from_chunks(
        [], window=500, lifetime_wr=0.318
    )
    assert source == "lifetime_fallback"
    assert wr == pytest.approx(0.318)
    assert covered == 0


@pytest.mark.unit
def test_partial_window_from_late_milestones() -> None:
    # Resume only has milestone at 2000; current 2379 — partial known window.
    result = rolling_winrate_last_n_trades(
        stage_trades=2379,
        stage_wins=758,
        wins_at_trade={2000: 620},
        window=500,
        return_meta=True,
    )
    assert isinstance(result, tuple)
    wr, source, covered = result
    assert source == "partial_window"
    assert covered == 379
    assert wr == pytest.approx((758 - 620) / 379, abs=0.001)
    assert wr != pytest.approx(758 / 2379, abs=0.01)


@pytest.mark.unit
def test_no_milestones_still_lifetime() -> None:
    result = rolling_winrate_last_n_trades(
        stage_trades=2000,
        stage_wins=620,
        wins_at_trade={},
        window=500,
        return_meta=True,
    )
    assert isinstance(result, tuple)
    wr, source, _covered = result
    assert source == "lifetime_fallback"
    assert wr == pytest.approx(620 / 2000)


@pytest.mark.unit
def test_chunks_preferred_over_milestones() -> None:
    chunks = [(50, 20)] * 12  # 600 trades @ 40%
    result = rolling_winrate_last_n_trades(
        stage_trades=3000,
        stage_wins=900,  # lifetime 30%
        wins_at_trade={2500: 750},
        window=500,
        chunks=chunks,
        return_meta=True,
    )
    assert isinstance(result, tuple)
    wr, source, covered = result
    assert source == "true_window"
    assert covered == 500
    assert wr == pytest.approx(0.40, abs=0.001)


@pytest.mark.unit
def test_prune_keeps_recent_coverage() -> None:
    chunks = [(50, 10)] * 40
    pruned = prune_rolling_trade_chunks(chunks, window=500, max_chunks=128)
    total = sum(t for t, _ in pruned)
    assert total >= 500
    assert len(pruned) <= 128
