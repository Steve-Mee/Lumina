"""Birth Phase: certified vs practice training_mode, checkpoints, UI warnings, preflight."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.lumina_birth_engine import LuminaBirthEngine
from lumina_launcher.services.birth_service import BirthService
from lumina_launcher.ui.tabs import first_boot as fb


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

    def save_intermediate_policy(self, _trades: int) -> None:
        return None


@pytest.mark.unit
def test_certified_start_sets_training_mode_certified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trainer = _FakePpoTrainer()
    ticks = [
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "last": 5000.0,
            "bid": 4999.875,
            "ask": 5000.125,
            "volume": 10,
            "source": "real_historical",
        }
        for _ in range(100)
    ]
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
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
    engine.run_birth_phase(
        target_trades=100,
        max_real_days=30,
        prefer_real_data_only=True,
        practice_mode=False,
        chunk_size=100,
        ppo_update_timesteps=1000,
    )
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress["training_mode"] == "certified"
    assert progress.get("certification_eligible") is True
    assert float(progress.get("real_data_pct", 0) or 0) > 0.0


@pytest.mark.unit
def test_practice_with_real_ticks_still_not_certified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trainer = _FakePpoTrainer()
    ticks = [
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "last": 5000.0,
            "bid": 4999.875,
            "ask": 5000.125,
            "volume": 10,
            "source": "real_historical",
        }
        for _ in range(50)
    ]
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    def _load_ticks(**_kwargs):
        engine._loaded_real_days = 5
        return ticks

    monkeypatch.setattr(engine, "_load_training_ticks", _load_ticks)
    monkeypatch.setattr(
        engine,
        "_simulate_chunk_with_policy",
        lambda *, ticks, chunk_trades, policy, **kwargs: {
            "trades": min(chunk_trades, 100),
            "total_pnl": 1.0,
            "winrate": 0.5,
            "trajectories": [{"reward": 1.0}],
            "pnl_series": [1.0],
        },
    )
    result = engine.run_birth_phase(
        target_trades=100,
        max_real_days=30,
        prefer_real_data_only=False,
        practice_mode=True,
        chunk_size=100,
        ppo_update_timesteps=1000,
    )
    assert result["training_mode"] == "practice"
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress["training_mode"] == "practice"
    assert progress.get("certification_eligible") is False
    assert int(progress.get("actual_real_days_loaded", 0) or 0) >= 1


@pytest.mark.unit
def test_checkpoint_mode_mismatch_blocks_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trainer = _FakePpoTrainer()
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=trainer,
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "lumina_birth_checkpoint.json").write_text(
        json.dumps(
            {
                "target_trades": 5000,
                "cumulative_trades": 4000,
                "ppo_steps": 10000,
                "training_mode": "practice",
            }
        ),
        encoding="utf-8",
    )
    ticks = [{"timestamp": "t", "last": 1.0, "bid": 0.9, "ask": 1.1, "volume": 1, "source": "real_historical"}] * 20
    monkeypatch.setattr(engine, "_load_training_ticks", lambda **_kwargs: ticks)
    monkeypatch.setattr(
        engine,
        "_simulate_chunk_with_policy",
        lambda *, ticks, chunk_trades, policy, **kwargs: {
            "trades": chunk_trades,
            "total_pnl": 0.0,
            "winrate": 0.0,
            "trajectories": [],
            "pnl_series": [],
        },
    )
    result = engine.run_birth_phase(
        target_trades=5000,
        practice_mode=False,
        chunk_size=5000,
        ppo_update_timesteps=1000,
    )
    assert result["status"] == "checkpoint_available"
    assert result.get("failure_reason") == "mode_mismatch"
    assert engine.cumulative_trades == 0


@pytest.mark.unit
def test_ui_warning_distinguishes_practice_with_real_days() -> None:
    source = Path(fb.__file__).read_text(encoding="utf-8")
    assert "_render_training_mode_warning" in source
    assert "Practice-run (niet certified voor live)" in source
    assert "zonder echte historische data" in source
    assert "_render_certified_data_metrics" in source


@pytest.mark.unit
def test_certified_preflight_rejects_empty_history(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "config.yaml").write_text("first_boot:\n  max_real_days: 30\n", encoding="utf-8")

    class _FakeMds:
        def load_historical_ohlc_extended(self, **_kwargs):
            return []

    class _FakeContainer:
        def __init__(self) -> None:
            self.engine = SimpleNamespace()
            self.market_data_service = _FakeMds()

    mod = importlib.import_module("lumina_launcher.services.birth_service")
    monkeypatch.setattr(mod, "ApplicationContainer", _FakeContainer)
    monkeypatch.setattr(mod, "_bind_headless_runtime_app", lambda _c: None)

    ok, msg = svc._preflight_historical_data(30)
    assert ok is False
    assert msg

    result = svc.start_birth(target_trades=5000, explicit_user_start=True, practice_mode=False)
    assert result["status"] == "rejected"
    assert "historische" in result["message"].lower() or "Geen" in result["message"]
    BirthService._instance = None  # type: ignore[attr-defined]
