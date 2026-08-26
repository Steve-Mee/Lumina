"""Plan completeness: frozen geometry, prepare chrono, first-touch, segment gaps."""

from __future__ import annotations

import inspect
import random
from unittest.mock import MagicMock

import numpy as np
import pytest

from lumina_core.birth.birth_trade_geometry import (
    SEGMENT_BREAK_KEY,
    SEGMENT_ID_KEY,
    calibrate_birth_stops,
    soft_prior_action_stops,
)
from lumina_core.birth.curriculum_intra import (
    Stage1IntraCurriculumState,
    sample_contiguous_intra_windows,
)
from lumina_core.birth.stage_loop_rollout_cycle import StageLoopRolloutCycleMixin
from lumina_core.birth.stage_loop_rollout_pre import StageLoopRolloutPreMixin
from lumina_core.birth.stage_loop_session_phase_prepare_init import (
    SessionPhasePrepareInitMixin,
)


def _rw_ticks(n: int = 500, seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    px = 5000.0
    out = []
    for i in range(n):
        px *= 1.0 + rng.uniform(-0.0004, 0.0004)
        out.append(
            {
                "bar_index": i,
                "last": px,
                "close": px,
                "trend_atr_norm": 0.00025,
                "timestamp": f"2026-03-01T10:{i // 60:02d}:{i % 60:02d}",
                "regime": "NEUTRAL",
            }
        )
    return out


@pytest.mark.unit
def test_rollout_cycle_passes_trade_geometry_kwarg() -> None:
    src = inspect.getsource(StageLoopRolloutCycleMixin._run_sim_and_apply_metrics)
    assert "trade_geometry" in src
    assert "_birth_trade_geometry" in src


@pytest.mark.unit
def test_prepare_init_calibs_stage_or_train_not_active_only() -> None:
    src = inspect.getsource(SessionPhasePrepareInitMixin)
    assert "active_stage_ticks" in src or "active_train" in src
    assert "calibrate_birth_stops" in src


@pytest.mark.unit
def test_rollout_pre_prefers_frozen_geometry() -> None:
    src = inspect.getsource(StageLoopRolloutPreMixin._prepare_rollout_cycle)
    assert "_birth_trade_geometry" in src
    assert "NEVER recalibrate on shuffled" in src or "frozen" in src.lower()
    # Must not bare-calibrate active_ticks as primary SSOT.
    compact = "".join(src.split())
    assert "calibrate_birth_stops(list(active_ticks" not in compact


@pytest.mark.unit
def test_first_touch_micro_near_floor() -> None:
    """Random entries at calibrated micro geometry should land near ~35% target hits."""
    ticks = _rw_ticks(2000, seed=3)
    geo = calibrate_birth_stops(ticks, max_hold_bars=90)
    assert geo.stop_pct < 0.005
    prices = np.array([float(t["close"]) for t in ticks], dtype=float)
    stop, target = float(geo.stop_pct), float(geo.target_pct)
    hold = 90
    c_stop = c_tgt = 0
    for i in range(50, len(prices) - hold - 1, 40):
        for side in (1.0, -1.0):
            entry = prices[i]
            if entry <= 0:
                continue
            outcome = None
            for j in range(i + 1, i + hold + 1):
                ret = (prices[j] - entry) / entry * side
                if ret <= -stop:
                    outcome = "stop"
                    break
                if ret >= target:
                    outcome = "target"
                    break
            if outcome == "stop":
                c_stop += 1
            elif outcome == "target":
                c_tgt += 1
    dec = c_stop + c_tgt
    assert dec >= 30
    thr = c_tgt / float(dec)
    # Truthful band around expectancy floor physics (not a guarantee of live WR).
    assert 0.25 <= thr <= 0.50, thr


@pytest.mark.unit
def test_segment_break_stops_peak_walk_macro() -> None:
    """Concatenated windows with segment breaks must not invent macro peak moves."""
    a = _rw_ticks(200, seed=1)
    b = _rw_ticks(200, seed=2)
    # Force large price jump between segments.
    for t in b:
        t["last"] = float(t["last"]) * 1.05
        t["close"] = t["last"]
        t["bar_index"] = int(t["bar_index"]) + 10_000
    joined = []
    for j, t in enumerate(a):
        row = dict(t)
        row[SEGMENT_ID_KEY] = 0
        joined.append(row)
    for j, t in enumerate(b):
        row = dict(t)
        row[SEGMENT_ID_KEY] = 1
        if j == 0:
            row[SEGMENT_BREAK_KEY] = True
        joined.append(row)
    geo = calibrate_birth_stops(joined, max_hold_bars=180)
    assert geo.stop_pct < 0.005
    assert geo.source in {
        "move_distribution",
        "atr_median",
        "atr_median_macro_guard",
        "fallback_empty",
        "atr_median_disordered",
        "fallback_disordered_pool",
    }


@pytest.mark.unit
def test_contiguous_windows_stamp_segment_breaks() -> None:
    series = _rw_ticks(400)
    easy = series[:200]
    hard = series[200:]
    pool = sample_contiguous_intra_windows(
        easy,
        hard,
        hard_pct=0.3,
        pool_size=300,
        rng=random.Random(2),
        window_len=50,
        chrono_source=series,
    )
    breaks = sum(1 for t in pool if t.get(SEGMENT_BREAK_KEY))
    assert breaks >= 2
    ids = {t.get(SEGMENT_ID_KEY) for t in pool}
    assert len(ids) >= 2


@pytest.mark.unit
def test_soft_prior_default_multiple_caps_macro() -> None:
    ticks = _rw_ticks(200)
    geo = calibrate_birth_stops(ticks)
    s, t = soft_prior_action_stops(0.008, 0.015, geometry=geo)
    assert s <= geo.stop_pct * 2.5 + 1e-9
    assert t >= s * 1.25 - 1e-9
