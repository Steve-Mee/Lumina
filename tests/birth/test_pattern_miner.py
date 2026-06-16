from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.pattern_miner import mine_winning_patterns


def _rising_ticks(n: int) -> list[dict]:
    ticks: list[dict] = []
    price = 5000.0
    for i in range(n):
        price += 0.75
        ticks.append(
            {
                "timestamp": f"2026-01-01T{i:04d}:00Z",
                "last": price,
                "close": price,
                "bid": price - 0.25,
                "ask": price + 0.25,
                "volume": 120,
                "source": "real_historical",
                "regime": "TREND_UP",
            }
        )
    return ticks


@pytest.mark.unit
def test_oracle_miner_finds_wins_on_rising_ticks() -> None:
    ticks = _rising_ticks(600)
    result = mine_winning_patterns(
        ticks=ticks,
        stage=CurriculumStage.STAGE1_TREND,
        runtime=SimpleNamespace(),
        max_patterns=200,
        scan_stride=3,
        max_hold_bars=200,
        target_pct=0.005,
    )

    assert result.scanned > 0
    assert len(result.patterns) >= 10
    assert result.wins >= 10
    assert all(p.get("source") == "oracle" for p in result.patterns)
    assert all("vector" in (p.get("observation") or {}) for p in result.patterns)
