"""Phoenix loop tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.phoenix_loop import (
    PHOENIX_CYCLE_REASON,
    PhoenixLoopState,
    begin_phoenix_cycle,
    build_phoenix_checkpoint_patch,
    can_start_phoenix,
)


@pytest.mark.unit
def test_phoenix_cycle_reason() -> None:
    assert PHOENIX_CYCLE_REASON == "phoenix_cycle"


@pytest.mark.unit
def test_can_start_phoenix_respects_max() -> None:
    cfg = BirthCurriculumConfig(phoenix_loop_enabled=True, phoenix_max_cycles=2)
    state = PhoenixLoopState(phoenix_count=2)
    assert can_start_phoenix(state, cfg=cfg) is False


@pytest.mark.unit
def test_build_checkpoint_patch_expand() -> None:
    from lumina_core.birth.phoenix_loop import PhoenixNoveltyAction

    patch = build_phoenix_checkpoint_patch(
        novelty=PhoenixNoveltyAction.EXPAND_DATA,
        curriculum_stage="stage1_trend",
        cfg=BirthCurriculumConfig(),
    )
    assert patch["phase"] == "phoenix_cycle"
    assert patch["stage_metrics"]["pending_data_expand"] is True


@pytest.mark.unit
def test_begin_phoenix_cycle_increments() -> None:
    from lumina_core.birth.phoenix_loop import PhoenixNoveltyAction

    state = PhoenixLoopState()
    begin_phoenix_cycle(state, novelty=PhoenixNoveltyAction.SOFT_GATE, stall_reason="test")
    assert state.phoenix_count == 1
    assert state.last_action == "soft_gate"