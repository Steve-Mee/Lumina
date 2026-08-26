"""Birth data expansion ladder helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from lumina_core.birth.data_expansion import (
    clamp_expansion_steps,
    default_expansion_steps,
    expand_birth_data,
    expansion_ladder_at_max,
)
from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.stage_loop_data_cache import StageLoopDataCacheMixin


class _EmptyMDS:
    def load_historical_ohlc_extended(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return []


class _EmptyRuntime:
    ohlc_1min = None


@pytest.mark.unit
def test_expansion_ladder_at_max_when_step_saturated() -> None:
    steps = default_expansion_steps()
    assert expansion_ladder_at_max(len(steps), steps, has_train_ticks=True) is True
    assert expansion_ladder_at_max(len(steps), steps, has_train_ticks=False) is False
    assert expansion_ladder_at_max(0, steps, has_train_ticks=True) is False


@pytest.mark.unit
def test_expansion_ladder_at_max_empty_steps() -> None:
    assert expansion_ladder_at_max(4, [], has_train_ticks=True) is False


@pytest.mark.unit
def test_clamp_expansion_steps_365_keeps_foundation_ladder() -> None:
    assert clamp_expansion_steps([90, 180, 365, 730], max_real_days=365) == [90, 180, 365]
    assert default_expansion_steps() == [90, 180, 365]


@pytest.mark.unit
def test_clamp_expansion_steps_to_max_real_days() -> None:
    clamped = clamp_expansion_steps([90, 180, 365, 730], max_real_days=112)
    assert clamped == [90, 112]
    assert max(clamped) == 112
    assert all(d <= 112 for d in clamped)


@pytest.mark.unit
def test_actual_calendar_days_from_ticks() -> None:
    ticks = [
        {"timestamp": "2026-07-01T00:00:00+00:00"},
        {"timestamp": "2026-07-10T12:00:00+00:00"},
    ]
    assert actual_calendar_days_from_ticks(ticks) == 10
    assert actual_calendar_days_from_ticks([]) == 0


@pytest.mark.unit
def test_clamp_expansion_steps_floor_refuses_start_below_90() -> None:
    """max_real_days=56 is not a live Birth ladder — floor is Foundation start 90."""
    steps = clamp_expansion_steps([90, 180, 365, 730], max_real_days=56)
    assert steps == [FOUNDATION_HISTORY_START_DAYS]
    result = expand_birth_data(
        market_data_service=_EmptyMDS(),
        runtime=_EmptyRuntime(),
        current_step=0,
        expansion_steps=steps,
        max_real_days=56,
        synthetic_fallback_fn=None,
    )
    assert result.train_ticks == []
    assert result.load_failed is True
    assert result.exhausted is True
    assert result.actual_calendar_days == 0
    assert result.requested_days == FOUNDATION_HISTORY_START_DAYS


@pytest.mark.unit
def test_expand_empty_load_intermediate_rung_load_failed_not_always_exhausted() -> None:
    result = expand_birth_data(
        market_data_service=_EmptyMDS(),
        runtime=_EmptyRuntime(),
        current_step=0,
        expansion_steps=[30, 60, 90],
        synthetic_fallback_fn=None,
    )
    assert result.load_failed is True
    assert result.train_ticks == []
    # Intermediate rung — more ladder remains.
    assert result.exhausted is False
    assert result.step_index == 1


@pytest.mark.unit
def test_maybe_expand_preserves_prior_train_on_empty_load() -> None:
    """Mid-run expansion with 0 bars must never wipe healthy active_train."""
    prior = [
        {
            "timestamp": "2026-07-01T00:00:00+00:00",
            "last": 5000.0,
            "close": 5000.0,
            "regime": "TREND_UP",
        }
        for _ in range(50)
    ]
    host = SimpleNamespace(
        birth_config=SimpleNamespace(max_real_days=56, holdout_pct=0.2),
        market_data_service=_EmptyMDS(),
        runtime=_EmptyRuntime(),
        workspace_root=".",
        _real_data_pct=100.0,
        _data_manifest={},
        _generate_synthetic_ticks=lambda n, start_price=5000.0: [],
    )
    session = object.__new__(StageLoopDataCacheMixin)
    session.host = host
    session.cur_cfg = SimpleNamespace(data_expansion_steps=(90, 180, 365, 730))
    session.news_cfg = SimpleNamespace(primary="none", enable_cache=False, cache_path="")
    session.prefer_real = True
    session.start_price = 5000.0
    session.expansion_step = 0
    session.data_exhausted = False
    session.active_train = list(prior)
    session.active_stage_ticks = list(prior)
    session.stage = SimpleNamespace(value="stage1_trend")
    session._write_progress = MagicMock()

    ok = session._maybe_expand_data()
    assert ok is False
    assert len(session.active_train) == 50
    assert session.data_exhausted is True
    session._write_progress.assert_called()


@pytest.mark.unit
def test_maybe_expand_empty_no_prior_returns_false() -> None:
    host = SimpleNamespace(
        birth_config=SimpleNamespace(max_real_days=56, holdout_pct=0.2),
        market_data_service=_EmptyMDS(),
        runtime=_EmptyRuntime(),
        workspace_root=".",
        _real_data_pct=0.0,
        _data_manifest={},
        _generate_synthetic_ticks=lambda n, start_price=5000.0: [],
    )
    session = object.__new__(StageLoopDataCacheMixin)
    session.host = host
    session.cur_cfg = SimpleNamespace(data_expansion_steps=(56,))
    session.news_cfg = SimpleNamespace(primary="none", enable_cache=False, cache_path="")
    session.prefer_real = True
    session.start_price = 5000.0
    session.expansion_step = 0
    session.data_exhausted = False
    session.active_train = []
    session.active_stage_ticks = []
    session.stage = SimpleNamespace(value="stage1_trend")
    session._write_progress = MagicMock()

    ok = session._maybe_expand_data()
    assert ok is False
    assert session.active_train == []
    assert session.data_exhausted is True
