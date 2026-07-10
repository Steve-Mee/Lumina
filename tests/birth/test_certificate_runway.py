"""Tests for Minimum Viable Runway (MVR) certificate path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.checkpoint import load_checkpoint_state, save_checkpoint
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    CurriculumStage,
    evaluate_stage_pass,
    ordered_runway_stages,
    stage_pass_trades,
)
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.purged_split import purged_validation_split
from lumina_core.birth.runway import micro_oos_sanity_passed, ticks_for_runway_stage


@pytest.mark.unit
def test_ordered_runway_stages() -> None:
    stages = ordered_runway_stages()
    assert [s.value for s in stages] == [
        "stage5_profit_val",
        "stage6_risk_discipline",
        "stage7_holdout_profile",
    ]


@pytest.mark.unit
def test_purged_validation_split_holdout_untouched() -> None:
    ticks = [
        {"timestamp": f"2024-01-{day:02d}T12:00:00", "last": 100.0}
        for day in range(1, 11)
    ]
    split = purged_validation_split(ticks, validation_pct=0.20)
    assert split.train_core
    assert split.validation
    assert len(split.train_core) + len(split.validation) <= len(ticks)


@pytest.mark.unit
def test_runway_stage5_pass_gate() -> None:
    cfg = BirthCurriculumConfig()
    required = stage_pass_trades(CurriculumStage.STAGE5_PROFIT_VAL, cfg)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE5_PROFIT_VAL,
        trades=required,
        wins=int(required * 0.42),
        hold_signals=40,
        total_signals=100,
        constitution_violations=0,
        target_trades=cfg.stage5_profit_val_trades,
        cfg=cfg,
    )
    assert result.passed is True


@pytest.mark.unit
def test_runway_stage6_sharpe_gate() -> None:
    cfg = BirthCurriculumConfig()
    required = stage_pass_trades(CurriculumStage.STAGE6_RISK_DISCIPLINE, cfg)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE6_RISK_DISCIPLINE,
        trades=required,
        wins=int(required * 0.45),
        hold_signals=40,
        total_signals=100,
        constitution_violations=0,
        target_trades=cfg.stage6_risk_discipline_trades,
        cfg=cfg,
        stage_val_sharpe=0.25,
        stage_val_max_drawdown_pct=10.0,
    )
    assert result.passed is True


@pytest.mark.unit
def test_micro_oos_sanity_requires_baseline_improvement() -> None:
    cfg = BirthCurriculumConfig()
    probe = {"oos_winrate": 0.36}
    ok, _ = micro_oos_sanity_passed(probe, cfg=cfg, baseline_oos_winrate=0.31)
    assert ok is True
    probe_fail = {"oos_winrate": 0.30}
    ok_fail, _ = micro_oos_sanity_passed(probe_fail, cfg=cfg, baseline_oos_winrate=0.31)
    assert ok_fail is False


@pytest.mark.unit
def test_ticks_for_runway_stage_uses_validation_slice() -> None:
    train = [{"timestamp": "2024-01-01", "regime": "TREND_UP"}]
    holdout = [{"timestamp": "2024-02-01", "regime": "NEUTRAL"}]
    val = [{"timestamp": "2024-01-15", "regime": "TREND_DOWN"}]
    s5 = ticks_for_runway_stage(
        CurriculumStage.STAGE5_PROFIT_VAL,
        train_ticks=train,
        holdout_ticks=holdout,
        validation_ticks=val,
    )
    assert s5 == val


@pytest.mark.unit
def test_checkpoint_persists_oos_metrics(tmp_path: Path) -> None:
    oos = {
        "oos_winrate": 0.31,
        "failure_reasons": ["winrate below threshold"],
    }
    save_checkpoint(
        tmp_path,
        cumulative_trades=1000,
        ppo_steps=500,
        training_mode="certified",
        stages_passed=["stage1_trend", "stage2_range", "stage3_mixed"],
        curriculum_stage="stage5_profit_val",
        phase="certificate_failed",
        oos_metrics=oos,
    )
    state = load_checkpoint_state(tmp_path)
    assert state["oos_metrics"]["oos_winrate"] == 0.31
    assert "winrate" in state["oos_metrics"]["failure_reasons"][0]


@pytest.mark.unit
def test_write_birth_progress_preserves_oos_on_attention_like_write(tmp_path: Path) -> None:
    write_birth_progress(
        tmp_path,
        stage="failed",
        phase="certificate_failed",
        message="cert failed",
        progress_pct=100.0,
        oos_metrics={"oos_winrate": 0.31, "failure_reasons": ["wr low"]},
        failure_reasons=["wr low"],
    )
    write_birth_progress(
        tmp_path,
        stage="failed",
        phase="certificate_failed",
        message="attention update",
        progress_pct=100.0,
        needs_attention=True,
        attention_summary="wr low; sharpe low",
    )
    loaded = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert loaded["oos_metrics"]["oos_winrate"] == 0.31
    assert loaded["failure_reasons"] == ["wr low"]
