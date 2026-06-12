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
from lumina_os.monitoring.dashboard_helpers import training_active_from_state
from lumina_core.birth.history_loader import load_historical_ticks
from lumina_core.birth.progress import write_birth_progress
from lumina_launcher.core.birth_actions import resolve_command_center_birth_flags


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
def test_history_chunk_callback_writes_progress(tmp_path: Path) -> None:
    write_birth_progress(
        tmp_path,
        stage="loading_data",
        phase="loading_history",
        message="Loading chunk 2/4",
        progress_pct=12.0,
        loading_chunk=2,
        chunk_total=4,
        bars_loaded=1200,
        chunk_bars=300,
    )
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress.get("loading_chunk") == 2
    assert progress.get("bars_loaded") == 1200


@pytest.mark.unit
def test_expand_chunk_writes_expanding_ticks_phase(tmp_path: Path) -> None:
    write_birth_progress(
        tmp_path,
        stage="historical_loaded",
        phase="ticks_ready",
        message="Ticks ready after expand",
        progress_pct=20.0,
        actual_real_days_loaded=8,
        chunk_phase="expand",
        loading_chunk=500,
        chunk_total=8000,
    )
    progress = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert progress.get("stage") == "historical_loaded"
    assert progress.get("phase") == "ticks_ready"
    assert int(progress.get("actual_real_days_loaded", 0) or 0) >= 1


@pytest.mark.unit
def test_birth_historical_limit_passed_to_market_data() -> None:
    seen_limits: list[int | None] = []

    def _fake_extended(**kwargs):
        seen_limits.append(kwargs.get("limit"))
        return []

    mds = SimpleNamespace(load_historical_ohlc_extended=_fake_extended)
    load_historical_ticks(
        market_data_service=mds,
        runtime=SimpleNamespace(),
        days_back=30,
        limit=None,
    )
    assert seen_limits == [None]
