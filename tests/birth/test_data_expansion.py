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
    same_tape_covers_rung,
)
from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.data_pipeline_types import train_hash
from lumina_core.birth.stage_loop_data_cache import StageLoopDataCacheMixin
from lumina_core.birth.stage_loop_rollout_tail import StageLoopRolloutTailMixin


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
    assert clamp_expansion_steps([90, 180, 365, 730], max_real_days=365) == [365]
    assert default_expansion_steps() == [365]


@pytest.mark.unit
def test_clamp_expansion_steps_to_max_real_days() -> None:
    """A ceiling below 365 cannot shrink the Awakening-capacity sport."""
    clamped = clamp_expansion_steps([90, 180, 365, 730], max_real_days=112)
    assert clamped == [365]
    assert max(clamped) == FOUNDATION_HISTORY_START_DAYS


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
    """max_real_days=56 is not a live Birth ladder — floor is the 365-day sport."""
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


@pytest.mark.unit
def test_same_tape_covers_loaded_sport_not_a_longer_rung() -> None:
    assert same_tape_covers_rung(loaded_days=366, requested_days=365, has_train_ticks=True) is True
    assert same_tape_covers_rung(loaded_days=90, requested_days=180, has_train_ticks=True) is False
    assert same_tape_covers_rung(loaded_days=366, requested_days=365, has_train_ticks=False) is False


@pytest.mark.unit
def test_maybe_expand_does_not_refetch_when_tape_already_covers_rung(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(**_kwargs: Any) -> Any:
        raise AssertionError("Fabric refetch on the same tape")

    monkeypatch.setattr(
        "lumina_core.birth.stage_loop_data_cache._expand_birth_data",
        _boom,
    )
    prior = [{"timestamp": "2026-01-01T00:00:00+00:00", "last": 5000.0, "close": 5000.0}]
    host = SimpleNamespace(
        birth_config=SimpleNamespace(max_real_days=365, holdout_pct=0.2),
        _data_manifest={"actual_calendar_days": 366, "days_loaded": 366},
    )
    session = object.__new__(StageLoopDataCacheMixin)
    session.host = host
    session.cur_cfg = SimpleNamespace(data_expansion_steps=(365,))
    session.expansion_step = 0
    session.data_exhausted = False
    session._same_tape_locked = False
    session._foundation_eval_only = False
    session.data_days_loaded = 366
    session.active_train = list(prior)
    session.stage = SimpleNamespace(value="stage4_viable_plant")
    session._write_progress = MagicMock()

    ok = session._maybe_expand_data()
    assert ok is False
    assert session._same_tape_locked is True
    assert session.data_exhausted is False
    assert session.active_train == prior
    message = session._write_progress.call_args.kwargs["message"]
    assert "Same data line" in message
    assert "No second download" in message


@pytest.mark.unit
def test_epoch_cap_on_same_tape_does_not_freeze() -> None:
    tape = [
        {"timestamp": "2026-01-01T00:00:00+00:00", "last": 1.0},
        {"timestamp": "2026-10-01T00:00:00+00:00", "last": 1.0},
    ]
    session = object.__new__(StageLoopRolloutTailMixin)
    session.stage = CurriculumStage.STAGE4_VIABLE_PLANT
    session._foundation_eval_only = False
    session._foundation_epoch_hash = train_hash(tape)
    session._foundation_epoch_count = 2
    session.active_train = tape
    session.data_exhausted = False
    session._same_tape_locked = False
    session._maybe_expand_data = lambda: setattr(session, "_same_tape_locked", True) or False
    session._write_progress = MagicMock()

    session._note_foundation_epoch_and_maybe_expand()
    assert session.data_exhausted is False
    assert session._same_tape_locked is True
    assert session._foundation_epoch_count == 3
