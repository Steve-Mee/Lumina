from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import numpy as np

from lumina_core.birth_policy_observation import BIRTH_RL_OBS_DIM
from lumina_core.lumina_birth_engine import LuminaBirthEngine


class _FakePpoTrainer:
    def __init__(self) -> None:
        self.saved_paths: list[str] = []
        self.create_policy_calls: list[bool] = []
        self.update_calls = 0
        self.update_payloads: list[dict[str, object]] = []

    def create_fresh_birth_policy(self, *, allow_load_existing: bool = True):
        self.create_policy_calls.append(bool(allow_load_existing))
        return {"policy": "fresh"}

    def update_from_buffer(self, **kwargs):
        self.update_calls += 1
        self.update_payloads.append(dict(kwargs))
        return {"policy": f"updated_{self.update_calls}"}

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
        lambda *, ticks, chunk_trades, policy, **kwargs: {
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

    def _slow_chunk(*, ticks, chunk_trades, policy, **kwargs):
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


class _RecordingPolicy:
    def __init__(self) -> None:
        self.shapes: list[int] = []

    def predict(self, observation: np.ndarray, *, deterministic: bool = True):
        self.shapes.append(int(observation.shape[0]))
        return np.array([1.0, 0.5, 0.0075, 0.013], dtype=np.float32), None


@pytest.mark.unit
def test_resolve_policy_action_uses_28_dim_vector(tmp_path: Path) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    policy = _RecordingPolicy()
    tick = {"last": 5000.0, "regime": "TRENDING", "imbalance": 1.0, "volume": 10}
    obs = engine._build_observation(tick=tick, position=None)
    obs_vec = engine._build_policy_observation_vector(tick=tick, position=None, tick_index=1, tick_count=10)
    action, source = engine._resolve_policy_action(
        policy=policy,
        observation=obs,
        tick=tick,
        observation_vector=obs_vec,
    )
    assert source == "policy"
    assert action["side"] == "BUY"
    assert policy.shapes == [BIRTH_RL_OBS_DIM]


@pytest.mark.unit
def test_near_complete_grace_completes_instead_of_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trainer = _FakePpoTrainer()
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0, "bid": 4999.875, "ask": 5000.125, "volume": 10}]
    monkeypatch.setattr(engine, "_load_training_ticks", lambda **_kwargs: ticks)

    call_count = {"n": 0}

    def _chunk(*, ticks, chunk_trades, policy, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {
                "trades": 24_611,
                "total_pnl": 1.0,
                "winrate": 0.5,
                "trajectories": [{"reward": 1.0}],
                "pnl_series": [1.0],
                "diagnostics": {},
            }
        return {
            "trades": 0,
            "total_pnl": 0.0,
            "winrate": 0.0,
            "trajectories": [],
            "pnl_series": [],
            "diagnostics": {"hold_signals": 100},
        }

    monkeypatch.setattr(engine, "_simulate_chunk_with_policy", _chunk)

    result = engine.run_birth_phase(
        target_trades=25_000,
        max_real_days=30,
        prefer_real_data_only=False,
        chunk_size=50_000,
    )
    assert result["status"] in {"birth_completed", "practice_completed", "completed"}
    assert engine.cumulative_trades >= 25_000
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress["stage"] != "failed"


@pytest.mark.unit
def test_consecutive_stall_chunks_fail_after_threshold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trainer = _FakePpoTrainer()
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0, "volume": 10}]
    monkeypatch.setattr(engine, "_load_training_ticks", lambda **_kwargs: ticks)
    monkeypatch.setattr(
        engine,
        "_simulate_chunk_with_policy",
        lambda *, ticks, chunk_trades, policy, **kwargs: {
            "trades": 0,
            "total_pnl": 0.0,
            "winrate": 0.0,
            "trajectories": [],
            "pnl_series": [],
            "diagnostics": {"exhausted": True},
        },
    )

    result = engine.run_birth_phase(
        target_trades=10_000,
        max_real_days=30,
        prefer_real_data_only=False,
        chunk_size=5_000,
    )
    assert result["status"] == "birth_failed"
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress["stage"] == "failed"
    assert progress["phase"] == "simulation_stall"
    assert progress.get("retryable") is True


def _rising_historical_ticks(count: int = 600) -> list[dict]:
    ticks: list[dict] = []
    base = 5000.0
    for i in range(count):
        price = base + float(i) * 0.5
        ticks.append(
            {
                "timestamp": f"2026-01-01T12:{i % 60:02d}:00Z",
                "last": price,
                "bid": price - 0.125,
                "ask": price + 0.125,
                "volume": 10,
                "source": "real_historical",
                "regime": "NEUTRAL",
                "imbalance": 1.0,
            }
        )
    return ticks


class _HoldOnlyPolicy:
    def predict(self, observation: np.ndarray, *, deterministic: bool = True):
        _ = observation, deterministic
        return np.array([0.0, 0.0, 0.0075, 0.013], dtype=np.float32), None


@pytest.mark.unit
def test_enrich_ticks_and_sim_produce_trades_on_neutral_historical(tmp_path: Path) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    ticks = engine._enrich_ticks_for_sim(_rising_historical_ticks(600))
    assert any("TREND" in str(t.get("regime", "")).upper() for t in ticks[25:])
    result = engine._simulate_chunk_with_policy(
        ticks=ticks,
        chunk_trades=5,
        policy=_HoldOnlyPolicy(),
        target_trades=5_000,
        training_mode="certified",
    )
    assert int(result.get("trades", 0) or 0) >= 1
    diag = result.get("diagnostics", {})
    assert int(diag.get("bootstrap_count", 0) or 0) >= 1 or int(diag.get("buy_signals", 0) or 0) >= 1


