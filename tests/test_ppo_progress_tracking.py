from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.infinite_simulator import InfiniteSimulator
from lumina_core.ppo_trainer import _notify_first_boot_ppo_progress


def test_notify_first_boot_ppo_progress_writes_expected_fields(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_write(stage: str, message: str, **extra: object) -> None:
        captured["stage"] = stage
        captured["message"] = message
        captured["extra"] = dict(extra)

    monkeypatch.setattr("lumina_core.engine.runtime_entrypoint._write_first_boot_progress", _fake_write)
    _notify_first_boot_ppo_progress(steps=120000, total_timesteps=300000, elapsed_sec=60.0)
    assert captured["stage"] == "training_running"
    extra = captured["extra"]
    assert extra["phase"] == "ppo_training"
    assert extra["ppo_steps"] == 120000
    assert extra["ppo_timesteps_total"] == 300000
    assert 39.9 <= float(extra["ppo_progress_pct"]) <= 40.1
    assert 68.0 <= float(extra["progress_pct"]) <= 95.0


def test_infinite_simulator_train_rl_enables_first_boot_progress(monkeypatch) -> None:
    class _TrainerStub:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def train_nightly_on_infinite_simulator(self, simulator_data: list[dict[str, Any]], **kwargs: Any) -> str:
            self.calls.append({"rows": len(simulator_data), "kwargs": dict(kwargs)})
            return "ok"

    trainer = _TrainerStub()
    sim = InfiniteSimulator.__new__(InfiniteSimulator)
    sim.ppo_trainer = trainer
    monkeypatch.setattr("lumina_core.infinite_simulator.ConfigLoader.section", lambda *args, **kwargs: {"ppo_progress_interval": 12000})
    sim._train_rl([{"x": i} for i in range(12)])
    assert len(trainer.calls) == 1
    kwargs = trainer.calls[0]["kwargs"]
    assert kwargs["report_first_boot_progress"] is True
    assert kwargs["ppo_progress_interval"] == 12000


def test_notify_first_boot_ppo_progress_writes_to_real_progress_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    progress_path = tmp_path / "state" / "first_boot_progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text('{"stage":"training_running","phase":"ppo_training"}', encoding="utf-8")
    monkeypatch.setattr(
        "lumina_core.engine.runtime_entrypoint.FIRST_BOOT_PROGRESS_PATH",
        progress_path,
    )
    _notify_first_boot_ppo_progress(steps=5000, total_timesteps=300000, elapsed_sec=12.0)
    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    assert payload["phase"] == "ppo_training"
    assert int(payload["ppo_steps"]) == 5000
    assert int(payload["ppo_timesteps_total"]) == 300000
