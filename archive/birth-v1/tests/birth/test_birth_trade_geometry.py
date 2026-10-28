"""Birth trade geometry SSOT — oracle/SIM/envelope share micro-scale stops."""

from __future__ import annotations

import random

import pytest

from lumina_core.birth.birth_trade_geometry import (
    BIRTH_FALLBACK_STOP_PCT,
    LEGACY_MACRO_STOP_PCT,
    MACRO_STOP_THRESHOLD,
    SOFT_PRIOR_DEFAULT_MULTIPLE,
    calibrate_birth_stops,
    clamp_birth_geometry,
    is_time_ordered,
    soft_prior_action_stops,
)
from lumina_core.birth.pattern_miner import calibrate_oracle_stops


def _synthetic_ticks(n: int = 200, step: float = 0.5) -> list[dict]:
    """Random-walk-ish ticks with ~0.1% bar moves (time-ordered bar_index)."""
    price = 5000.0
    ticks: list[dict] = []
    for i in range(n):
        price += step if i % 2 == 0 else -step * 0.8
        ticks.append(
            {
                "last": price,
                "close": price,
                "trend_atr_norm": 0.0002,
                "regime": "NEUTRAL",
                "bar_index": i,
            }
        )
    return ticks


@pytest.mark.unit
def test_fallback_geometry_is_micro_not_macro() -> None:
    geo = calibrate_birth_stops([])
    assert geo.stop_pct == pytest.approx(BIRTH_FALLBACK_STOP_PCT)
    assert geo.stop_pct < LEGACY_MACRO_STOP_PCT / 2
    assert geo.target_pct >= geo.stop_pct * 1.25


@pytest.mark.unit
def test_calibrate_on_ticks_stays_below_macro() -> None:
    geo = calibrate_birth_stops(_synthetic_ticks(300))
    assert geo.stop_pct < 0.005
    assert geo.target_pct <= 0.015
    assert geo.source.split("+")[0] in {
        "move_distribution",
        "atr_median",
        "fallback_thin",
        "fallback_empty",
        "atr_median_macro_guard",
    }
    assert geo.time_ordered is True


@pytest.mark.unit
def test_oracle_api_matches_geometry() -> None:
    ticks = _synthetic_ticks(250)
    s, t = calibrate_oracle_stops(ticks)
    geo = calibrate_birth_stops(ticks)
    assert s == pytest.approx(geo.stop_pct)
    assert t == pytest.approx(geo.target_pct)


@pytest.mark.unit
def test_soft_prior_pulls_macro_stops() -> None:
    geo = calibrate_birth_stops(_synthetic_ticks(200))
    s, t = soft_prior_action_stops(
        0.0075, 0.015, geometry=geo, max_multiple=SOFT_PRIOR_DEFAULT_MULTIPLE
    )
    assert s <= geo.stop_pct * SOFT_PRIOR_DEFAULT_MULTIPLE + 1e-9
    assert t >= s * 1.25 - 1e-9


@pytest.mark.unit
def test_clamp_respects_constitution_max() -> None:
    s, t = clamp_birth_geometry(0.05, 0.10)
    assert s <= 0.01
    assert t <= 0.05


@pytest.mark.unit
def test_shuffled_pool_never_move_distribution_macro() -> None:
    """Root-cause guard: IID/shuffle must not yield 0.008 + move_distribution."""
    chrono = _synthetic_ticks(400, step=2.0)
    # Wide price range so peak-over-shuffle would hit the hard cap without guard.
    for i, t in enumerate(chrono):
        t["last"] = 5000.0 + (i % 50) * 5.0
        t["close"] = t["last"]
        t["bar_index"] = i
    shuffled = list(chrono)
    random.Random(42).shuffle(shuffled)
    assert is_time_ordered(chrono) is True
    assert is_time_ordered(shuffled) is False

    geo_s = calibrate_birth_stops(shuffled, max_hold_bars=180)
    assert geo_s.source != "move_distribution" or geo_s.stop_pct < MACRO_STOP_THRESHOLD
    assert geo_s.stop_pct < MACRO_STOP_THRESHOLD or geo_s.macro_rejected
    # Must not report honest move_distribution at the poison cap.
    if geo_s.stop_pct >= 0.007:
        assert geo_s.source != "move_distribution"
    assert geo_s.time_ordered is False
    assert geo_s.source.split("+")[0] in {
        "fallback_disordered_pool",
        "atr_median_disordered",
        "atr_median",
        "fallback_thin",
    }


@pytest.mark.unit
def test_chrono_pool_allows_move_distribution() -> None:
    chrono = _synthetic_ticks(400)
    geo = calibrate_birth_stops(chrono, max_hold_bars=90)
    assert geo.time_ordered is True
    assert geo.stop_pct < 0.005
    assert geo.source.split("+")[0] in {
        "move_distribution",
        "atr_median",
        "atr_median_macro_guard",
    }


@pytest.mark.unit
def test_is_time_ordered_detects_shuffle() -> None:
    ticks = [{"bar_index": i, "last": 100.0 + i * 0.01} for i in range(50)]
    assert is_time_ordered(ticks) is True
    bad = list(ticks)
    random.Random(0).shuffle(bad)
    assert is_time_ordered(bad) is False
