"""Integration: adaptive recovery continues without manual resume APIs."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.sim_runner import SimRolloutResult


class _FakePpoTrainer:
    def update_from_buffer(self, **_kwargs):
        return SimpleNamespace()

    def create_fresh_birth_policy(self, **_kwargs):
        return SimpleNamespace(predict=lambda *_a, **_k: (0, None))


def _trend_ticks(n: int) -> list[dict]:
    return [{"price": 5000.0 + i * 0.1, "regime": "TREND_UP"} for i in range(n)]


@pytest.mark.unit
def test_adaptive_stall_never_calls_human_resume_apis(
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
            max_adaptation_stuck_escapes=0,
            autonomous_recovery_enabled=True,
            meta_controller_enabled=False,
        ),
        trade_budget_cap=500,
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

    monkeypatch.setattr("lumina_core.birth.stage_loop_rollout.time.time", _fake_time)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.time.time", _fake_time)
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.run_policy_rollout", _rollout)
    monkeypatch.setattr(engine, "_stop_requested", lambda: rollout_calls["n"] >= 18)
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
    assert result.get("status") != "stage_stalled"
    ckpt = json.loads((tmp_path / "state" / "lumina_birth_checkpoint.json").read_text(encoding="utf-8"))
    metrics = ckpt.get("stage_metrics") or {}
    assert len(metrics.get("adaptation_history") or []) >= 1
    assert ckpt.get("phase") != "stage_stalled"
    assert float(metrics.get("autonomous_recovery_rate_pct", 0.0) or 0.0) > 0.0

    bus = engine._birth_bus_client
    assert bus is not None
    assert bus.bus.latest("birth.adaptation.applied") is not None
