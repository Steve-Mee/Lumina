from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthV2Config
from lumina_core.birth.data_expansion import DataExpansionResult
from lumina_core.birth.pattern_miner import PatternMineResult
from lumina_core.birth.purged_split import PurgedSplit
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
def test_bro_one_trade_rollout_plus_oracle_progresses_stage(
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
            max_rollouts_per_stage=6,
            gen0_provisional_min_trades=5,
            oracle_patterns_per_stage=200,
        ),
        trade_budget_cap=500,
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
            patterns=[
                {"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.1]}, "source": "oracle"}
                for i in range(150)
            ],
            wins=150,
            scanned=200,
            regimes_seen={"TREND_UP"},
        ),
    )

    def _one_trade_rollout(**_kwargs) -> SimRolloutResult:
        return SimRolloutResult(
            trades=1,
            wins=1,
            hold_signals=0,
            total_signals=1,
            total_pnl=1.0,
            trajectories=[{"reward": 1.0, "observation": {"vector": [5000.0]}}],
            pnl_series=[1.0],
            constitution_violations=0,
            regimes_seen={"TREND_UP"},
            partial_complete=True,
            rollout_steps=200,
        )

    monkeypatch.setattr("lumina_core.birth.engine.run_policy_rollout", _one_trade_rollout)
    monkeypatch.setattr(
        "lumina_core.birth.engine.evaluate_holdout_certificate",
        lambda **_kwargs: {"certificate_passed": False},
    )

    engine.run_birth_phase(target_trades=100, force=True, prefer_real_data_only=False)

    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    assert progress_path.is_file()
    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    assert payload.get("phase") != "curriculum_failed"
    assert payload.get("phase") not in {"simulation_stall", "curriculum_failed"}


@pytest.mark.unit
def test_bro_engine_version_constant() -> None:
    from lumina_core.birth.config import BRO_ENGINE_VERSION

    assert BRO_ENGINE_VERSION == "BRO-v2"


@pytest.mark.unit
def test_reason_specific_remediation_passes_on_second_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lumina_core.birth.engine import BirthPhaseEngineV2
    from lumina_core.birth.purged_split import purged_train_holdout_split

    trainer = _FakePpoTrainer()
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.birth_config = BirthV2Config(
        curriculum=BirthCurriculumConfig(
            max_certificate_remediation_attempts=3,
            curriculum_ppo_timesteps=2000,
            polish_ppo_timesteps=4000,
            rollout_chunk_trades=50,
        ),
        trade_budget_cap=500,
    )
    ticks = _rising_ticks(900)
    split = purged_train_holdout_split(ticks, holdout_pct=0.2)
    for i in range(100):
        engine.buffer.add({"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.1]}})

    eval_calls = {"n": 0}

    def _mock_eval(**_kwargs) -> dict:
        eval_calls["n"] += 1
        if eval_calls["n"] < 2:
            return {
                "certificate_passed": False,
                "failure_reasons": ["regimes_covered:1/3"],
            }
        return {
            "certificate_passed": True,
            "regimes_covered": ["TREND_UP", "TREND_DOWN", "NEUTRAL"],
        }

    monkeypatch.setattr(
        "lumina_core.birth.engine.evaluate_holdout_certificate",
        _mock_eval,
    )
    monkeypatch.setattr("lumina_core.birth.engine.expand_birth_data", _mock_expand)
    monkeypatch.setattr(
        "lumina_core.birth.engine.run_policy_rollout",
        lambda **_kwargs: SimRolloutResult(
            trades=10,
            wins=5,
            hold_signals=0,
            total_signals=10,
            total_pnl=5.0,
            trajectories=[
                {"reward": 1.0, "observation": {"vector": [5000.0 + i * 0.1]}} for i in range(100)
            ],
            pnl_series=[1.0] * 10,
            constitution_violations=0,
            regimes_seen={"TREND_UP", "TREND_DOWN", "NEUTRAL"},
            partial_complete=True,
            rollout_steps=200,
        ),
    )

    result = engine._run_certificate_remediation(
        split=split,
        eval_result={
            "certificate_passed": False,
            "failure_reasons": ["regimes_covered:1/3"],
        },
        training_mode="certified",
        ppo_steps_per_update=1000,
        trade_budget_cap=500,
        prefer_real=False,
        start_price=5000.0,
    )
    assert result.get("certificate_passed") is True
    assert eval_calls["n"] >= 2


@pytest.mark.unit
def test_bro_empty_oracle_returns_history_unavailable(
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
            max_rollouts_per_stage=2,
            stagnation_rollouts_before_expand=1,
        ),
        trade_budget_cap=100,
        prefer_real_data_only=True,
    )

    monkeypatch.setattr(
        "lumina_core.birth.engine.load_historical_ticks",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.enrich_ticks_with_news",
        lambda ticks, **_kwargs: ticks,
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.mine_winning_patterns",
        lambda **_kwargs: PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set()),
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.expand_birth_data",
        lambda **_kwargs: DataExpansionResult(
            train_ticks=[],
            holdout_ticks=[],
            all_ticks=[],
            split=PurgedSplit(train=[], holdout=[], holdout_days=0, train_days=0),
            days_back=90,
            step_index=3,
            real_data_pct=0.0,
            exhausted=True,
        ),
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.run_policy_rollout",
        lambda **_kwargs: SimRolloutResult(
            trades=0,
            wins=0,
            hold_signals=0,
            total_signals=0,
            total_pnl=0.0,
            trajectories=[],
            pnl_series=[],
            constitution_violations=0,
            regimes_seen=set(),
            partial_complete=True,
            rollout_steps=10,
        ),
    )

    result = engine.run_birth_phase(target_trades=50, force=True, prefer_real_data_only=True)
    assert result["status"] == "history_unavailable"
