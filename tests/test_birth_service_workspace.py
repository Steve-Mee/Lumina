"""BirthService workspace resolution — must not depend on process cwd."""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_launcher.services.birth_service import (
    BirthService,
    configure_birth_workspace,
    resolve_birth_workspace_root,
)

birth_service_module = importlib.import_module("lumina_launcher.services.birth_service")


@pytest.mark.unit
def test_resolve_birth_workspace_root_defaults_to_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUMINA_WORKSPACE_ROOT", raising=False)
    root = resolve_birth_workspace_root()
    assert (root / "lumina_launcher").is_dir()
    assert root == resolve_birth_workspace_root(None)


@pytest.mark.unit
def test_resolve_birth_workspace_root_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = tmp_path / "custom_ws"
    ws.mkdir()
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(ws))
    assert resolve_birth_workspace_root() == ws.resolve()


@pytest.mark.unit
def test_configure_birth_workspace_updates_paths(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    ws = tmp_path / "repo"
    (ws / "state").mkdir(parents=True)
    svc.configure_workspace(ws)
    assert svc.workspace_root == ws.resolve()
    assert svc.progress_file == ws / "state" / "lumina_birth_progress.json"
    assert svc.policy_path == ws / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_artifacts_ok_requires_flag_and_policy(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    assert svc.artifacts_ok() is False
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    svc.completed_flag.write_text("done", encoding="utf-8")
    assert svc.artifacts_ok() is False
    policy_dir = tmp_path / "lumina_agents" / "ppo"
    policy_dir.mkdir(parents=True)
    (policy_dir / "lumina_ppo_policy.zip").write_bytes(b"zip")
    assert svc.artifacts_ok() is True
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_configure_birth_workspace_module_helper(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    out = configure_birth_workspace(tmp_path)
    assert out == tmp_path.resolve()
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_start_birth_wires_container_dependencies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.yaml").write_text(
        "first_boot:\n  training_trades: 12000\n  prefer_real_data_only: true\n  max_real_days: 40\n",
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    class _FakeEngine:
        def __init__(self, **kwargs) -> None:
            captured["engine_kwargs"] = kwargs

        def run_birth_phase(self, **kwargs):
            captured["run_kwargs"] = kwargs
            return {"status": "history_unavailable", "message": "no data", "total_trades": 0}

    class _FakeContainer:
        def __init__(self) -> None:
            self.engine = SimpleNamespace()
            self.ppo_trainer = object()
            self.market_data_service = object()
            self.runtime_context = SimpleNamespace(app=None)
            self.logger = SimpleNamespace(info=lambda *a, **k: None)

    monkeypatch.setattr(birth_service_module, "ApplicationContainer", _FakeContainer)
    monkeypatch.setattr(birth_service_module, "_bind_headless_runtime_app", lambda _c: None)
    monkeypatch.setattr(birth_service_module, "LuminaBirthEngine", _FakeEngine)

    def _preflight_ok(_days: int) -> tuple[bool, str]:
        return True, ""

    monkeypatch.setattr(svc, "_preflight_historical_data", _preflight_ok)

    result = svc.start_birth(
        target_trades=9000, force=True, practice_mode=False, explicit_user_start=True
    )
    assert result["status"] == "started"
    # Ensure background thread ran once.
    assert svc._thread is not None  # type: ignore[attr-defined]
    svc._thread.join(timeout=1.0)  # type: ignore[attr-defined]
    assert captured["engine_kwargs"] is not None
    run_kwargs = captured.get("run_kwargs")
    assert isinstance(run_kwargs, dict)
    assert run_kwargs.get("target_trades") == 12000
    assert run_kwargs.get("practice_mode") is False
    assert run_kwargs.get("reuse_existing_policy") is False
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_start_birth_practice_forces_non_real_data_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.yaml").write_text(
        "first_boot:\n  training_trades: 10000\n  prefer_real_data_only: true\n  max_real_days: 30\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class _FakeEngine:
        def __init__(self, **_kwargs) -> None:
            pass

        def run_birth_phase(self, **kwargs):
            captured["run_kwargs"] = kwargs
            return {"status": "practice_completed", "total_trades": 2500}

    class _FakeContainer:
        def __init__(self) -> None:
            self.engine = SimpleNamespace()
            self.ppo_trainer = object()
            self.market_data_service = object()
            self.runtime_context = SimpleNamespace(app=None)
            self.logger = SimpleNamespace(info=lambda *a, **k: None)

    monkeypatch.setattr(birth_service_module, "ApplicationContainer", _FakeContainer)
    monkeypatch.setattr(birth_service_module, "_bind_headless_runtime_app", lambda _c: None)
    monkeypatch.setattr(birth_service_module, "LuminaBirthEngine", _FakeEngine)

    result = svc.start_birth(
        target_trades=10000, force=True, practice_mode=True, explicit_user_start=True
    )
    assert result["status"] == "started"
    assert svc._thread is not None  # type: ignore[attr-defined]
    svc._thread.join(timeout=1.0)  # type: ignore[attr-defined]
    run_kwargs = captured.get("run_kwargs")
    assert isinstance(run_kwargs, dict)
    assert run_kwargs.get("prefer_real_data_only") is False
    assert run_kwargs.get("practice_mode") is True
    assert run_kwargs.get("reuse_existing_policy") is False
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_start_birth_continue_training_reuses_existing_policy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.yaml").write_text(
        "first_boot:\n  training_trades: 10000\n  prefer_real_data_only: true\n  max_real_days: 30\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class _FakeEngine:
        def __init__(self, **_kwargs) -> None:
            pass

        def run_birth_phase(self, **kwargs):
            captured["run_kwargs"] = kwargs
            return {"status": "completed", "total_trades": 10_000}

    class _FakeContainer:
        def __init__(self) -> None:
            self.engine = SimpleNamespace()
            self.ppo_trainer = object()
            self.market_data_service = object()
            self.runtime_context = SimpleNamespace(app=None)
            self.logger = SimpleNamespace(info=lambda *a, **k: None)

    monkeypatch.setattr(birth_service_module, "ApplicationContainer", _FakeContainer)
    monkeypatch.setattr(birth_service_module, "_bind_headless_runtime_app", lambda _c: None)
    monkeypatch.setattr(birth_service_module, "LuminaBirthEngine", _FakeEngine)
    monkeypatch.setattr(svc, "_preflight_historical_data", lambda _days: (True, ""))

    result = svc.start_birth(
        target_trades=10000,
        force=False,
        practice_mode=False,
        explicit_user_start=True,
        continue_training=True,
    )
    assert result["status"] == "started"
    assert svc._thread is not None  # type: ignore[attr-defined]
    svc._thread.join(timeout=1.0)  # type: ignore[attr-defined]
    run_kwargs = captured.get("run_kwargs")
    assert isinstance(run_kwargs, dict)
    assert run_kwargs.get("reuse_existing_policy") is True
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_stop_birth_not_running(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    result = svc.stop_birth()
    assert result["status"] == "not_running"
    assert not svc.pause_flag_path.exists()
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_reconcile_orphaned_marks_interrupted(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    orphan = {
        "timestamp": stale_ts,
        "stage": "loading_data",
        "phase": "loading_history",
        "target_trades": 25000,
        "trades_done": 0,
    }
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps(orphan, ensure_ascii=True),
        encoding="utf-8",
    )
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    reconciled = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert reconciled.get("stage") == "interrupted"
    assert reconciled.get("phase") == "restart_required"
    assert reconciled.get("prior_stage") == "loading_data"
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_get_status_idle_not_running_for_orphan_progress(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    status = svc.get_status()
    assert status["status"] in {"idle", "interrupted"}
    assert status.get("live") is False
    assert status["status"] != "running"
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_get_status_exposes_trade_and_ppo_progress_from_file(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": "training_running",
        "phase": "ppo_training",
        "trades_done": 15_000,
        "target_trades": 25_000,
        "progress_pct": 60.0,
        "ppo_steps": 50_000,
        "ppo_steps_cumulative": 50_000,
        "ppo_timesteps_planned_total": 125_000,
        "ppo_batch_count": 2,
    }
    svc.progress_file.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    svc.runner_lock_path.write_text(
        json.dumps({"runner": "file_progress", "pid": "unknown"}, ensure_ascii=True),
        encoding="utf-8",
    )

    status = svc.get_status()

    assert status["status"] == "running"
    progress = status.get("progress") or {}
    assert int(progress.get("trades_done", 0) or 0) == 15_000
    assert int(progress.get("target_trades", 0) or 0) == 25_000
    assert int(progress.get("ppo_steps", 0) or 0) == 50_000
    assert int(progress.get("ppo_steps_cumulative", 0) or 0) == 50_000
    assert int(progress.get("ppo_timesteps_planned_total", 0) or 0) == 125_000
    assert int(progress.get("ppo_batch_count", 0) or 0) == 2
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_stop_birth_sets_pause_flag_when_progress_active(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        '{"stage": "training_running", "timestamp": "2099-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    result = svc.stop_birth()
    assert result["status"] == "stopping"
    assert svc.pause_flag_path.exists()
    BirthService._instance = None  # type: ignore[attr-defined]
