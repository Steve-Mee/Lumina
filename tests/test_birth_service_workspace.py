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
from tests.birth.test_certificate_fast_path import _seed_certificate_failed_checkpoint

birth_service_module = importlib.import_module("lumina_launcher.services.birth_service")
birth_runner_module = importlib.import_module("lumina_launcher.services.birth_runner")
birth_runner_start_module = importlib.import_module("lumina_launcher.services.birth_runner_start")
birth_runner_wipe_module = importlib.import_module("lumina_launcher.services.birth_runner_wipe")
birth_status_enricher_module = importlib.import_module(
    "lumina_launcher.services.birth_status_enricher"
)


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
def test_artifacts_ok_requires_v2_certificate_and_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timezone

    from lumina_core.birth.birth_certificate import BirthCertificateV2, sha256_file, write_certificate

    monkeypatch.delenv("LUMINA_BIRTH_V2_DISABLED", raising=False)
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    assert svc.artifacts_ok() is False
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    svc.completed_flag.write_text("done", encoding="utf-8")
    assert svc.artifacts_ok() is False
    policy = svc.policy_path
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_bytes(b"zip")
    assert svc.artifacts_ok() is False
    cert = BirthCertificateV2(
        issued_at=datetime.now(timezone.utc),
        policy_path=str(policy),
        policy_sha256=sha256_file(policy),
        real_data_pct=99.0,
        oos_winrate=0.5,
        oos_sharpe=0.4,
        oos_max_drawdown_pct=4.0,
        constitution_violations=0,
        regimes_covered=["TREND_UP", "TREND_DOWN", "NEUTRAL"],
        curriculum_stages_passed=["stage1_trend", "stage2_range", "stage3_mixed", "stage4_polish"],
        holdout_days=5,
        holdout_trades=60,
        training_trades=500,
        ppo_steps=1000,
    )
    write_certificate(tmp_path, cert)
    assert svc.artifacts_ok() is True
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_is_completed_requires_valid_certificate(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    assert svc.is_completed() is False
    svc.completed_flag.write_text("done", encoding="utf-8")
    assert svc.is_completed() is False
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_get_status_running_before_stale_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    svc.completed_flag.write_text("done", encoding="utf-8")
    monkeypatch.setattr(svc, "is_running", lambda: True)
    status = svc.get_status()
    assert status["status"] == "running"
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_retry_birth_wipe_clears_stale_flag_and_starts_with_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    svc.completed_flag.write_text("done", encoding="utf-8")
    calls: list[dict[str, object]] = []

    def _fake_start(_svc: BirthService, **kwargs: object) -> dict[str, str]:
        calls.append(dict(kwargs))
        return {"status": "started", "message": "ok"}

    monkeypatch.setattr(birth_runner_start_module, "start_birth", _fake_start)
    result = svc.retry_birth(target_trades=10000, wipe=True)
    assert result["status"] == "started"
    assert not svc.completed_flag.exists()
    assert calls
    assert calls[0]["force"] is True
    assert calls[0]["continue_training"] is False
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_retry_birth_preserves_checkpoint_on_certificate_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    _seed_certificate_failed_checkpoint(tmp_path)
    calls: list[dict[str, object]] = []

    def _fake_start(_svc: BirthService, **kwargs: object) -> dict[str, str]:
        calls.append(dict(kwargs))
        return {"status": "started", "message": "ok"}

    monkeypatch.setattr(birth_runner_start_module, "start_birth", _fake_start)
    monkeypatch.setattr(
        "lumina_launcher.core.first_boot.FirstBootManager.clear_stale_for_certified_retry",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should not wipe")),
    )
    result = svc.retry_birth(target_trades=10000, wipe=False)
    assert result["status"] == "started"
    assert calls
    assert calls[0]["force"] is False
    assert calls[0]["continue_training"] is True
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_get_status_flag_without_certificate_reports_certificate_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    svc.completed_flag.write_text("done", encoding="utf-8")
    status = svc.get_status()
    assert status["status"] == "certificate_failed"
    assert svc.certificate_ok() is False
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_get_status_stage_stalled_from_progress_file(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    svc.progress_file.parent.mkdir(parents=True, exist_ok=True)
    svc.progress_file.write_text(
        json.dumps(
            {
                "stage": "stage_stalled",
                "phase": "stage_stalled",
                "pass_reason": "winrate 13.0% < 45%",
                "progress_pct": 68.0,
                "curriculum_stage": "stage1_trend",
            }
        ),
        encoding="utf-8",
    )
    status = svc.get_status()
    assert status["status"] == "stage_stalled"
    assert "13.0%" in str(status.get("message"))
    assert status.get("live") is False
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_get_status_certificate_failed_without_completion_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    monkeypatch.setattr(svc, "_maybe_execute_autonomous_recovery", lambda: None)
    monkeypatch.setattr(svc, "_maybe_auto_resume_stalled_birth", lambda: None)
    svc.progress_file.parent.mkdir(parents=True, exist_ok=True)
    svc.progress_file.write_text(
        json.dumps(
            {
                "stage": "failed",
                "phase": "certificate_failed",
                "message": "Birth Certificate v2 thresholds not met after remediation.",
                "failure_reasons": ["holdout_trades:12/50"],
                "stages_passed": ["stage1_trend", "stage2_range", "stage3_mixed"],
            }
        ),
        encoding="utf-8",
    )
    status = svc.get_status()
    assert status["status"] == "certificate_failed"
    assert "thresholds" in str(status.get("message", "")).lower()
    assert status.get("live") is False
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_get_status_includes_launcher_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    monkeypatch.setattr(
        birth_status_enricher_module,
        "launcher_setup_status_payload",
        lambda workspace_root: {
            "setup_complete": False,
            "intelligence_stack_ready": True,
            "needs_smart_setup": False,
            "needs_guided_setup": True,
            "launcher_ready": False,
            "recommended_model": "qwen3.5-9b",
            "recommended_provider": "ollama",
            "recommended_ollama_tag": "qwen3.5:9b",
            "missing": ["setup_complete"],
        },
    )
    status = svc.get_status()
    assert "launcher_setup" in status
    assert status["launcher_setup"]["needs_guided_setup"] is True
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_configure_birth_workspace_module_helper(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    out = configure_birth_workspace(tmp_path)
    assert out == tmp_path.resolve()
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_preflight_historical_data_does_not_raise_name_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression: preflight must not crash with NameError (missing import os)."""
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "first_boot:\n  max_real_days: 30\n",
        encoding="utf-8",
    )

    class _FakeMds:
        def load_historical_ohlc_extended(self, **_kwargs: object) -> list[dict[str, int]]:
            return [{"t": 1}]

    class _FakeContainer:
        def __init__(self) -> None:
            self.engine = SimpleNamespace()
            self.market_data_service = _FakeMds()
            self.runtime_context = SimpleNamespace(app=None)

    monkeypatch.setattr(birth_runner_start_module, "ApplicationContainer", _FakeContainer)
    monkeypatch.setattr(birth_runner_start_module, "_bind_headless_runtime_app", lambda _c: None)

    ok, msg = svc._preflight_historical_data(30)
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    assert ok is True
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

    monkeypatch.setattr(birth_runner_start_module, "ApplicationContainer", _FakeContainer)
    monkeypatch.setattr(birth_runner_start_module, "_bind_headless_runtime_app", lambda _c: None)
    monkeypatch.setattr(birth_runner_start_module, "LuminaBirthEngine", _FakeEngine)

    def _preflight_ok(_svc: BirthService, _days: int) -> tuple[bool, str]:
        return True, ""

    monkeypatch.setattr(birth_runner_start_module, "preflight_historical_data", _preflight_ok)

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
    assert run_kwargs.get("target_trades") == 9000
    assert run_kwargs.get("practice_mode") is False
    assert run_kwargs.get("reuse_existing_policy") is False
    engine_kwargs = captured.get("engine_kwargs")
    assert isinstance(engine_kwargs, dict)
    assert engine_kwargs.get("config", {}).get("first_boot", {}).get("training_trades") == 9000
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_start_birth_uses_saved_target_when_request_omits_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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

    monkeypatch.setattr(birth_runner_start_module, "ApplicationContainer", _FakeContainer)
    monkeypatch.setattr(birth_runner_start_module, "_bind_headless_runtime_app", lambda _c: None)
    monkeypatch.setattr(birth_runner_start_module, "LuminaBirthEngine", _FakeEngine)
    monkeypatch.setattr(
        birth_runner_start_module,
        "preflight_historical_data",
        lambda _svc, _days: (True, ""),
    )

    result = svc.start_birth(
        target_trades=None, force=True, practice_mode=False, explicit_user_start=True
    )
    assert result["status"] == "started"
    assert svc._thread is not None  # type: ignore[attr-defined]
    svc._thread.join(timeout=1.0)  # type: ignore[attr-defined]
    run_kwargs = captured.get("run_kwargs")
    assert isinstance(run_kwargs, dict)
    assert run_kwargs.get("target_trades") == 12000
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_start_birth_uses_configured_ppo_update_timesteps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.yaml").write_text(
        "first_boot:\n  training_trades: 12000\n  prefer_real_data_only: true\n  max_real_days: 40\n  ppo_update_timesteps: 12345\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class _FakeEngine:
        def __init__(self, **_kwargs) -> None:
            pass

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

    monkeypatch.setattr(birth_runner_start_module, "ApplicationContainer", _FakeContainer)
    monkeypatch.setattr(birth_runner_start_module, "_bind_headless_runtime_app", lambda _c: None)
    monkeypatch.setattr(birth_runner_start_module, "LuminaBirthEngine", _FakeEngine)
    monkeypatch.setattr(
        birth_runner_start_module,
        "preflight_historical_data",
        lambda _svc, _days: (True, ""),
    )

    result = svc.start_birth(
        target_trades=None, force=True, practice_mode=False, explicit_user_start=True
    )
    assert result["status"] == "started"
    assert svc._thread is not None  # type: ignore[attr-defined]
    svc._thread.join(timeout=1.0)  # type: ignore[attr-defined]
    run_kwargs = captured.get("run_kwargs")
    assert isinstance(run_kwargs, dict)
    assert run_kwargs.get("ppo_update_timesteps") == 12345
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

    monkeypatch.setattr(birth_runner_start_module, "ApplicationContainer", _FakeContainer)
    monkeypatch.setattr(birth_runner_start_module, "_bind_headless_runtime_app", lambda _c: None)
    monkeypatch.setattr(birth_runner_start_module, "LuminaBirthEngine", _FakeEngine)

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

    monkeypatch.setattr(birth_runner_start_module, "ApplicationContainer", _FakeContainer)
    monkeypatch.setattr(birth_runner_start_module, "_bind_headless_runtime_app", lambda _c: None)
    monkeypatch.setattr(birth_runner_start_module, "LuminaBirthEngine", _FakeEngine)
    monkeypatch.setattr(
        birth_runner_start_module,
        "preflight_historical_data",
        lambda _svc, _days: (True, ""),
    )

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
    assert "Hervat checkpoint" in str(reconciled.get("message", ""))
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_reconcile_orphaned_skips_attention_when_checkpoint_exists(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    orphan = {
        "timestamp": stale_ts,
        "stage": "training_running",
        "phase": "curriculum_learning",
        "target_trades": 25000,
        "trades_done": 140,
        "ppo_steps": 1500,
    }
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps(orphan, ensure_ascii=True),
        encoding="utf-8",
    )
    (tmp_path / "state" / "lumina_birth_checkpoint.json").write_text(
        json.dumps(
            {
                "version": 3,
                "ppo_steps": 1500,
                "cumulative_trades": 140,
                "curriculum_stage": "stage1_trend",
                "phase": "curriculum_learning",
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    reconciled = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert reconciled.get("stage") == "interrupted"
    assert not reconciled.get("needs_attention")
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_sanitize_running_progress_strips_stale_attention(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    progress = {
        "phase": "curriculum_learning",
        "stage": "training_running",
        "needs_attention": True,
        "attention_summary": "Vorige Birth Phase gestopt",
        "attention_reason_code": "birth_interrupted",
        "user_initiated_stop": True,
    }
    sanitized = svc._sanitize_running_progress(progress)
    assert "needs_attention" not in sanitized
    assert "attention_summary" not in sanitized
    assert sanitized.get("user_initiated_stop") is False
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
    import os

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
        json.dumps({"runner": "file_progress", "pid": os.getpid()}, ensure_ascii=True),
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
def test_stop_birth_sets_pause_flag_when_progress_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        '{"stage": "training_running", "timestamp": "2099-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(BirthService, "reconcile_orphaned_birth_progress", lambda self: False)
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    result = svc.stop_birth()
    assert result["status"] in {"stopping", "stopped"}
    progress = svc._load_progress()
    assert progress.get("user_initiated_stop") is True
    assert progress.get("phase") == "restart_required"
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_configure_workspace_auto_resumes_retryable_stage_stalled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    ws = tmp_path / "repo"
    state = ws / "state"
    state.mkdir(parents=True)
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "stage": "stage_stalled",
                "phase": "stage_stalled",
                "retryable": True,
                "message": "winrate 23.6% < 45%",
            }
        ),
        encoding="utf-8",
    )
    (state / "lumina_birth_checkpoint.json").write_text(
        json.dumps({"phase": "stage_stalled", "version": 3}),
        encoding="utf-8",
    )
    calls = {"n": 0}

    def _fake_resume(target_trades: int | None = None) -> dict[str, str]:
        _ = target_trades
        calls["n"] += 1
        return {"status": "started"}

    svc = BirthService()
    monkeypatch.setattr(svc, "resume_stalled_stage", _fake_resume)
    svc.configure_workspace(ws)
    assert calls["n"] == 1
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_auto_resume_allowed_for_plateau_evolution_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    ws = tmp_path / "repo"
    state = ws / "state"
    state.mkdir(parents=True)
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "stage": "training_running",
                "phase": "plateau_evolution",
                "retryable": True,
                "needs_attention": True,
                "terminal_stall_reason": "plateau_evolution_exhausted",
            }
        ),
        encoding="utf-8",
    )
    (state / "lumina_birth_checkpoint.json").write_text(
        json.dumps({"phase": "plateau_evolution", "version": 3}),
        encoding="utf-8",
    )
    calls = {"n": 0}

    def _fake_resume(target_trades: int | None = None) -> dict[str, str]:
        _ = target_trades
        calls["n"] += 1
        return {"status": "started"}

    svc = BirthService()
    monkeypatch.setattr(svc, "resume_stalled_stage", _fake_resume)
    svc.configure_workspace(ws)
    assert calls["n"] == 1
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_auto_resume_blocked_for_needs_attention(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    ws = tmp_path / "repo"
    state = ws / "state"
    state.mkdir(parents=True)
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "stage": "stage_stalled",
                "phase": "stage_stalled",
                "retryable": False,
                "needs_attention": True,
                "terminal_stall_reason": "stall_remediation_exhausted",
            }
        ),
        encoding="utf-8",
    )
    (state / "lumina_birth_checkpoint.json").write_text(
        json.dumps({"phase": "stage_stalled", "version": 3}),
        encoding="utf-8",
    )
    calls = {"n": 0}

    def _fake_resume(target_trades: int | None = None) -> dict[str, str]:
        _ = target_trades
        calls["n"] += 1
        return {"status": "started"}

    svc = BirthService()
    monkeypatch.setattr(svc, "resume_stalled_stage", _fake_resume)
    svc.configure_workspace(ws)
    assert calls["n"] == 0
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_auto_resume_allowed_for_plateau_exhausted_when_autonomous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    ws = tmp_path / "repo"
    state = ws / "state"
    state.mkdir(parents=True)
    (ws / "config.yaml").write_text(
        "birth_v2:\n  curriculum:\n    autonomous_recovery_enabled: true\n",
        encoding="utf-8",
    )
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "stage": "stage_stalled",
                "phase": "stage_stalled",
                "retryable": True,
                "terminal_stall_reason": "plateau_evolution_exhausted",
            }
        ),
        encoding="utf-8",
    )
    (state / "lumina_birth_checkpoint.json").write_text(
        json.dumps({"phase": "stage_stalled", "version": 3}),
        encoding="utf-8",
    )
    calls = {"n": 0}

    def _fake_resume(target_trades: int | None = None) -> dict[str, str]:
        _ = target_trades
        calls["n"] += 1
        return {"status": "started"}

    svc = BirthService()
    monkeypatch.setattr(svc, "resume_stalled_stage", _fake_resume)
    svc.configure_workspace(ws)
    assert calls["n"] == 1
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_auto_resume_blocked_for_plateau_exhausted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    ws = tmp_path / "repo"
    state = ws / "state"
    state.mkdir(parents=True)
    (ws / "config.yaml").write_text(
        "birth_v2:\n  curriculum:\n    autonomous_recovery_enabled: false\n",
        encoding="utf-8",
    )
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "stage": "stage_stalled",
                "phase": "stage_stalled",
                "retryable": True,
                "terminal_stall_reason": "plateau_evolution_exhausted",
            }
        ),
        encoding="utf-8",
    )
    (state / "lumina_birth_checkpoint.json").write_text(
        json.dumps({"phase": "stage_stalled", "version": 3}),
        encoding="utf-8",
    )
    calls = {"n": 0}

    def _fake_resume(target_trades: int | None = None) -> dict[str, str]:
        _ = target_trades
        calls["n"] += 1
        return {"status": "started"}

    svc = BirthService()
    monkeypatch.setattr(svc, "resume_stalled_stage", _fake_resume)
    svc.configure_workspace(ws)
    assert calls["n"] == 0
    BirthService._instance = None  # type: ignore[attr-defined]
