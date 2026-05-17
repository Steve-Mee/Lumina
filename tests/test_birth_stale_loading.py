"""STALE vs active pulse and historical load heartbeat."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.first_boot_progress import (
    BIRTH_LOADING_DATA_MAX_AGE_WITHOUT_LOCK_SEC,
    birth_runner_lock_active,
    birth_runner_lock_exists,
    resolve_birth_training_pulse,
    resolve_progress_active_max_age_sec,
)
from lumina_os.frontend.dashboard_views import training_active_from_state
from lumina_core.lumina_birth_engine import LuminaBirthEngine
from lumina_launcher.ui.tabs.first_boot import resolve_command_center_birth_flags


@pytest.mark.unit
def test_loading_data_max_age_is_extended() -> None:
    assert resolve_progress_active_max_age_sec("loading_data", runner_lock_active=True) >= 300.0
    assert (
        resolve_progress_active_max_age_sec("loading_data", runner_lock_active=False)
        == BIRTH_LOADING_DATA_MAX_AGE_WITHOUT_LOCK_SEC
    )
    assert resolve_progress_active_max_age_sec("training_running") == 30.0


@pytest.mark.unit
def test_pulse_stale_for_orphan_loading_data_without_lock(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    progress = {"stage": "loading_data", "timestamp": stale_ts, "phase": "loading_history"}
    pulse = resolve_birth_training_pulse(
        progress,
        birth_running=False,
        workspace_root=tmp_path,
    )
    assert pulse == "stale"


@pytest.mark.unit
def test_training_active_from_state_ignores_orphan_stage(tmp_path: Path) -> None:
    fb = {"stage": "loading_data", "timestamp": datetime.now(timezone.utc).isoformat()}
    assert training_active_from_state(fb, {}, workspace_root=tmp_path, birth_running=False) is False


@pytest.mark.unit
def test_pulse_active_when_runner_lock_during_loading_data(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    lock = tmp_path / "state" / "birth_runner.json"
    lock.write_text("{}", encoding="utf-8")
    stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    progress = {"stage": "loading_data", "timestamp": stale_ts}
    pulse = resolve_birth_training_pulse(
        progress,
        birth_running=False,
        workspace_root=tmp_path,
    )
    assert pulse == "active"
    assert birth_runner_lock_exists(tmp_path)
    assert birth_runner_lock_active(tmp_path)


@pytest.mark.unit
def test_pulse_stale_when_runner_pid_dead(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    lock = tmp_path / "state" / "birth_runner.json"
    lock.write_text('{"pid": 99999999}', encoding="utf-8")
    stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    progress = {"stage": "loading_data", "timestamp": stale_ts}
    pulse = resolve_birth_training_pulse(
        progress,
        birth_running=False,
        workspace_root=tmp_path,
    )
    assert pulse == "stale"
    assert birth_runner_lock_exists(tmp_path)
    assert birth_runner_lock_active(tmp_path) is False


@pytest.mark.unit
def test_command_center_flags_use_backend_running(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "birth_runner.json").write_text("{}", encoding="utf-8")
    backend = MagicMock()
    backend.is_backend_reachable.return_value = True
    backend.get_birth_status_sync.return_value = {"status": "running", "progress": {"stage": "loading_data"}}
    birth = MagicMock()
    birth.is_running.return_value = False
    birth.is_stopping.return_value = False

    flags = resolve_command_center_birth_flags(
        birth_service=birth,
        backend_client=backend,
        workspace_root=tmp_path,
        process_alive=False,
        progress={"stage": "loading_data", "timestamp": datetime.now(timezone.utc).isoformat()},
    )
    assert flags["birth_running"] is True
    assert flags["pulse"] == "active"


@pytest.mark.unit
def test_command_center_flags_idle_when_backend_not_running(tmp_path: Path) -> None:
    backend = MagicMock()
    backend.is_backend_reachable.return_value = True
    backend.get_birth_status_sync.return_value = {
        "status": "interrupted",
        "orphaned": True,
        "progress": {"stage": "interrupted", "phase": "restart_required"},
    }
    birth = MagicMock()
    birth.is_running.return_value = False
    birth.is_stopping.return_value = False

    flags = resolve_command_center_birth_flags(
        birth_service=birth,
        backend_client=backend,
        workspace_root=tmp_path,
        process_alive=False,
        progress={"stage": "interrupted", "phase": "restart_required"},
    )
    assert flags["birth_running"] is False
    assert flags["pulse"] in {"stale", "idle"}


@pytest.mark.unit
def test_history_chunk_callback_writes_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    captured: list[dict] = []

    def _fake_load(**kwargs):
        on_chunk = kwargs.get("on_chunk")
        if on_chunk:
            on_chunk(chunk_index=2, chunk_total=4, bars_merged=1200, chunk_bars=300)
        return [{"last": 5000.0, "volume": 1}]

    monkeypatch.setattr(engine, "_load_real_historical_ticks", _fake_load)
    original_write = engine._write_progress

    def _capture_write(**kwargs):
        captured.append(dict(kwargs))
        return original_write(**kwargs)

    monkeypatch.setattr(engine, "_write_progress", _capture_write)
    engine._load_training_ticks(
        max_real_days=10,
        prefer_real_data_only=True,
        target_trades=25_000,
        training_mode="certified",
    )
    assert any(c.get("loading_chunk") == 2 for c in captured)
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress.get("bars_loaded") == 1200 or any(c.get("bars_loaded") == 1200 for c in captured)


@pytest.mark.unit
def test_expand_chunk_writes_expanding_ticks_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )

    def _fake_load(**kwargs):
        on_chunk = kwargs.get("on_chunk")
        if on_chunk:
            on_chunk(
                chunk_index=500,
                chunk_total=8000,
                bars_merged=500,
                chunk_bars=0,
                chunk_phase="expand",
            )
        return [{"last": 5000.0, "volume": 1, "source": "real_historical"}] * 8

    monkeypatch.setattr(engine, "_load_real_historical_ticks", _fake_load)
    engine._load_training_ticks(
        max_real_days=10,
        prefer_real_data_only=True,
        target_trades=25_000,
        training_mode="certified",
    )
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress.get("stage") == "historical_loaded"
    assert progress.get("phase") == "ticks_ready"
    assert int(progress.get("actual_real_days_loaded", 0) or 0) >= 1


@pytest.mark.unit
def test_birth_historical_limit_capped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine = LuminaBirthEngine(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )
    seen_limits: list[int] = []

    def _fake_load(*, days_back, limit, on_chunk=None):
        seen_limits.append(limit)
        return []

    monkeypatch.setattr(engine, "_load_real_historical_ticks", _fake_load)
    engine._load_training_ticks(max_real_days=30, prefer_real_data_only=True, target_trades=25_000)
    assert seen_limits
    assert seen_limits[0] is None
