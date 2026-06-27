from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.data_expansion import DataExpansionResult
from lumina_core.birth.pattern_miner import PatternMineResult
from lumina_core.birth.sim_runner import SimRolloutResult
from lumina_core.lumina_birth_engine import LuminaBirthEngine


class _FakePpoTrainer:
    def __init__(self) -> None:
        self.update_calls = 0
        self._active_policy: dict[str, str] = {"policy": "fresh"}

    def create_fresh_birth_policy(self, *, allow_load_existing: bool = True):
        _ = allow_load_existing
        return self._active_policy

    def update_from_buffer(self, **kwargs):
        _ = kwargs
        self.update_calls += 1
        return {"policy": f"updated_{self.update_calls}"}

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
                "regime": "TREND_UP" if i % 3 else "NEUTRAL",
            }
        )
    return ticks


def _fast_oracle_mine(**_kwargs) -> PatternMineResult:
    patterns = [
        {
            "reward": 1.0,
            "observation": {"vector": [5000.0 + i * 0.1]},
            "source": "oracle",
        }
        for i in range(150)
    ]
    return PatternMineResult(
        patterns=patterns,
        wins=len(patterns),
        scanned=200,
        regimes_seen={"TREND_UP"},
    )


def _mock_expand(**kwargs):
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


_expand_calls = {"n": 0}


def _mock_expand_once(**_kwargs):
    from lumina_core.birth.purged_split import purged_train_holdout_split

    _expand_calls["n"] += 1
    ticks = _rising_ticks(800)
    split = purged_train_holdout_split(ticks, holdout_pct=0.2)
    if _expand_calls["n"] > 1:
        return DataExpansionResult(
            train_ticks=[],
            holdout_ticks=[],
            all_ticks=ticks,
            split=split,
            days_back=90,
            step_index=_expand_calls["n"],
            real_data_pct=99.0,
            exhausted=True,
        )
    return DataExpansionResult(
        train_ticks=list(split.train),
        holdout_ticks=list(split.holdout),
        all_ticks=ticks,
        split=split,
        days_back=90,
        step_index=_expand_calls["n"],
        real_data_pct=99.0,
        exhausted=False,
    )


@pytest.mark.unit
def test_learning_loop_continues_after_single_trade_chunk(
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
    small_cfg = BirthV2Config(
        curriculum=BirthCurriculumConfig(
            stage1_trend_trades=2000,
            rollout_chunk_trades=10,
            max_rollouts_per_stage=15,
            max_escalation_level=5,
            gen0_provisional_min_trades=25,
            rollout_step_budget_multiplier=20,
        ),
        trade_budget_cap=10_000,
    )
    engine.birth_config = small_cfg

    monkeypatch.setattr(
        "lumina_core.birth.engine.load_historical_ticks",
        lambda **_kwargs: _rising_ticks(800),
    )
    monkeypatch.setattr("lumina_core.birth.engine.expand_birth_data", _mock_expand)
    monkeypatch.setattr("lumina_core.birth.engine.mine_winning_patterns", _fast_oracle_mine)
    monkeypatch.setattr(
        "lumina_core.birth.engine.enrich_ticks_with_news",
        lambda ticks, **_kwargs: ticks,
    )
    rollout_calls = {"n": 0}

    def _chunk_rollout(**_kwargs) -> SimRolloutResult:
        rollout_calls["n"] += 1
        trades = 50 if rollout_calls["n"] >= 3 else 1
        trajectories = [{"reward": 1.0, "pnl": 1.0}] * trades
        return SimRolloutResult(
            trades=trades,
            wins=trades,
            hold_signals=0,
            total_signals=trades,
            total_pnl=float(trades),
            trajectories=trajectories,
            pnl_series=[1.0] * trades,
            constitution_violations=0,
            regimes_seen={"TREND_UP"},
            rollout_steps=100,
            partial_complete=trades < 50,
        )

    monkeypatch.setattr("lumina_core.birth.engine.run_policy_rollout", _chunk_rollout)
    monkeypatch.setattr(
        "lumina_core.birth.engine.evaluate_holdout_certificate",
        lambda **_kwargs: {
            "certificate_passed": True,
            "holdout_trades": 60,
            "real_data_pct": 99.0,
            "oos_winrate": 0.5,
            "oos_sharpe": 0.4,
            "oos_max_drawdown_pct": 4.0,
            "constitution_violations": 0,
            "regimes_covered": ["TREND_UP", "NEUTRAL"],
            "holdout_days": 5,
        },
    )

    result = engine.run_birth_phase(target_trades=500, force=True, prefer_real_data_only=False)

    assert rollout_calls["n"] >= 3
    assert result["status"] in {
        "completed",
        "certificate_failed",
        "practice_completed",
        "stage_stalled",
    }
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    if progress_path.is_file():
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
        assert payload.get("phase") != "curriculum_failed"


@pytest.mark.unit
def test_learning_loop_never_writes_curriculum_failed_on_partial_winrate(
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
            stage1_trend_trades=5,
            stage2_range_trades=5,
            stage3_mixed_trades=5,
            rollout_chunk_trades=5,
            max_rollouts_per_stage=8,
            gen0_provisional_min_trades=5,
        ),
    )

    monkeypatch.setattr(
        "lumina_core.birth.engine.load_historical_ticks",
        lambda **_kwargs: _rising_ticks(400),
    )
    _expand_calls["n"] = 0
    monkeypatch.setattr("lumina_core.birth.engine.expand_birth_data", _mock_expand_once)
    monkeypatch.setattr("lumina_core.birth.engine.mine_winning_patterns", _fast_oracle_mine)
    monkeypatch.setattr(
        "lumina_core.birth.engine.enrich_ticks_with_news",
        lambda ticks, **_kwargs: ticks,
    )

    def _one_trade_rollout(**_kwargs) -> SimRolloutResult:
        return SimRolloutResult(
            trades=1,
            wins=1,
            hold_signals=0,
            total_signals=1,
            total_pnl=1.0,
            trajectories=[{"reward": 1.0}],
            pnl_series=[1.0],
            constitution_violations=0,
            regimes_seen={"TREND_UP"},
            partial_complete=True,
            rollout_steps=500,
        )

    monkeypatch.setattr("lumina_core.birth.engine.run_policy_rollout", _one_trade_rollout)
    monkeypatch.setattr(
        "lumina_core.birth.engine.evaluate_holdout_certificate",
        lambda **_kwargs: {"certificate_passed": False},
    )

    engine.run_birth_phase(target_trades=100, force=True, prefer_real_data_only=False)
    payload = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert payload.get("phase") != "curriculum_failed"
