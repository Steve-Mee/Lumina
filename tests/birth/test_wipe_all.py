"""Tests for POST /api/birth/wipe-all and birth training reset SSOT."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from lumina_launcher.core.birth_reset import clear_birth_training_state
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.birth_service import BirthService

birth_runner_start_module = importlib.import_module("lumina_launcher.services.birth_runner_start")
birth_runner_wipe_module = importlib.import_module("lumina_launcher.services.birth_runner_wipe")


@pytest.fixture(autouse=True)
def _reset_birth_service_singleton() -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    yield
    BirthService._instance = None  # type: ignore[attr-defined]


def _touch(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    state.mkdir()
    ppo = tmp_path / "lumina_agents" / "ppo"
    ppo.mkdir(parents=True)
    journal = tmp_path / "journal" / "simulator"
    journal.mkdir(parents=True)
    logs = tmp_path / "logs"
    logs.mkdir()
    lumina_os_logs = tmp_path / "lumina_os" / "logs"
    lumina_os_logs.mkdir(parents=True)
    lumina_os_state = tmp_path / "lumina_os" / "state"
    lumina_os_state.mkdir(parents=True)

    _touch(state / "lumina_birth_progress.json", '{"stage":"interrupted","cumulative_trades":42}')
    _touch(state / "lumina_birth_checkpoint.json", "{}")
    _touch(state / "lumina_birth_buffer.jsonl", "{}\n")
    _touch(state / "lumina_birth_ticks_cache.jsonl", "{}\n")
    _touch(state / "lumina_birth_split_cache.json", "{}")
    _touch(state / "birth_news_cache.json", "{}")
    _touch(state / "birth_runner.json", "{}")
    _touch(state / "ppo_policy_metadata.json", "{}")
    _touch(state / "hardware_profile.json", "{}")
    _touch(state / "birth_regime_prior.json", "{}")
    _touch(state / "ppo_training_log.jsonl", "{}\n")
    _touch(state / "monitoring_debug_training_process.json", "{}")
    _touch(state / "monitoring_runtime_metrics.json", "{}")
    _touch(state / "monitoring_twin_training.jsonl", "{}\n")
    _touch(state / "lumina_birth_completed.flag", "done")
    _touch(state / "lumina_birth_certificate.json", "{}")
    _touch(ppo / "lumina_ppo_policy.zip", "zip")
    _touch(ppo / "lumina_ppo_policy_practice.zip", "zip")
    _touch(ppo / "lumina_ppo_policy_birth_500.zip", "zip")
    _touch(journal / "lumina_birth_training_1.json", "{}")
    _touch(logs / "lumina_full_log.csv", "event\n")
    _touch(lumina_os_logs / "ui.log", "log")
    _touch(lumina_os_state / "metrics.db", "db")
    _touch(state / "first_boot_user_configured.flag", "1")
    _touch(state / "lumina_setup_complete.json", "{}")
    return tmp_path


def test_clear_birth_training_state_removes_full_checklist(workspace: Path) -> None:
    result = clear_birth_training_state(workspace, wipe_genesis=True)

    assert result.success is True
    assert not (workspace / "state" / "lumina_birth_progress.json").exists()
    assert not (workspace / "state" / "lumina_birth_buffer.jsonl").exists()
    assert not (workspace / "state" / "lumina_birth_ticks_cache.jsonl").exists()
    assert not (workspace / "state" / "birth_runner.json").exists()
    assert not (workspace / "state" / "hardware_profile.json").exists()
    assert not (workspace / "state" / "birth_regime_prior.json").exists()
    assert not (workspace / "lumina_agents" / "ppo" / "lumina_ppo_policy_birth_500.zip").exists()
    assert not (workspace / "journal" / "simulator" / "lumina_birth_training_1.json").exists()
    assert not (workspace / "logs" / "lumina_full_log.csv").exists()
    assert not (workspace / "lumina_os" / "state" / "metrics.db").exists()
    assert not (workspace / "state" / "first_boot_user_configured.flag").exists()
    assert not (workspace / "state" / "lumina_setup_complete.json").exists()


def test_clear_all_birth_artifacts_delegates_to_ssot(workspace: Path) -> None:
    manager = FirstBootManager(workspace)
    removed = manager.clear_all_birth_artifacts()

    assert not (workspace / "state" / "lumina_birth_progress.json").exists()
    assert not (workspace / "state" / "lumina_birth_ticks_cache.jsonl").exists()
    assert not (workspace / "state" / "lumina_birth_buffer.jsonl").exists()
    assert (workspace / "state" / "lumina_setup_complete.json").exists()
    assert len(removed) > 0


def test_wipe_all_birth_data_service(workspace: Path) -> None:
    svc = BirthService()
    svc.configure_workspace(workspace)
    svc._result = {"status": "completed", "message": "done"}
    result = svc.wipe_all_birth_data()
    assert result["status"] == "wiped"
    assert result["checkpoint_resumable"] is False
    assert not (workspace / "state" / "lumina_birth_progress.json").exists()
    status = svc.get_status()
    assert status["status"] == "idle"
    assert svc._result is None


def test_wipe_all_endpoint_handler_has_required_imports() -> None:
    """Regression: extracted actions module must bind logger/asyncio/_enrich_status.

    Missing imports caused NameError → HTTP 500 on Genesis 'Volledige wipe'.
    """
    mod = importlib.import_module("lumina_os.backend.birth_endpoints_actions")
    assert hasattr(mod, "logger")
    assert hasattr(mod, "asyncio")
    assert callable(mod._enrich_status)
    assert callable(mod.wipe_all_birth_data)


def test_wipe_all_endpoint_handler_success_and_confirm_guard() -> None:
    """POST /api/birth/wipe-all handler must not raise NameError (Internal Server Error)."""
    from lumina_os.backend import birth_endpoints_actions as actions

    with pytest.raises(HTTPException) as missing_confirm:
        asyncio.run(actions.wipe_all_birth_data(confirm=False, preserve_tick_cache=False))
    assert missing_confirm.value.status_code == 400

    fake_result = {
        "status": "wiped",
        "message": "ok",
        "removed_artifacts": ["state/lumina_birth_progress.json"],
        "checkpoint_resumable": False,
    }
    mock_svc = MagicMock()
    mock_svc.workspace_root = Path(".")
    mock_svc.wipe_all_birth_data.return_value = fake_result

    with (
        patch.object(actions, "birth_service", mock_svc),
        patch.object(actions, "_invalidate_enrich_artifact_cache") as inv,
    ):
        result = asyncio.run(
            actions.wipe_all_birth_data(confirm=True, preserve_tick_cache=False)
        )

    assert result["status"] == "wiped"
    mock_svc.wipe_all_birth_data.assert_called_once_with(preserve_tick_cache=False)
    inv.assert_called_once()


def test_retry_birth_wipe_parity_with_wipe_all(workspace: Path) -> None:
    svc = BirthService()
    svc.configure_workspace(workspace)
    svc._result = {"status": "certificate_failed"}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        birth_runner_start_module,
        "start_birth",
        lambda _svc, **kwargs: {"status": "started"},
    )
    try:
        result = svc.retry_birth(target_trades=10000, wipe=True)
    finally:
        monkeypatch.undo()

    assert result["status"] == "started"
    assert not (workspace / "state" / "lumina_birth_progress.json").exists()
    assert not (workspace / "state" / "hardware_profile.json").exists()
    assert not (workspace / "state" / "lumina_birth_ticks_cache.jsonl").exists()
    assert svc._result is None


def test_wipe_all_birth_data_with_orphan_runner_lock(workspace: Path) -> None:
    svc = BirthService()
    svc.configure_workspace(workspace)
    lock = workspace / "state" / "birth_runner.json"
    lock.write_text("{}", encoding="utf-8")

    result = svc.wipe_all_birth_data()

    assert result["status"] == "wiped"
    assert not lock.exists()
    assert not (workspace / "state" / "lumina_birth_progress.json").exists()


def test_clear_birth_training_state_removes_birth_best_policies(workspace: Path) -> None:
    ppo = workspace / "lumina_agents" / "ppo"
    _touch(ppo / "birth_best_stage1_trend.zip", "zip")
    _touch(ppo / "birth_best_stage2_range.zip", "zip")

    result = clear_birth_training_state(workspace, wipe_genesis=False)

    assert result.success is True
    assert not (ppo / "birth_best_stage1_trend.zip").exists()
    assert not (ppo / "birth_best_stage2_range.zip").exists()


def test_wipe_rejected_when_thread_still_running(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = BirthService()
    svc.configure_workspace(workspace)

    class _AliveThread:
        def is_alive(self) -> bool:
            return True

    svc._thread = _AliveThread()  # type: ignore[assignment]
    monkeypatch.setattr(
        birth_runner_start_module,
        "stop_birth",
        lambda _svc, **kwargs: {"status": "stopping"},
    )

    result = svc.wipe_all_birth_data()
    assert result["status"] == "rejected"
    assert (workspace / "state" / "lumina_birth_progress.json").exists()


def test_clear_orphan_runner_lock_for_wipe_clears_lock_without_pid(workspace: Path) -> None:
    svc = BirthService()
    svc.configure_workspace(workspace)
    lock = workspace / "state" / "birth_runner.json"
    lock.write_text("{}", encoding="utf-8")

    svc._clear_orphan_runner_lock_for_wipe()

    assert not lock.exists()


def test_ensure_birth_stopped_rejects_when_runner_still_live(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = BirthService()
    svc.configure_workspace(workspace)
    monkeypatch.setattr(
        birth_runner_start_module,
        "stop_birth",
        lambda _svc, **kwargs: {"status": "stopped"},
    )
    monkeypatch.setattr(svc, "_clear_orphan_runner_lock_for_wipe", lambda: None)
    monkeypatch.setattr(
        birth_runner_wipe_module,
        "birth_training_is_live",
        lambda *args, **kwargs: True,
    )

    result = svc._ensure_birth_stopped_for_wipe(join_timeout=0.05)

    assert result is not None
    assert result["status"] == "rejected"
    assert "runner" in result["message"].lower() or "lock" in result["message"].lower()
