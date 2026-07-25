"""Raptor v4: adaptive oracle must find patterns on real-scale 1m MES moves."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.pattern_miner import (
    _BIRTH_FALLBACK_STOP_PCT,
    _LEGACY_STOP_PCT,
    calibrate_oracle_stops,
    mine_winning_patterns,
)


def _synthetic_trend_ticks(n: int = 400) -> list[dict]:
    """Slow trend + noise so calibrated stops hit; legacy 0.75% would not."""
    ticks: list[dict] = []
    price = 5000.0
    for i in range(n):
        # ~0.15% swings with occasional 0.25% bursts
        if i % 40 < 20:
            price *= 1.0008
        else:
            price *= 0.9993
        ticks.append(
            {
                "last": price,
                "close": price,
                "regime": "TREND_UP" if i % 40 < 20 else "TREND_DOWN",
                "trend_atr_norm": 0.0015,
                "timestamp": f"2026-01-01T00:{i//60:02d}:{i%60:02d}",
            }
        )
    return ticks


@pytest.mark.unit
def test_calibrate_stops_sane_band() -> None:
    ticks = _synthetic_trend_ticks(300)
    stop, target = calibrate_oracle_stops(ticks, max_hold_bars=120)
    assert 0.0003 <= stop <= 0.01
    assert target > stop
    assert target <= 0.02


@pytest.mark.unit
def test_adaptive_mine_finds_patterns() -> None:
    ticks = _synthetic_trend_ticks(500)
    result = mine_winning_patterns(
        ticks=ticks,
        stage=CurriculumStage.STAGE1_TREND,
        runtime=None,
        workspace_root=Path("."),
        max_patterns=100,
        scan_stride=3,
        max_hold_bars=80,
        auto_calibrate=True,
        min_pnl_usd=0.0,
    )
    assert result.scanned > 0
    assert len(result.patterns) > 0
    assert result.reason in {"ok", "ok_capped"}
    assert result.stop_pct <= 0.01


@pytest.mark.unit
def test_birth_fallback_below_legacy_defaults() -> None:
    """Document pre-v4 failure: legacy 0.75% stop never hits 1m MES (~0.15% moves)."""
    assert _BIRTH_FALLBACK_STOP_PCT < _LEGACY_STOP_PCT
    assert _BIRTH_FALLBACK_STOP_PCT < 0.002
