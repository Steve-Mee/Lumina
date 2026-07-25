"""Fail-closed curriculum graduation integrity (stage pass receipts)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.checkpoint import save_checkpoint
from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.progress import read_birth_progress, write_birth_progress
from lumina_core.birth.stage_pass_receipt import (
    StagePassReceipt,
    audit_curriculum_integrity,
    receipt_from_stage_result,
    verify_stage_pass_receipt,
)
from scripts.birth_stage_forensics import build_report


def _stage1_cfg() -> BirthCurriculumConfig:
    return BirthCurriculumConfig(
        stage1_trend_trades=100,
        allow_provisional_pass=False,
    )


def _valid_stage1_receipt(*, trades: int = 100, wins: int = 50) -> StagePassReceipt:
    cfg = _stage1_cfg()
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=trades,
        wins=wins,
        hold_signals=0,
        total_signals=trades,
        constitution_violations=0,
        target_trades=100,
        cfg=cfg,
        allow_provisional=False,
    )
    assert result.passed
    return receipt_from_stage_result(CurriculumStage.STAGE1_TREND, result, cfg=cfg)


@pytest.mark.unit
def test_missing_receipt_fails_verify() -> None:
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE1_TREND,
        None,
        cfg=_stage1_cfg(),
        training_mode="certified",
    )
    assert ok is False
    assert reason == "missing_receipt"


@pytest.mark.unit
def test_valid_receipt_allows_verify() -> None:
    receipt = _valid_stage1_receipt(trades=100, wins=50)
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE1_TREND,
        receipt,
        cfg=_stage1_cfg(),
        training_mode="certified",
    )
    assert ok is True
    assert reason == "ok"


@pytest.mark.unit
def test_low_winrate_receipt_fails_re_eval() -> None:
    receipt = StagePassReceipt(
        stage="stage1_trend",
        trades=100,
        wins=24,
        winrate=0.24,
        required_trades=100,
        pass_criteria_id="stage1_trend",
        provisional=False,
        passed_at="2026-01-01T00:00:00+00:00",
        engine_version="BRO-v2",
    )
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE1_TREND,
        receipt,
        cfg=_stage1_cfg(),
        training_mode="certified",
    )
    assert ok is False
    assert reason.startswith("stage1_winrate_below_gate")


@pytest.mark.unit
def test_audit_truncates_stages_without_receipts() -> None:
    audit = audit_curriculum_integrity(
        stages_passed=["stage1_trend"],
        stage_pass_receipts=[],
        cfg=_stage1_cfg(),
        training_mode="certified",
    )
    assert audit.ok is False
    assert audit.stages_passed == []
    assert audit.reset_applied is True
    assert any("missing_receipt" in r for r in audit.invalid_reasons)


@pytest.mark.unit
def test_audit_keeps_valid_prefix() -> None:
    receipt = _valid_stage1_receipt()
    audit = audit_curriculum_integrity(
        stages_passed=["stage1_trend"],
        stage_pass_receipts=[receipt],
        cfg=_stage1_cfg(),
        training_mode="certified",
    )
    assert audit.ok is True
    assert audit.stages_passed == ["stage1_trend"]


@pytest.mark.unit
def test_stage_stalled_progress_does_not_preserve_stale_stages_passed(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True)
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="curriculum_learning",
        message="running",
        progress_pct=30.0,
        stages_passed=["stage1_trend"],
    )
    write_birth_progress(
        tmp_path,
        stage="stage_stalled",
        phase="stage_stalled",
        message="stalled",
        progress_pct=35.0,
        stages_passed=[],
    )
    payload = read_birth_progress(tmp_path)
    assert payload.get("stages_passed") == []


@pytest.mark.unit
def test_engine_invalidates_blind_skip_on_resume(tmp_path: Path) -> None:
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(curriculum=_stage1_cfg(), trade_budget_cap=500)
    engine._stages_passed = ["stage1_trend"]
    engine._stage_pass_receipts = []

    ok = engine._verify_stage_pass_receipt_for_skip(
        CurriculumStage.STAGE1_TREND,
        training_mode="certified",
    )
    assert ok is False
    assert engine._stages_passed == []


@pytest.mark.unit
def test_engine_valid_receipt_allows_skip(tmp_path: Path) -> None:
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(curriculum=_stage1_cfg(), trade_budget_cap=500)
    engine._stages_passed = ["stage1_trend"]
    engine._stage_pass_receipts = [_valid_stage1_receipt()]

    ok = engine._verify_stage_pass_receipt_for_skip(
        CurriculumStage.STAGE1_TREND,
        training_mode="certified",
    )
    assert ok is True
    assert engine._stages_passed == ["stage1_trend"]


@pytest.mark.unit
def test_metrics_not_restored_when_curriculum_stage_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lumina_core.birth.sim_runner import SimRolloutResult

    save_checkpoint(
        tmp_path,
        cumulative_trades=50,
        ppo_steps=100,
        training_mode="certified",
        stages_passed=[],
        curriculum_stage="stage2_range",
        stage_metrics={
            "stage_trades": 99,
            "stage_wins": 40,
            "curriculum_stage_scope": "stage2_range",
        },
        phase="curriculum_learning",
    )

    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(update_from_buffer=lambda **_k: SimpleNamespace()),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(
            stage1_trend_trades=200,
            rollout_chunk_trades=20,
            checkpoint_interval_sec=3600,
            meta_controller_enabled=False,
        ),
        trade_budget_cap=500,
    )
    for i in range(80):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i]}})

    captured: dict[str, int] = {}

    def _rollout(**kwargs: object) -> SimRolloutResult:
        captured["target"] = int(kwargs.get("target_trades", 0) or 0)  # type: ignore[arg-type]
        raise RuntimeError("stop_after_first_rollout")

    monkeypatch.setattr("lumina_core.birth.stage_training_loop.run_policy_rollout", _rollout)
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_k: SimpleNamespace(
            patterns=[],
            wins=0,
            scanned=0,
            regimes_seen=set(),
            stop_pct=0.0012,
            target_pct=0.0020,
            reason="test_stub",
        ),
    )
    ticks = [{"last": 5000.0, "regime": "TREND_UP"} for _ in range(200)]
    with pytest.raises(RuntimeError, match="stop_after_first_rollout"):
        engine._run_stage_research_loop(
            stage=CurriculumStage.STAGE1_TREND,
            stage_index=0,
            stage_ticks=ticks,
            train_ticks=ticks,
            holdout_ticks=ticks[:40],
            target=200,
            stage_progress_pct=25.0,
            training_mode="certified",
            ppo_steps_per_update=1000,
            polish_ppo_timesteps=1000,
            trade_budget_cap=500,
            prefer_real=True,
            start_price=5000.0,
        )

    progress = read_birth_progress(tmp_path)
    assert int(progress.get("stage_trades", 0) or 0) < 99


@pytest.mark.unit
def test_forensics_detects_stage_pass_integrity_mismatch(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True)
    (tmp_path / "config.yaml").write_text(
        "birth_v2:\n  trade_budget_cap: 10000\n  curriculum:\n    stage1_trend_trades: 100\n",
        encoding="utf-8",
    )
    (tmp_path / "state" / "lumina_birth_checkpoint.json").write_text(
        json.dumps(
            {
                "training_mode": "certified",
                "stages_passed": ["stage1_trend"],
                "stage_pass_receipts": [],
                "curriculum_stage": "stage2_range",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "curriculum_stage": "stage2_range",
                "stages_passed": ["stage1_trend"],
                "stage_trades": 100,
                "stage_wins": 28,
                "stage_winrate": 0.28,
            }
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path)
    audit = report["stage_pass_audit"]
    assert audit["integrity_mismatch"] is True
    assert audit["integrity_ok"] is False
    assert "stages_passed_without_receipts" in str(audit.get("invalid_reasons"))
