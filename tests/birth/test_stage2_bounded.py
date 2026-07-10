"""Stage 2 bounded convergence tests (wall budget + hold stagnation explore)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.sim_runner import SimRolloutResult


class _FakePpoTrainer:
    def __init__(self) -> None:
        self._active_policy: dict[str, str] = {"policy": "fresh"}

    def create_fresh_birth_policy(self, *, allow_load_existing: bool = True):
        _ = allow_load_existing
        return self._active_policy

    def update_from_buffer(self, **kwargs):
        _ = kwargs
        return {"policy": "updated"}

    def final_birth_polish(self, _buffer) -> None:
        return None

    def save_final_birth_policy(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"policy")


def _range_ticks(n: int = 600) -> list[dict]:
    ticks: list[dict] = []
    price = 5000.0
    for i in range(n):
        price += 0.1
        ticks.append(
            {
                "timestamp": f"2026-01-01T{i:04d}:00Z",
                "last": price,
                "bid": price - 0.125,
                "ask": price + 0.125,
                "volume": 100,
                "source": "real_historical",
                "regime": "RANGE",
            }
        )
    return ticks


@pytest.mark.unit
def test_stage2_hold_stagnation_increases_exploration(
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
            stage2_range_trades=50,
            rollout_chunk_trades=10,
            exploration_steps=1000,
            stage2_hold_stagnation_rollouts=2,
            max_rollouts_per_stage=20,
            gen0_provisional_min_trades=5,
            oracle_patterns_per_stage=50,
            checkpoint_interval_sec=3600,
        ),
        trade_budget_cap=500,
    )
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    explore_steps_seen: list[int] = []
    rollout_calls = {"n": 0}

    def _stagnant_rollout(**kwargs) -> SimRolloutResult:
        rollout_calls["n"] += 1
        explore_steps_seen.append(int(kwargs.get("exploration_steps", 0) or 0))
        if rollout_calls["n"] >= 6:
            raise RuntimeError("bounded_rollouts")
        return SimRolloutResult(
            trades=10,
            wins=4,
            hold_signals=95,
            total_signals=100,
            total_pnl=1.0,
            trajectories=[{"reward": 1.0, "observation": {"vector": [5000.0]}} for _ in range(20)],
            pnl_series=[1.0],
            constitution_violations=0,
            regimes_seen={"RANGE"},
            partial_complete=True,
            rollout_steps=200,
            range_hold_signals=95,
            range_total_signals=100,
        )

    monkeypatch.setattr("lumina_core.birth.stage_training_loop.run_policy_rollout", _stagnant_rollout)
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_kwargs: __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set()),
    )
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.expand_birth_data", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no expand")))

    with pytest.raises(RuntimeError, match="bounded_rollouts"):
        engine._run_stage_research_loop(
            stage=CurriculumStage.STAGE2_RANGE,
            stage_index=1,
            stage_ticks=_range_ticks(600),
            train_ticks=_range_ticks(600),
            holdout_ticks=_range_ticks(120),
            target=50,
            stage_progress_pct=40.0,
            training_mode="certified",
            ppo_steps_per_update=1000,
            polish_ppo_timesteps=1000,
            trade_budget_cap=500,
            prefer_real=True,
            start_price=5000.0,
        )

    assert rollout_calls["n"] >= 3
    assert max(explore_steps_seen) > min(explore_steps_seen), "exploration should escalate after stagnation"


@pytest.mark.unit
def test_stage2_wall_budget_triggers_provisional_pass(
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
            stage2_range_trades=400,
            rollout_chunk_trades=10,
            max_stage_wall_sec=300,
            max_rollouts_per_stage=50,
            allow_provisional_pass=True,
            checkpoint_interval_sec=3600,
        ),
        trade_budget_cap=500,
    )
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    start = 1_000_000.0
    tick = {"value": start}

    def _fake_time() -> float:
        return tick["value"]

    def _advance_time(_: float) -> None:
        tick["value"] += 400.0

    monkeypatch.setattr("lumina_core.birth.stage_training_loop.time.time", _fake_time)
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.run_policy_rollout",
        lambda **_kwargs: (
            _advance_time(0),
            SimRolloutResult(
                trades=15,
                wins=6,
                hold_signals=40,
                total_signals=100,
                total_pnl=2.0,
                trajectories=[{"reward": 1.0, "observation": {"vector": [5000.0]}} for _ in range(20)],
                pnl_series=[1.0],
                constitution_violations=0,
                regimes_seen={"RANGE"},
                partial_complete=True,
                rollout_steps=200,
                range_hold_signals=35,
                range_total_signals=100,
            ),
        )[1],
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_kwargs: __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set()),
    )
    monkeypatch.setattr("lumina_core.birth.stage_training_loop.expand_birth_data", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no expand")))

    result = engine._run_stage_research_loop(
        stage=CurriculumStage.STAGE2_RANGE,
        stage_index=1,
        stage_ticks=_range_ticks(600),
        train_ticks=_range_ticks(600),
        holdout_ticks=_range_ticks(120),
        target=400,
        stage_progress_pct=40.0,
        training_mode="certified",
        ppo_steps_per_update=1000,
        polish_ppo_timesteps=1000,
        trade_budget_cap=500,
        prefer_real=True,
        start_price=5000.0,
    )

    assert result is None
    assert tick["value"] - start >= 300.0


@pytest.mark.unit
def test_certified_wall_budget_exhausted_does_not_provisional_pass(
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
            stage2_range_trades=50,
            rollout_chunk_trades=10,
            max_stage_wall_sec=300,
            certified_max_rollouts_per_stage=15,
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
        return tick["value"]

    def _advance_time(_: float) -> None:
        tick["value"] += 400.0

    monkeypatch.setattr("lumina_core.birth.stage_training_loop.time.time", _fake_time)
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.run_policy_rollout",
        lambda **_kwargs: (
            _advance_time(0),
            SimRolloutResult(
                trades=6,
                wins=2,
                hold_signals=90,
                total_signals=100,
                total_pnl=0.5,
                trajectories=[{"reward": 0.5, "observation": {"vector": [5000.0]}} for _ in range(20)],
                pnl_series=[0.5],
                constitution_violations=0,
                regimes_seen={"RANGE"},
                partial_complete=True,
                rollout_steps=200,
                range_hold_signals=90,
                range_total_signals=100,
            ),
        )[1],
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.mine_winning_patterns",
        lambda **_kwargs: __import__(
            "lumina_core.birth.pattern_miner", fromlist=["PatternMineResult"]
        ).PatternMineResult(
            patterns=[{"reward": 1.0, "observation": {"vector": [5000.0]}}] * 120,
            wins=120,
            scanned=100,
            regimes_seen={"RANGE"},
        ),
    )
    monkeypatch.setattr(
        "lumina_core.birth.stage_training_loop.expand_birth_data",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no expand")),
    )

    result = engine._run_stage_research_loop(
        stage=CurriculumStage.STAGE2_RANGE,
        stage_index=1,
        stage_ticks=_range_ticks(600),
        train_ticks=_range_ticks(600),
        holdout_ticks=_range_ticks(120),
        target=50,
        stage_progress_pct=40.0,
        training_mode="certified",
        ppo_steps_per_update=1000,
        polish_ppo_timesteps=1000,
        trade_budget_cap=500,
        prefer_real=True,
        start_price=5000.0,
    )

    assert result is not None
    assert result.get("status") == "stage_stalled"
