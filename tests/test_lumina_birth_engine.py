from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.lumina_birth_engine import LuminaBirthEngine


class _FakePpoTrainer:
    def __init__(self) -> None:
        self.saved_paths: list[str] = []
        self.create_policy_calls: list[bool] = []
        self.loaded_paths: list[str] = []
        self.update_calls = 0
        self._active_policy: dict[str, str] | None = None

    def create_fresh_birth_policy(self, *, allow_load_existing: bool = True):
        self.create_policy_calls.append(bool(allow_load_existing))
        if self._active_policy is not None:
            return self._active_policy
        return {"policy": "fresh" if not allow_load_existing else "resumed"}

    def load_policy(self, policy_path: str) -> None:
        self.loaded_paths.append(policy_path)
        self._active_policy = {"policy": "loaded_from_checkpoint", "path": policy_path}

    def _resolve_active_model(self):
        return self._active_policy

    def update_from_buffer(self, **kwargs):
        self.update_calls += 1
        return {"policy": f"updated_{self.update_calls}"}

    def final_birth_polish(self, _buffer) -> None:
        return None

    def save_final_birth_policy(self, path: str) -> None:
        self.saved_paths.append(path)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"policy")


def _rising_historical_ticks(n: int) -> list[dict]:
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
            }
        )
    return ticks


class _HoldOnlyPolicy:
    def predict(self, observation, *, deterministic: bool = True):
        _ = observation, deterministic
        return __import__("numpy").array([0.0, 0.0, 0.0075, 0.013], dtype=__import__("numpy").float32), None


class _RecordingPolicy:
    def predict(self, observation, *, deterministic: bool = True):
        _ = deterministic
        return __import__("numpy").array([1.0, 0.5, 0.0075, 0.013], dtype=__import__("numpy").float32), None


@pytest.mark.unit
def test_birth_engine_marks_history_unavailable_when_no_real_data(tmp_path: Path) -> None:
    trainer = _FakePpoTrainer()
    svc = SimpleNamespace(load_historical_ohlc_extended=lambda **_kwargs: [])
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=svc,
        workspace_root=tmp_path,
    )
    result = engine.run_birth_phase(
        target_trades=10_000,
        max_real_days=30,
        prefer_real_data_only=True,
    )
    assert result["status"] == "history_unavailable"
    payload = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert payload["stage"] == "history_unavailable"
    assert payload["retryable"] is True


@pytest.mark.unit
def test_enrich_ticks_and_sim_runner_produce_trades(tmp_path: Path) -> None:
    ticks = enrich_ticks_for_sim(_rising_historical_ticks(600))
    assert any("TREND" in str(t.get("regime", "")).upper() for t in ticks[25:])
    runtime = SimpleNamespace(
        detect_market_regime=lambda _df: "NEUTRAL",
        market_data=SimpleNamespace(get_tape_snapshot=lambda: {}),
        get_current_dream_snapshot=lambda: {},
        AI_DRAWN_FIBS={},
        world_model={},
    )
    result = run_policy_rollout(
        runtime=runtime,
        data=ticks,
        policy=_RecordingPolicy(),
        target_trades=3,
        workspace_root=tmp_path,
    )
    assert result.trades >= 1


@pytest.mark.unit
def test_resume_checkpoint_reuses_existing_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trainer = _FakePpoTrainer()
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes(b"policy")
    (tmp_path / "state" / "lumina_birth_checkpoint.json").write_text(
        json.dumps(
            {
                "version": 2,
                "cumulative_trades": 200,
                "ppo_steps": 1000,
                "training_mode": "certified",
                "stages_passed": ["stage1_trend"],
                "curriculum_stage": "stage2_range",
                "policy_path": str(policy_path),
            }
        ),
        encoding="utf-8",
    )
    ticks = _rising_historical_ticks(800)
    monkeypatch.setattr(
        "lumina_core.birth.engine.load_historical_ticks",
        lambda **_kwargs: ticks,
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
    result = engine.run_birth_phase(target_trades=500, force=False, prefer_real_data_only=False)
    assert trainer.loaded_paths == [str(policy_path)]
    assert trainer.create_policy_calls == []
    assert result["status"] in {"completed", "certificate_failed", "practice_completed"}


@pytest.mark.unit
def test_checkpoint_persists_policy_path(tmp_path: Path) -> None:
    from lumina_core.birth.checkpoint import read_checkpoint_payload, save_checkpoint

    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes(b"policy")
    save_checkpoint(
        tmp_path,
        cumulative_trades=120,
        ppo_steps=500,
        training_mode="certified",
        stages_passed=["stage1_trend"],
        curriculum_stage="stage2_range",
        policy_path=str(policy_path),
    )
    payload = read_checkpoint_payload(tmp_path)
    assert payload is not None
    assert payload["policy_path"] == str(policy_path)
