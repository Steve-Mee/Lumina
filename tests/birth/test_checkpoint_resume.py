from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.buffer_persist import save_buffer
from lumina_core.birth.checkpoint import save_checkpoint
from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.data_expansion import DataExpansionResult
from lumina_core.birth.pattern_miner import PatternMineResult
from lumina_core.birth.sim_runner import SimRolloutResult
from lumina_core.lumina_birth_engine import LuminaBirthEngine


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
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"policy")


def _rising_ticks(n: int) -> list[dict]:
    ticks = []
    price = 5000.0
    for i in range(n):
        price += 0.5
        ticks.append(
            {
                "timestamp": f"2026-01-01T{i:04d}:00Z",
                "last": price,
                "bid": price - 0.125,
                "ask": price + 0.125,
                "volume": 100,
                "source": "real_historical",
                "regime": ("TREND_UP", "TREND_DOWN", "NEUTRAL")[i % 3],
            }
        )
    return ticks


def _mock_expand(**_kwargs) -> DataExpansionResult:
    from lumina_core.birth.purged_split import purged_train_holdout_split

    ticks = _rising_ticks(800)
    split = purged_train_holdout_split(ticks, holdout_pct=0.2)
    return DataExpansionResult(
        train_ticks=list(split.train),
        holdout_ticks=list(split.holdout),
        all_ticks=ticks,
        split=split,
        days_back=90,
        step_index=0,
        real_data_pct=99.0,
        exhausted=False,
    )


