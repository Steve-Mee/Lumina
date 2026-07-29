"""Post volume gate chunk_target must not collapse to 1."""

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
    def create_fresh_birth_policy(self, *, allow_load_existing: bool = True):
        _ = allow_load_existing
        return {"policy": "fresh"}

    def update_from_buffer(self, **kwargs):
        _ = kwargs
        return {"policy": "updated"}


def _trend_ticks(n: int = 600) -> list[dict]:
    ticks: list[dict] = []
    price = 5000.0
    for i in range(n):
        price += 0.2
        ticks.append(
            {
                "timestamp": f"2026-01-01T{i:04d}:00Z",
                "last": price,
                "bid": price - 0.125,
                "ask": price + 0.125,
                "volume": 100,
                "source": "real_historical",
                "regime": "TREND_UP" if i % 2 == 0 else "TREND_DOWN",
            }
        )
    return ticks


@pytest.mark.unit
def test_post_gate_chunk_target_uses_rollout_chunk_not_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User scenario: 386 trades past required=200 must not get chunk_target=1."""
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    rollout_chunk = 20
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(
            stage1_trend_trades=2000,
            rollout_chunk_trades=rollout_chunk,
            exploration_chunk_size=8,
            certified_max_rollouts_per_stage=5,
            checkpoint_interval_sec=3600,
        ),
        trade_budget_cap=5000,
    )
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    save_checkpoint(
        tmp_path,
        cumulative_trades=386,
        ppo_steps=1000,
        training_mode="certified",
        stages_passed=[],
        curriculum_stage="stage1_trend",
        stage_metrics={
            "stage_trades": 386,
            "stage_wins": 117,
            "stage_hold_signals": 0,
            "stage_total_signals": 386,
            "patterns_mined": 50,
        },
        phase="curriculum_learning",
    )

    captured: list[int] = []

    def _capture_rollout(**kwargs) -> SimRolloutResult:
        captured.append(int(kwargs.get("target_trades", 0) or 0))
        raise RuntimeError("bounded_after_first_rollout")

    monkeypatch.setattr("lumina_core.birth.stage_training_loop.run_policy_rollout", _capture_rollout)
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_kwargs: __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set()),
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.expand_birth_data",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no expand")),
    )

    with pytest.raises(RuntimeError, match="bounded_after_first_rollout"):
        engine._run_stage_research_loop(
            stage=CurriculumStage.STAGE1_TREND,
            stage_index=0,
            stage_ticks=_trend_ticks(600),
            train_ticks=_trend_ticks(600),
            holdout_ticks=_trend_ticks(120),
            target=2000,
            stage_progress_pct=25.0,
            training_mode="certified",
            ppo_steps_per_update=1000,
            polish_ppo_timesteps=1000,
            trade_budget_cap=5000,
            prefer_real=True,
            start_price=5000.0,
        )

    assert len(captured) >= 1
    assert captured[0] == rollout_chunk
    assert captured[0] > 1


@pytest.mark.unit
def test_adaptive_recovery_does_not_write_stage_stalled_progress(
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
        curriculum=BirthCurriculumConfig(
            stage1_trend_trades=100,
            rollout_chunk_trades=20,
            stage1_winrate_stagnation_rollouts=2,
            certified_stage_stall_wall_sec=300,
            certified_max_rollouts_per_stage=500,
            allow_provisional_pass=False,
            checkpoint_interval_sec=3600,
            wall_behavior="adaptive",
            max_stage_retries=1,
            exploration_chunk_size=8,
            auto_expand_on_adaptation=False,
        ),
        trade_budget_cap=500,
    )
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    tick = {"value": 1_000_000.0}
    stall_writes: list[str] = []
    original_write = __import__(
        "lumina_core.birth.progress", fromlist=["write_birth_progress"]
    ).write_birth_progress

    def _track_write(*args, **kwargs):
        phase = str(kwargs.get("phase", "") or "")
        if phase == "stage_stalled":
            stall_writes.append(phase)
        return original_write(*args, **kwargs)

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

    monkeypatch.setattr("lumina_core.birth.stage_training_loop.time.time", _fake_time)
    monkeypatch.setattr("lumina_core.birth.progress.write_birth_progress", _track_write)
    monkeypatch.setattr("lumina_core.birth.birth_phase_orchestrator.write_birth_progress", _track_write)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.run_policy_rollout", _rollout)
    monkeypatch.setattr(engine, "_stop_requested", lambda: rollout_calls["n"] >= 20)
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_kwargs: __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set()),
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
        trade_budget_cap=500,
        prefer_real=True,
        start_price=5000.0,
    )

    assert result is not None
    assert result.get("status") == "paused"
    ckpt = json.loads((tmp_path / "state" / "lumina_birth_checkpoint.json").read_text(encoding="utf-8"))
    assert len((ckpt.get("stage_metrics") or {}).get("adaptation_history") or []) >= 1
    assert len(stall_writes) == 0
