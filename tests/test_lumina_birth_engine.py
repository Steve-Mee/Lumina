from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.lumina_birth_engine import LuminaBirthEngine


class _FakePpoTrainer:
    def __init__(self) -> None:
        self.saved_paths: list[str] = []

    def create_fresh_birth_policy(self):
        return {"policy": "fresh"}

    def update_from_buffer(self, **_kwargs):
        return {"policy": "updated"}

    def final_birth_polish(self, _buffer) -> None:
        return None

    def save_final_birth_policy(self, path: str) -> None:
        self.saved_paths.append(path)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"policy")

    def save_intermediate_policy(self, _trades: int) -> None:
        return None


@pytest.mark.unit
def test_estimate_ppo_timesteps_planned_includes_chunks_and_polish(tmp_path: Path) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    planned = engine._estimate_ppo_timesteps_planned(
        target_trades=100_000,
        chunk_size=50_000,
        ppo_update_timesteps=25_000,
    )
    assert planned == 100_000


@pytest.mark.unit
def test_ppo_progress_extra_writes_cumulative_and_planned(tmp_path: Path) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    engine.ppo_steps = 75_000
    engine._ppo_timesteps_planned_total = 225_000
    engine.cumulative_trades = 25_000
    extra = engine._ppo_progress_extra(target_trades=25_000)
    assert extra["ppo_steps_cumulative"] == 75_000
    assert extra["ppo_timesteps_planned_total"] == 225_000
    assert extra["sim_trades_complete"] is True


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
    assert payload["phase"] == "loading_history_failed"
    assert payload["retryable"] is True


@pytest.mark.unit
def test_birth_engine_practice_mode_never_marks_certified_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trainer = _FakePpoTrainer()
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0, "bid": 4999.875, "ask": 5000.125, "volume": 10}]
    monkeypatch.setattr(engine, "_load_training_ticks", lambda **_kwargs: ticks)
    monkeypatch.setattr(
        engine,
        "_simulate_chunk_with_policy",
        lambda *, ticks, chunk_trades, policy: {
            "trades": chunk_trades,
            "total_pnl": 12.0,
            "winrate": 0.5,
            "trajectories": [{"reward": 1.0}],
            "pnl_series": [12.0],
        },
    )

    result = engine.run_birth_phase(
        target_trades=5_000,
        max_real_days=30,
        prefer_real_data_only=False,
        practice_mode=True,
    )
    assert result["status"] == "practice_completed"
    assert not (tmp_path / "state" / "lumina_birth_completed.flag").exists()
    assert not (tmp_path / "state" / "first_boot_completed.flag").exists()
    assert (tmp_path / "state" / "lumina_birth_practice_completed.flag").exists()
    assert (tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy_practice.zip").exists()
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress["stage"] == "practice_completed"
    assert progress["training_mode"] == "practice"


@pytest.mark.unit
def test_birth_engine_stops_mid_chunk_on_stop_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trainer = _FakePpoTrainer()
    stop_event = threading.Event()
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
        stop_event=stop_event,
    )
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0, "bid": 4999.875, "ask": 5000.125, "volume": 10}]

    def _slow_chunk(*, ticks, chunk_trades, policy):
        stop_event.set()
        return {"trades": 0, "total_pnl": 0.0, "winrate": 0.0, "trajectories": [], "pnl_series": []}

    monkeypatch.setattr(engine, "_load_training_ticks", lambda **_kwargs: ticks)
    monkeypatch.setattr(engine, "_simulate_chunk_with_policy", _slow_chunk)

    result = engine.run_birth_phase(
        target_trades=10_000,
        max_real_days=30,
        prefer_real_data_only=False,
        chunk_size=5_000,
    )
    assert result["status"] == "stopped"
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress["stage"] == "stopped_by_user"
