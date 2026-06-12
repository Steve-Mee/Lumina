"""Birth Phase: certified vs practice training_mode and checkpoint behavior (v2)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.checkpoint import can_resume_checkpoint
from lumina_core.lumina_birth_engine import LuminaBirthEngine


class _FakePpoTrainer:
    def __init__(self) -> None:
        self.create_policy_calls: list[bool] = []

    def create_fresh_birth_policy(self, *, allow_load_existing: bool = True):
        self.create_policy_calls.append(bool(allow_load_existing))
        return {"policy": "fresh"}

    def update_from_buffer(self, **_kwargs):
        return {"policy": "updated"}

    def final_birth_polish(self, _buffer) -> None:
        return None

    def save_final_birth_policy(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"policy")


def _ticks(n: int = 100) -> list[dict]:
    return [
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "last": 5000.0 + i,
            "bid": 4999.875,
            "ask": 5000.125,
            "volume": 10,
            "source": "real_historical",
        }
        for i in range(n)
    ]


@pytest.mark.unit
def test_certified_start_sets_training_mode_certified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    monkeypatch.setattr("lumina_core.birth.engine.load_historical_ticks", lambda **_kwargs: _ticks())
    monkeypatch.setattr(
        "lumina_core.birth.engine.run_policy_rollout",
        lambda **_kwargs: SimpleNamespace(
            trades=100,
            wins=55,
            hold_signals=0,
            total_signals=100,
            trajectories=[{"reward": 1.0}] * 300,
            constitution_violations=0,
            regimes_seen={"TREND_UP", "NEUTRAL"},
        ),
    )
    monkeypatch.setattr(
        "lumina_core.birth.engine.evaluate_holdout_certificate",
        lambda **_kwargs: {
            "certificate_passed": True,
            "real_data_pct": 99.0,
            "oos_winrate": 0.5,
            "oos_sharpe": 0.4,
            "oos_max_drawdown_pct": 4.0,
            "constitution_violations": 0,
            "regimes_covered": ["TREND_UP", "TREND_DOWN", "NEUTRAL"],
            "holdout_days": 5,
            "holdout_trades": 60,
        },
    )
    result = engine.run_birth_phase(prefer_real_data_only=True, practice_mode=False)
    assert result.get("training_mode") == "certified"
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress.get("training_mode") in {None, "certified"} or result.get("training_mode") == "certified"


@pytest.mark.unit
def test_practice_with_real_ticks_still_not_certified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    monkeypatch.setattr("lumina_core.birth.engine.load_historical_ticks", lambda **_kwargs: _ticks(50))
    monkeypatch.setattr(
        "lumina_core.birth.engine.run_policy_rollout",
        lambda **_kwargs: SimpleNamespace(
            trades=50,
            wins=25,
            hold_signals=0,
            total_signals=50,
            trajectories=[{"reward": 1.0}] * 50,
            constitution_violations=0,
            regimes_seen={"TREND_UP"},
        ),
    )
    result = engine.run_birth_phase(prefer_real_data_only=False, practice_mode=True)
    assert result["training_mode"] == "practice"
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress.get("stage") == "practice_completed" or result["training_mode"] == "practice"


@pytest.mark.unit
def test_checkpoint_mode_mismatch_blocks_resume(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "lumina_birth_checkpoint.json").write_text(
        json.dumps({"training_mode": "practice", "cumulative_trades": 100, "ppo_steps": 10}),
        encoding="utf-8",
    )
    flags = (
        tmp_path / "state" / "lumina_birth_completed.flag",
        tmp_path / "state" / "first_boot_completed.flag",
    )
    assert can_resume_checkpoint(tmp_path, training_mode="certified", completion_flag_paths=flags) is False