@pytest.mark.unit
def test_sim_heartbeat_writes_sim_diagnostics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    ticks = engine._enrich_ticks_for_sim(_rising_historical_ticks(12_000))
    writes: list[dict] = []
    original = engine._write_progress

    def _capture(**kwargs):
        writes.append(dict(kwargs))
        return original(**kwargs)

    monkeypatch.setattr(engine, "_write_progress", _capture)
    monkeypatch.setattr(engine, "_stop_requested", lambda: len(writes) >= 3)
    engine._simulate_chunk_with_policy(
        ticks=ticks,
        chunk_trades=100,
        policy=_HoldOnlyPolicy(),
        target_trades=100,
        training_mode="certified",
    )
    diag_writes = [w for w in writes if isinstance(w.get("sim_diagnostics"), dict)]
    assert diag_writes
    assert int(diag_writes[0]["sim_diagnostics"].get("ticks_processed", 0) or 0) > 0
    assert int(diag_writes[0].get("trades_done", 0) or 0) >= 0
    assert "chunk_trades_partial" in diag_writes[0]


@pytest.mark.unit
def test_force_start_creates_fresh_policy_without_loading_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        lambda *, ticks, chunk_trades, policy, **kwargs: {
            "trades": chunk_trades,
            "total_pnl": 1.0,
            "winrate": 0.5,
            "trajectories": [{"reward": 1.0}],
            "pnl_series": [1.0],
        },
    )
    result = engine.run_birth_phase(target_trades=100, force=True, chunk_size=100, ppo_update_timesteps=1_000)
    assert result["status"] in {"birth_completed", "completed", "practice_completed"}
    assert trainer.create_policy_calls
    assert trainer.create_policy_calls[0] is False


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
    (tmp_path / "state" / "lumina_birth_checkpoint.json").write_text(
        json.dumps({"target_trades": 500, "cumulative_trades": 200, "ppo_steps": 1000, "training_mode": "certified"}),
        encoding="utf-8",
    )
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0, "bid": 4999.875, "ask": 5000.125, "volume": 10}]
    monkeypatch.setattr(engine, "_load_training_ticks", lambda **_kwargs: ticks)
    monkeypatch.setattr(
        engine,
        "_simulate_chunk_with_policy",
        lambda *, ticks, chunk_trades, policy, **kwargs: {
            "trades": chunk_trades,
            "total_pnl": 1.0,
            "winrate": 0.5,
            "trajectories": [{"reward": 1.0}],
            "pnl_series": [1.0],
        },
    )
    result = engine.run_birth_phase(target_trades=500, force=False, chunk_size=300, ppo_update_timesteps=1_000)
    assert result["status"] in {"birth_completed", "completed", "practice_completed"}
    assert trainer.create_policy_calls
    assert trainer.create_policy_calls[0] is True


@pytest.mark.unit
def test_birth_engine_interleaves_ppo_updates_and_rolls_policy_between_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trainer = _FakePpoTrainer()
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0, "bid": 4999.875, "ask": 5000.125, "volume": 10}]
    monkeypatch.setattr(engine, "_load_training_ticks", lambda **_kwargs: ticks)

    seen_policies: list[str] = []

    def _chunk(*, ticks, chunk_trades, policy, **kwargs):
        seen_policies.append(str(policy.get("policy", "missing")) if isinstance(policy, dict) else "unknown")
        trajectories = [{"reward": 1.0} for _ in range(300)]
        return {
            "trades": chunk_trades,
            "total_pnl": 1.0,
            "winrate": 0.5,
            "trajectories": trajectories,
            "pnl_series": [1.0],
        }

    monkeypatch.setattr(engine, "_simulate_chunk_with_policy", _chunk)

    result = engine.run_birth_phase(
        target_trades=9_000,
        max_real_days=30,
        prefer_real_data_only=False,
        chunk_size=3_000,
        ppo_update_timesteps=1_000,
    )

    assert result["status"] in {"birth_completed", "completed", "practice_completed"}
    assert seen_policies[:3] == ["fresh", "updated_1", "updated_2"]
    assert trainer.update_calls >= 3
    assert result["ppo_steps"] >= 3_000 + 50_000

    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert int(progress.get("ppo_steps", 0) or 0) >= 3_000
    assert int(progress.get("ppo_steps_cumulative", 0) or 0) >= 3_000
    assert int(progress.get("ppo_batch_count", 0) or 0) >= 3


@pytest.mark.unit
def test_check_exit_uses_tick_distance_for_time_exit(tmp_path: Path) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=_FakePpoTrainer(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    position = {
        "side": "BUY",
        "entry_price": 5000.0,
        "qty": 1,
        "stop": 4900.0,
        "target": 5100.0,
        "entry_idx": 1,
    }
    exited, pnl, reason = engine._check_exit(
        position=position,
        tick={"last": 5000.5},
        current_entry_index=43,
    )
    assert exited is True
    assert reason == "time_exit"
    assert float(pnl) > 0.0
