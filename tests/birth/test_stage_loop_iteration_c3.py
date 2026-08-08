"""C3 god-surface guards for stage_loop_iteration modularization."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_loop_iteration import StageLoopIterationMixin
from lumina_core.birth.stage_loop_iteration_helpers import (
    failure_key_for_stage,
    force_failure_key_for_stage,
    history_unavailable_result,
    stage_winrate,
    wall_budget_elapsed,
)
from lumina_core.birth.stage_loop_iteration_swarm import (
    compute_rollout_chunk_target,
    heartbeat_progress_message,
    swarm_hard_stop_result,
)

_BIRTH = Path(__file__).resolve().parents[2] / "lumina_core" / "birth"
_CORE = _BIRTH / "stage_loop_iteration_core.py"
_FACADE = _BIRTH / "stage_loop_iteration.py"
_STALL = _BIRTH / "stage_loop_iteration_stall.py"
_PASS = _BIRTH / "stage_loop_iteration_pass.py"
_STAG = _BIRTH / "stage_loop_iteration_stagnation.py"
_LOC_LIMIT = 400


def _loc(path: Path) -> int:
    return sum(1 for _ in path.open(encoding="utf-8"))


@pytest.mark.unit
def test_stage_loop_iteration_modules_under_loc_bar() -> None:
    assert _loc(_FACADE) < 40
    assert _loc(_CORE) <= _LOC_LIMIT, f"core LOC {_loc(_CORE)} > {_LOC_LIMIT}"
    assert _loc(_STALL) <= _LOC_LIMIT
    assert _loc(_PASS) <= _LOC_LIMIT
    assert _loc(_STAG) <= _LOC_LIMIT


@pytest.mark.unit
def test_stage_loop_iteration_mixin_mro_includes_branches() -> None:
    names = {c.__name__ for c in StageLoopIterationMixin.__mro__}
    assert "StageLoopIterationStallMixin" in names
    assert "StageLoopIterationPassMixin" in names
    assert "StageLoopIterationStagnationMixin" in names
    assert hasattr(StageLoopIterationMixin, "_run_main_loop")
    assert hasattr(StageLoopIterationMixin, "_iteration_handle_stall_pending")
    assert hasattr(StageLoopIterationMixin, "_iteration_evaluate_and_handle_stage_pass")


@pytest.mark.unit
def test_pure_helpers_stable() -> None:
    assert failure_key_for_stage(CurriculumStage.STAGE1_TREND) == "stage1_winrate"
    assert force_failure_key_for_stage(CurriculumStage.STAGE3_MIXED) == "stage3_constitution"
    assert stage_winrate(5, 10) == 0.5
    assert compute_rollout_chunk_target(stage_trades=0, required=100, rollout_chunk_trades=50) == 50
    assert compute_rollout_chunk_target(stage_trades=90, required=100, rollout_chunk_trades=50) == 10
    assert wall_budget_elapsed(400, 300) is True
    msg = heartbeat_progress_message(
        stage_value="stage1_trend", stage_trades=10, required=100, patterns_mined=3
    )
    assert "stage1_trend" in msg
    r = swarm_hard_stop_result(total_trades=1, ppo_steps=2, training_mode="certified")
    assert r["status"] == "stage_stalled"
    h = history_unavailable_result(total_trades=9, ppo_steps=1)
    assert h["status"] == "history_unavailable"