@pytest.mark.unit
def test_mid_stage_resume_restores_buffer_and_stage_trades(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trainer = _FakePpoTrainer()
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(
            rollout_chunk_trades=5,
            max_rollouts_per_stage=3,
            gen0_provisional_min_trades=5,
            oracle_patterns_per_stage=50,
            checkpoint_interval_sec=60,
        ),
        trade_budget_cap=500,
    )

    trajectories = [{"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.1]}} for i in range(120)]
    buffer_path = save_buffer(tmp_path, trajectories)
    policy_path = tmp_path / "state" / "birth_policy.zip"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes(b"policy")

    save_checkpoint(
        tmp_path,
        cumulative_trades=77,
        ppo_steps=5000,
        training_mode="certified",
        stages_passed=["stage1_trend"],
        curriculum_stage="stage2_range",
        policy_path=str(policy_path),
        stage_metrics={
            "stage_trades": 42,
            "stage_wins": 20,
            "stage_hold_signals": 10,
            "stage_total_signals": 50,
            "stage_range_hold_signals": 8,
            "stage_range_total_signals": 30,
            "patterns_mined": 25,
            "stages_passed": ["stage1_trend"],
            "buffer_size": len(trajectories),
        },
        buffer_path=buffer_path,
        data_manifest={"train_hash": "seed", "preflight_ok": True},
        phase="stage2_range",
    )

    restored_trades: list[int] = []

    def _capture_rollout(**kwargs) -> SimRolloutResult:
        restored_trades.append(kwargs.get("target_trades", 0))
        return SimRolloutResult(
            trades=2,
            wins=1,
            hold_signals=1,
            total_signals=2,
            total_pnl=1.0,
            trajectories=[{"reward": 1.0, "observation": {"vector": [5000.0]}}],
            pnl_series=[1.0],
            constitution_violations=0,
            regimes_seen={"NEUTRAL"},
            partial_complete=True,
            rollout_steps=100,
            range_hold_signals=1,
            range_total_signals=2,
        )

    monkeypatch.setattr(
        "lumina_core.birth.engine.load_historical_ticks",
        lambda **_kwargs: _rising_ticks(900),
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.enrich_ticks_with_news",
        lambda ticks, **_kwargs: ticks,
    )
    monkeypatch.setattr("lumina_core.birth.engine.expand_birth_data", _mock_expand)
    monkeypatch.setattr(
        "lumina_core.birth.engine.mine_winning_patterns",
        lambda **_kwargs: PatternMineResult(
            patterns=[{"reward": 1.0, "observation": {"vector": [5000.0]}} for _ in range(30)],
            wins=30,
            scanned=50,
            regimes_seen={"NEUTRAL"},
        ),
    )
    monkeypatch.setattr("lumina_core.birth.engine.run_policy_rollout", _capture_rollout)
    monkeypatch.setattr(
        "lumina_core.birth.engine.evaluate_holdout_certificate",
        lambda **_kwargs: {"certificate_passed": False, "failure_reasons": ["oos_sharpe:0/0.35"]},
    )

    engine.run_birth_phase(
        target_trades=100,
        force=False,
        prefer_real_data_only=False,
        reuse_existing_policy=True,
    )

    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    assert progress_path.is_file()
    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    stage_trades = int(payload.get("stage_trades", 0) or 0)
    assert stage_trades >= 42, f"expected resumed stage_trades >= 42, got {stage_trades}"

    ckpt = json.loads((tmp_path / "state" / "lumina_birth_checkpoint.json").read_text(encoding="utf-8"))
    metrics = ckpt.get("stage_metrics") or {}
    assert int(metrics.get("stage_trades", 0) or 0) >= 42
    assert int(metrics.get("buffer_size", 0) or 0) >= 80


@pytest.mark.unit
def test_checkpoint_persists_adaptation_fields_on_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lumina_core.birth.engine import BirthPhaseEngineV2
    from lumina_core.birth.curriculum import CurriculumStage

    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(
            stage1_trend_trades=200,
            rollout_chunk_trades=20,
            checkpoint_interval_sec=60,
            wall_behavior="adaptive",
            max_stage_retries=3,
        ),
        trade_budget_cap=500,
    )
    for i in range(300):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.01]}})

    save_checkpoint(
        tmp_path,
        cumulative_trades=100,
        ppo_steps=1000,
        training_mode="certified",
        stages_passed=[],
        curriculum_stage="stage1_trend",
        stage_metrics={
            "stage_trades": 100,
            "stage_wins": 30,
            "stage_hold_signals": 0,
            "stage_total_signals": 100,
            "patterns_mined": 50,
            "winrate_history": [0.30, 0.29, 0.28, 0.27, 0.26],
            "retries_this_stage": 1,
            "adaptation_history": [{"reason": "metrics_not_improving_within_wall", "chunk_target": 8}],
            "escalation_level": 2,
        },
        phase="curriculum_learning",
    )

    rollout_calls = {"n": 0}

    def _one_rollout(**_kwargs) -> SimRolloutResult:
        rollout_calls["n"] += 1
        if rollout_calls["n"] >= 2:
            raise RuntimeError("bounded")
        return SimRolloutResult(
            trades=5,
            wins=2,
            hold_signals=0,
            total_signals=5,
            total_pnl=0.5,
            trajectories=[{"reward": 0.5, "observation": {"vector": [5000.0]}}],
            pnl_series=[0.5],
            constitution_violations=0,
            regimes_seen={"TREND_UP"},
            partial_complete=True,
            rollout_steps=100,
        )

    monkeypatch.setattr("lumina_core.birth.engine.run_policy_rollout", _one_rollout)
    monkeypatch.setattr(
        "lumina_core.birth.engine.mine_winning_patterns",
        lambda **_kwargs: PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set()),
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.expand_birth_data",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no expand")),
    )

    ticks = _rising_ticks(600)
    with pytest.raises(RuntimeError, match="bounded"):
        engine._run_stage_research_loop(
            stage=CurriculumStage.STAGE1_TREND,
            stage_index=0,
            stage_ticks=ticks,
            train_ticks=ticks,
            holdout_ticks=ticks[:120],
            target=200,
            stage_progress_pct=25.0,
            training_mode="certified",
            ppo_steps_per_update=1000,
            polish_ppo_timesteps=1000,
            trade_budget_cap=500,
            prefer_real=True,
            start_price=5000.0,
        )

    ckpt = json.loads((tmp_path / "state" / "lumina_birth_checkpoint.json").read_text(encoding="utf-8"))
    metrics = ckpt.get("stage_metrics") or {}
    assert metrics.get("winrate_history") == [0.30, 0.29, 0.28, 0.27, 0.26] or len(
        metrics.get("winrate_history") or []
    ) >= 5
    assert int(metrics.get("retries_this_stage", 0) or 0) >= 1
    assert len(metrics.get("adaptation_history") or []) >= 1
    assert int(metrics.get("escalation_level", 0) or 0) >= 2


