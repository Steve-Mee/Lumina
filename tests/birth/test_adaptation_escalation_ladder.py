"""Escalation ladder: adaptive mode avoids terminal stall until budget/data exhausted."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.checkpoint import save_checkpoint
from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.sim_runner import SimRolloutResult


class _FakePpoTrainer:
    def update_from_buffer(self, **_kwargs):
        return SimpleNamespace()


def _trend_ticks(n: int) -> list[dict]:
    return [{"price": 5000.0 + i * 0.1, "regime": "TREND_UP"} for i in range(n)]


def _ladder_curriculum(**kwargs: object) -> BirthCurriculumConfig:
    """Isolate adaptation ladder from phoenix/plateau autonomous recovery."""
    base = {
        "autonomous_recovery_enabled": False,
        "phoenix_loop_enabled": False,
        "plateau_detection_enabled": False,
        "stall_remediation_enabled": False,
    }
    base.update(kwargs)
    return BirthCurriculumConfig(**base)


@pytest.mark.unit
def test_adaptive_ladder_advances_tier_without_terminal_stall(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=_ladder_curriculum(
            stage1_trend_trades=100,
            rollout_chunk_trades=20,
            stage1_winrate_stagnation_rollouts=2,
            certified_stage_stall_wall_sec=300,
            certified_max_rollouts_per_stage=500,
            allow_provisional_pass=False,
            checkpoint_interval_sec=3600,
            wall_behavior="adaptive",
            max_stage_retries=1,
            max_adaptation_tiers=4,
            auto_expand_on_adaptation=False,
            exploration_chunk_size=8,
            meta_controller_enabled=False,
        ),
        trade_budget_cap=5000,
    )
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    tick = {"value": 1_000_000.0}
    rollout_calls = {"n": 0}

    def _fake_time() -> float:
        tick["value"] += 400.0
        return tick["value"]

    def _rollout(**_kwargs) -> SimRolloutResult:
        rollout_calls["n"] += 1
        return SimRolloutResult(
            trades=15,
            wins=2,
            hold_signals=92,
            total_signals=100,
            total_pnl=0.2,
            trajectories=[{"reward": 0.2, "observation": {"vector": [5000.0]}} for _ in range(20)],
            pnl_series=[0.2],
            constitution_violations=0,
            regimes_seen={"TREND_UP"},
            partial_complete=True,
            rollout_steps=200,
        )

    def _stop_after_budgeted_rollouts() -> bool:
        return rollout_calls["n"] >= 25

    monkeypatch.setattr("lumina_core.birth.stage_rollout_executor.time.time", _fake_time)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.time.time", _fake_time)
    monkeypatch.setattr("lumina_core.birth.sim_runner.run_policy_rollout", _rollout)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.run_policy_rollout", _rollout)
    monkeypatch.setattr(engine, "_stop_requested", _stop_after_budgeted_rollouts)
    monkeypatch.setattr(
        "lumina_core.birth.pattern_miner.mine_winning_patterns",
        lambda **_kwargs: __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set()),
    )
    monkeypatch.setattr(
        "lumina_core.birth.data_expansion.expand_birth_data",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no expand")),
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_rollout_executor.expand_birth_data",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no expand")),
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.expand_birth_data",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no expand")),
    )

    result = engine._run_stage_research_loop(
        stage=CurriculumStage.STAGE1_TREND,
        stage_index=0,
        stage_ticks=_trend_ticks(600),
        train_ticks=_trend_ticks(600),
        holdout_ticks=_trend_ticks(120),
        target=100,
        stage_progress_pct=25.0,
        training_mode="certified",
        ppo_steps_per_update=1000,
        polish_ppo_timesteps=1000,
        trade_budget_cap=5000,
        prefer_real=True,
        start_price=5000.0,
    )

    assert result is not None
    assert result.get("status") == "paused"
    ckpt = json.loads((tmp_path / "state" / "lumina_birth_checkpoint.json").read_text(encoding="utf-8"))
    metrics = ckpt.get("stage_metrics") or {}
    history = metrics.get("adaptation_history") or []
    assert len(history) >= 1
    assert ckpt.get("phase") != "stage_stalled"
    assert int(metrics.get("adaptation_tier", 0) or 0) >= 0


@pytest.mark.unit
def test_strict_mode_still_terminal_stalls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=_ladder_curriculum(
            stage1_trend_trades=100,
            rollout_chunk_trades=20,
            stage1_winrate_stagnation_rollouts=2,
            certified_stage_stall_wall_sec=300,
            certified_max_rollouts_per_stage=500,
            allow_provisional_pass=False,
            checkpoint_interval_sec=3600,
            wall_behavior="strict",
        ),
        trade_budget_cap=500,
    )
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    tick = {"value": 1_000_000.0}

    def _fake_time() -> float:
        tick["value"] += 400.0
        return tick["value"]

    monkeypatch.setattr("lumina_core.birth.stage_rollout_executor.time.time", _fake_time)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.time.time", _fake_time)
    def _fake_rollout(**_kwargs) -> SimRolloutResult:
        return SimRolloutResult(
            trades=15,
            wins=2,
            hold_signals=92,
            total_signals=100,
            total_pnl=0.2,
            trajectories=[{"reward": 0.2, "observation": {"vector": [5000.0]}} for _ in range(20)],
            pnl_series=[0.2],
            constitution_violations=0,
            regimes_seen={"TREND_UP"},
            partial_complete=True,
            rollout_steps=200,
        )

    monkeypatch.setattr("lumina_core.birth.sim_runner.run_policy_rollout", _fake_rollout)
    monkeypatch.setattr("lumina_core.birth.stage_rollout_executor.run_policy_rollout", _fake_rollout)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.run_policy_rollout", _fake_rollout)

    def _fake_mine(**_kwargs):
        return __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set())

    monkeypatch.setattr("lumina_core.birth.pattern_miner.mine_winning_patterns", _fake_mine)
    monkeypatch.setattr("lumina_core.birth.stage_rollout_executor.mine_winning_patterns", _fake_mine)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.mine_winning_patterns", _fake_mine)

    def _no_expand(**_kwargs):
        raise AssertionError("no expand")

    monkeypatch.setattr("lumina_core.birth.data_expansion.expand_birth_data", _no_expand)
    monkeypatch.setattr("lumina_core.birth.stage_rollout_executor.expand_birth_data", _no_expand)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.expand_birth_data", _no_expand)

    result = engine._run_stage_research_loop(
        stage=CurriculumStage.STAGE1_TREND,
        stage_index=0,
        stage_ticks=_trend_ticks(600),
        train_ticks=_trend_ticks(600),
        holdout_ticks=_trend_ticks(120),
        target=100,
        stage_progress_pct=25.0,
        training_mode="certified",
        ppo_steps_per_update=1000,
        polish_ppo_timesteps=1000,
        trade_budget_cap=500,
        prefer_real=True,
        start_price=5000.0,
    )

    assert result.get("status") == "stage_stalled"


@pytest.mark.unit
def test_tier_three_triggers_data_expand_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expand_calls = {"n": 0}

    def _expand(**_kwargs):
        expand_calls["n"] += 1
        from lumina_core.birth.data_expansion import DataExpansionResult
        from lumina_core.birth.purged_split import PurgedSplit

        train = _trend_ticks(200)
        holdout = _trend_ticks(40)
        split = PurgedSplit(train=train, holdout=holdout, train_days=1, holdout_days=1)
        return DataExpansionResult(
            train_ticks=train,
            holdout_ticks=holdout,
            all_ticks=train + holdout,
            split=split,
            days_back=180,
            step_index=1,
            real_data_pct=1.0,
            exhausted=False,
        )

    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=_ladder_curriculum(
            stage1_trend_trades=100,
            rollout_chunk_trades=20,
            stage1_winrate_stagnation_rollouts=2,
            certified_stage_stall_wall_sec=300,
            certified_max_rollouts_per_stage=500,
            allow_provisional_pass=False,
            checkpoint_interval_sec=3600,
            wall_behavior="adaptive",
            max_stage_retries=1,
            max_adaptation_tiers=4,
            auto_expand_on_adaptation=True,
            meta_controller_enabled=False,
        ),
        trade_budget_cap=5000,
    )
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    save_checkpoint(
        tmp_path,
        cumulative_trades=200,
        ppo_steps=0,
        training_mode="certified",
        stages_passed=[],
        curriculum_stage="stage1_trend",
        phase="curriculum_learning",
        stage_metrics={
            "stage_trades": 120,
            "stage_wins": 30,
            "retries_this_stage": 0,
            "adaptation_tier": 2,
            "adaptation_history": [],
        },
    )

    tick = {"value": 1_000_000.0}
    rollout_calls = {"n": 0}

    def _fake_time() -> float:
        tick["value"] += 400.0
        return tick["value"]

    def _rollout(**_kwargs) -> SimRolloutResult:
        rollout_calls["n"] += 1
        return SimRolloutResult(
            trades=15,
            wins=2,
            hold_signals=92,
            total_signals=100,
            total_pnl=0.2,
            trajectories=[{"reward": 0.2, "observation": {"vector": [5000.0]}} for _ in range(20)],
            pnl_series=[0.2],
            constitution_violations=0,
            regimes_seen={"TREND_UP"},
            partial_complete=True,
            rollout_steps=200,
        )

    monkeypatch.setattr("lumina_core.birth.stage_rollout_executor.time.time", _fake_time)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.run_policy_rollout", _rollout)
    monkeypatch.setattr("lumina_core.birth.stage_rollout_executor.expand_birth_data", _expand)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.expand_birth_data", _expand)
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_kwargs: __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(patterns=[{"reward": 1.0}], wins=1, scanned=1, regimes_seen=set()),
    )
    monkeypatch.setattr(engine, "_stop_requested", lambda: rollout_calls["n"] >= 8)

    engine._run_stage_research_loop(
        stage=CurriculumStage.STAGE1_TREND,
        stage_index=0,
        stage_ticks=_trend_ticks(600),
        train_ticks=_trend_ticks(600),
        holdout_ticks=_trend_ticks(120),
        target=100,
        stage_progress_pct=25.0,
        training_mode="certified",
        ppo_steps_per_update=1000,
        polish_ppo_timesteps=1000,
        trade_budget_cap=5000,
        prefer_real=True,
        start_price=5000.0,
    )

    assert expand_calls["n"] >= 1
