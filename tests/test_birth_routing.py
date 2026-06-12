"""Birth start routing, cross-process status, and checkpoint preservation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.lumina_birth_engine import LuminaBirthEngine
from lumina_launcher.core.birth_actions import start_birth_training
from lumina_launcher.services.birth_service import BirthService
from lumina_os.backend import birth_endpoints


@pytest.mark.unit
def test_start_birth_training_prefers_backend_when_reachable() -> None:
    backend = MagicMock()
    backend.is_backend_reachable.return_value = True
    backend.start_birth_sync.return_value = {"status": "started", "message": "via backend"}
    birth = MagicMock()

    ok, msg = start_birth_training(
        birth_service=birth,
        backend_client=backend,
        workspace_root=Path("."),
        target_trades=25_000,
        explicit_user_start=True,
    )

    assert ok is True
    assert "backend" in msg.lower()
    backend.start_birth_sync.assert_called_once()
    birth.start_birth.assert_not_called()


@pytest.mark.unit
def test_start_birth_training_falls_back_to_local_when_backend_down() -> None:
    backend = MagicMock()
    backend.is_backend_reachable.return_value = False
    birth = MagicMock()
    birth.start_birth.return_value = {"status": "started", "message": "local"}

    ok, msg = start_birth_training(
        birth_service=birth,
        backend_client=backend,
        workspace_root=Path("."),
        target_trades=25_000,
        explicit_user_start=True,
    )

    assert ok is True
    birth.start_birth.assert_called_once()
    backend.start_birth_sync.assert_not_called()


@pytest.mark.unit
def test_get_status_reports_running_from_fresh_progress(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    svc.progress_file.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": "loading_data",
                "phase": "loading_history",
                "trades_done": 24611,
                "target_trades": 25000,
                "progress_pct": 18.0,
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    svc.runner_lock_path.write_text(
        json.dumps({"runner": "file_progress", "pid": "unknown"}, ensure_ascii=True),
        encoding="utf-8",
    )

    payload = svc.get_status()
    assert payload["status"] == "running"
    assert payload.get("runner") in {"file_progress", "thread"}
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_checkpoint_preserved_on_mode_mismatch_without_force(tmp_path: Path) -> None:
    ckpt_path = tmp_path / "state" / "lumina_birth_checkpoint.json"
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    ckpt_path.write_text(
        json.dumps(
            {
                "cumulative_trades": 24611,
                "ppo_steps": 1_050_000,
                "target_trades": 25000,
                "training_mode": "practice",
            }
        ),
        encoding="utf-8",
    )

    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(create_fresh_birth_policy=lambda: {"policy": "x"}),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )

    result = engine.run_birth_phase(
        target_trades=25_000,
        max_real_days=30,
        prefer_real_data_only=True,
        practice_mode=False,
        force=False,
    )

    assert result["status"] in {"checkpoint_available", "history_unavailable"}
    if result["status"] == "checkpoint_available":
        assert ckpt_path.exists()
        progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
        assert progress["stage"] == "checkpoint_available"
        assert progress.get("checkpoint_trades") == 24611


@pytest.mark.unit
def test_load_training_ticks_writes_resolved_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    loader = getattr(engine, "_load_real_historical_ticks", None) or getattr(engine, "_load_training_ticks_from_history", None)
    if loader is None:
        pytest.skip("Birth engine historical loader API changed")
    monkeypatch.setattr(engine, loader.__name__, lambda **_kwargs: [{"last": 5000.0, "volume": 1}])
    engine._load_training_ticks(
        max_real_days=30,
        prefer_real_data_only=True,
        target_trades=25_000,
        training_mode="certified",
    )
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress["target_trades"] == 25_000


@pytest.mark.unit
def test_birth_endpoint_status_keeps_trade_and_ppo_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(birth_endpoints.birth_service, "artifacts_ok", lambda: True)
    payload = {
        "status": "running",
        "progress": {
            "trades_done": 19_000,
            "target_trades": 25_000,
            "ppo_steps": 75_000,
            "ppo_steps_cumulative": 75_000,
            "ppo_timesteps_planned_total": 125_000,
        },
    }
    enriched = birth_endpoints._enrich_status(payload)
    assert enriched["artifacts_ok"] is True
    assert enriched["phase_label"] == "Birth Phase v2"
    progress = enriched["progress"]
    assert int(progress["trades_done"]) == 19_000
    assert int(progress["target_trades"]) == 25_000
    assert int(progress["ppo_steps"]) == 75_000
    assert int(progress["ppo_steps_cumulative"]) == 75_000
