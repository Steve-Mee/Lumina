"""Regression tests for constitution graduation gate alignment (never-stop birth)."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    CurriculumStage,
    constitution_blocks_graduation,
    evaluate_stage_pass,
    graduation_requires_clean_constitution,
)
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.graduation_result import GraduationResult
from lumina_core.birth.stage_scorecard import compute_stage_blocker
from lumina_core.birth.wall_trigger_engine import (
    constitution_blocks_adaptation,
    evaluate_certified_stall,
)
from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment


class _FakePpoTrainer:
    def save_final_birth_policy(self, path: str) -> None:
        return None


@pytest.mark.unit
def test_graduation_requires_clean_constitution_stages() -> None:
    assert graduation_requires_clean_constitution(CurriculumStage.STAGE1_TREND)
    assert graduation_requires_clean_constitution(CurriculumStage.STAGE2_RANGE)
    assert graduation_requires_clean_constitution(CurriculumStage.STAGE3_MIXED)
    assert graduation_requires_clean_constitution(CurriculumStage.STAGE4_VIABLE_PLANT)
    assert graduation_requires_clean_constitution(CurriculumStage.STAGE5_PROBE_HANDOFF)
    assert not graduation_requires_clean_constitution(CurriculumStage.STAGE4_POLISH)


@pytest.mark.unit
def test_stage2_pass_blocked_when_constitution_violations_present() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000, stage2_edgescore_enabled=False)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=300,
        wins=150,
        hold_signals=500,
        total_signals=1000,
        range_hold_signals=100,
        range_total_signals=500,
        range_flat_bars=250,
        range_round_trips=30,
        constitution_violations=860,
        target_trades=3000,
        cfg=cfg,
    )
    assert result.passed is False
    assert "constitution" in result.message


@pytest.mark.unit
def test_stage1_pass_blocked_when_constitution_violations_present() -> None:
    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=250,
        wins=120,
        hold_signals=400,
        total_signals=1000,
        constitution_violations=12,
        target_trades=2000,
        cfg=cfg,
    )
    assert result.passed is False
    assert constitution_blocks_graduation(
        stage=CurriculumStage.STAGE1_TREND,
        constitution_violations=12,
    )


@pytest.mark.unit
def test_compute_stage_blocker_stage2_flags_constitution_violations() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000, stage2_edgescore_enabled=False)
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE2_RANGE,
        stage_trades=300,
        stage_wins=150,
        hold_ratio=0.5,
        required=300,
        constitution_violations=5,
        range_flat_ratio=0.55,
        range_round_trips=30,
        range_total_signals=500,
        cfg=cfg,
    )
    assert metric == "constitution_violations"
    assert value == 5.0
    assert "violations 5" in (reason or "")


@pytest.mark.unit
def test_commit_stage_graduation_returns_recovery_not_runtime_error(tmp_path) -> None:
    engine = BirthPhaseEngineV2(
        ppo_trainer=_FakePpoTrainer(),
        workspace_root=tmp_path,
    )
    engine._constitution_guard.violations = 7

    result = engine._commit_stage_graduation(
        CurriculumStage.STAGE2_RANGE,
        training_mode="certified",
        curriculum_stage="stage2_range",
        policy_path=str(tmp_path / "policy.zip"),
        phase="test",
    )

    assert isinstance(result, GraduationResult)
    assert result.ok is False
    assert "constitution_violations_pending" in result.reason
    assert "stage2_range" not in engine._stages_passed


@pytest.mark.unit
def test_commit_stage_graduation_succeeds_when_constitution_clean(tmp_path) -> None:
    engine = BirthPhaseEngineV2(
        ppo_trainer=_FakePpoTrainer(),
        workspace_root=tmp_path,
    )
    engine._constitution_guard.violations = 0

    result = engine._commit_stage_graduation(
        CurriculumStage.STAGE2_RANGE,
        training_mode="certified",
        curriculum_stage="stage2_range",
        policy_path=str(tmp_path / "policy.zip"),
        phase="test",
    )

    assert result.ok is True
    assert "stage2_range" in engine._stages_passed


@pytest.mark.unit
def test_birth_gym_clips_stop_pct_to_one_percent_for_constitution() -> None:
    guard = BirthConstitutionGuard()
    data = [{"close": 5000.0, "last": 5000.0, "bid": 4999.875, "ask": 5000.125}]
    env = RLTradingEnvironment(
        engine=SimpleNamespace(config=SimpleNamespace(instrument="MES")),
        simulator_data=data,
        config=RLConfig(trade_mode="birth"),
    )
    env.set_birth_context(workspace_root=".", constitution_guard=guard)
    env.reset()
    # Policy requests 1.5% stop; birth mode must clip to 1% so guard allows entry.
    action = np.array([1.0, 0.5, 0.015, 0.02], dtype=np.float32)
    _obs, _reward, _terminated, _truncated, info = env.step(action)
    assert not info.get("blocked_by_birth_constitution")
    assert guard.violations == 0


@pytest.mark.unit
def test_certified_stall_triggers_immediately_on_constitution_blocker() -> None:
    cur = BirthCurriculumConfig(stage2_range_trades=3000)
    result = evaluate_certified_stall(
        stage=CurriculumStage.STAGE2_RANGE,
        stage_trades=300,
        stage_wins=150,
        required=300,
        hold_ratio=0.5,
        constitution_violations=3,
        range_flat_ratio=0.55,
        range_round_trips=30,
        range_total_signals=500,
        elapsed_stage_sec=10.0,
        winrate_stagnation_count=0,
        hold_stagnation_count=0,
        wall_budget_exhausted=False,
        allow_provisional=False,
        failure_key="stage2_range",
        force=False,
        cfg=cur,
    )
    assert result.triggered is True
    assert result.trigger_type == "constitution_stall"
    assert result.constitution_blocked is True


@pytest.mark.unit
def test_constitution_blocks_adaptation_for_stage1_and_stage2() -> None:
    assert constitution_blocks_adaptation(
        stage=CurriculumStage.STAGE1_TREND,
        constitution_violations=1,
    )
    assert constitution_blocks_adaptation(
        stage=CurriculumStage.STAGE2_RANGE,
        constitution_violations=1,
    )
    assert constitution_blocks_adaptation(
        stage=CurriculumStage.STAGE3_MIXED,
        constitution_violations=1,
    )
    assert not constitution_blocks_adaptation(
        stage=CurriculumStage.STAGE4_POLISH,
        constitution_violations=5,
    )
