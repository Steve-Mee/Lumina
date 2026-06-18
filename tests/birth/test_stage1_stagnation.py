"""Stage 1 winrate/hold stagnation escalation tests."""

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
def test_stage1_winrate_stagnation_escalates_exploration(
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
            certified_max_rollouts_per_stage=30,
            allow_provisional_pass=False,
            checkpoint_interval_sec=3600,
        ),
        trade_budget_cap=500,
    )
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    explore_steps_seen: list[int] = []
    rollout_calls = {"n": 0}

    def _low_winrate_rollout(**kwargs) -> SimRolloutResult:
        rollout_calls["n"] += 1
        explore_steps_seen.append(int(kwargs.get("exploration_steps", 0) or 0))
        if rollout_calls["n"] >= 8:
            raise RuntimeError("bounded_rollouts")
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

    monkeypatch.setattr("lumina_core.birth.engine.run_policy_rollout", _low_winrate_rollout)
    monkeypatch.setattr(
        "lumina_core.birth.engine.mine_winning_patterns",
        lambda **_kwargs: __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set()),
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.expand_birth_data",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no expand")),
    )

    with pytest.raises(RuntimeError, match="bounded_rollouts"):
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
            trade_budget_cap=500,
            prefer_real=True,
            start_price=5000.0,
        )

    assert rollout_calls["n"] >= 4
    assert max(explore_steps_seen) > min(explore_steps_seen)


@pytest.mark.unit
def test_stage1_wall_stagnation_aborts_before_max_rollouts(
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
        ),
        trade_budget_cap=500,
    )
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    tick = {"value": 1_000_000.0}

    def _fake_time() -> float:
        return tick["value"]

    def _advance_time(_: float) -> None:
        tick["value"] += 400.0

    monkeypatch.setattr("lumina_core.birth.engine.time.time", _fake_time)
    monkeypatch.setattr(
        "lumina_core.birth.engine.run_policy_rollout",
        lambda **_kwargs: (
            _advance_time(0),
            SimRolloutResult(
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
            ),
        )[1],
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.mine_winning_patterns",
        lambda **_kwargs: __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set()),
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.expand_birth_data",
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
    assert result.get("status") == "stage_stalled"
    assert result.get("failure_reason") == "stage1_winrate"

    ckpt_path = tmp_path / "state" / "lumina_birth_checkpoint.json"
    assert ckpt_path.is_file()
    ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
    assert ckpt.get("phase") == "stage_stalled"
    metrics = ckpt.get("stage_metrics") or {}
    assert int(metrics.get("stage_trades", 0) or 0) >= 100
