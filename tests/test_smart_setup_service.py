from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from lumina_core.adaptive_intelligence import AdaptiveIntelligenceStatus
from lumina_core.engine.hardware_inspector import HardwareSnapshot
from lumina_core.engine.model_catalog import ModelDescriptor
from lumina_core.engine.setup_service import SetupStepResult
from lumina_launcher.services.smart_setup_service import (
    SetupProgressEvent,
    SmartSetupOptions,
    SmartSetupService,
    SubprocessStepResult,
)


def _make_intelligence_status(**overrides: Any) -> AdaptiveIntelligenceStatus:
    defaults = {
        "tier": "standard",
        "mode": "auto",
        "reasoning_mode": "hybrid_balanced",
        "degraded_state": False,
        "status_reason": "auto_hardware_resolution",
        "recommended_model": "qwen3.5-9b",
        "recommended_provider": "ollama",
        "context_length": 16384,
        "last_probe_error": None,
    }
    defaults.update(overrides)
    return AdaptiveIntelligenceStatus(**defaults)


def _make_descriptor() -> ModelDescriptor:
    return ModelDescriptor(
        key="qwen3.5-9b",
        display_name="Qwen3.5 9B Instruct",
        family="qwen3.5",
        ollama_tag="qwen3.5:9b",
        parameter_size_b=9.0,
        vram_min_gb=8.0,
        ram_min_gb=32.0,
        recommended_tier="sweet",
        recommended_provider="ollama",
        tested_by_lumina=True,
        upgrade_notes="",
        supports_unsloth=True,
        context_length=16384,
    )


def _make_hardware_snapshot() -> HardwareSnapshot:
    return HardwareSnapshot(
        os_name="Linux",
        os_version="test",
        cpu_name="cpu",
        cpu_cores_physical=8,
        cpu_cores_logical=16,
        ram_gb=64.0,
        gpu_name="RTX 4090",
        gpu_vram_gb=24.0,
        compute_capability=8.9,
        ollama_installed=True,
        ollama_running=True,
        nvidia_smi_available=True,
        vllm_supported=True,
        profile_tier="beast",
        recommended_model_key="qwen3.5-35b",
        recommended_provider="vllm",
        recommended_context_length=32768,
        notes=[],
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"mode": "paper"}), encoding="utf-8")
    catalog_src = Path(__file__).resolve().parents[1] / "lumina_model_catalog.json"
    (tmp_path / "lumina_model_catalog.json").write_text(
        catalog_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def mock_intelligence_manager() -> MagicMock:
    manager = MagicMock()
    status = _make_intelligence_status()
    manager.refresh.return_value = status
    manager.get_status.return_value = status
    hardware_snapshot = MagicMock()
    hardware_snapshot.to_dict.return_value = {
        "profile_tier": "sweet",
        "intelligence_tier": "standard",
        "recommended_model_key": "qwen3.5-9b",
        "recommended_provider": "ollama",
        "recommended_context_length": 16384,
        "ram_gb": 32.0,
        "gpu_vram_gb": 8.0,
        "vllm_supported": False,
    }
    hardware_snapshot.intelligence_tier = "standard"
    manager.hardware_manager.latest.return_value = hardware_snapshot
    manager.hardware_manager.catalog.get.return_value = _make_descriptor()
    return manager


@pytest.fixture
def mock_setup_service(workspace: Path) -> MagicMock:
    service = MagicMock()
    service.is_setup_complete.return_value = False
    service.install_launcher_dependencies.return_value = SetupStepResult(
        "launcher_dependencies", True, "ok", "pip install"
    )
    service.install_runtime_dependencies.return_value = SetupStepResult(
        "runtime_dependencies", True, "ok", "pip install -r"
    )
    service.ensure_ollama.return_value = SetupStepResult("ollama", True, "ok", "ollama")
    service.pull_model.return_value = SetupStepResult("model_pull", True, "ok", "ollama pull")
    service.apply_recommended_config.return_value = SetupStepResult("config_update", True, "ok", "")
    service.load_status.return_value = {}
    return service


@pytest.fixture
def smart_setup(
    workspace: Path,
    mock_setup_service: MagicMock,
    mock_intelligence_manager: MagicMock,
) -> SmartSetupService:
    return SmartSetupService(
        workspace,
        setup_service=mock_setup_service,
        intelligence_manager=mock_intelligence_manager,
    )


def _patch_ollama_ready(monkeypatch: pytest.MonkeyPatch, *, models: list[str] | None = None) -> None:
    installed = models if models is not None else ["qwen3.5:9b"]
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.shutil.which",
        lambda name: "/usr/bin/ollama" if name == "ollama" else None,
    )
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.ModelCatalog.installed_ollama_models",
        lambda: list(installed),
    )


@pytest.mark.unit
def test_is_first_time_without_complete_file(smart_setup: SmartSetupService) -> None:
    assert smart_setup.is_first_time() is True


@pytest.mark.unit
def test_is_first_time_with_complete_file(workspace: Path, mock_setup_service: MagicMock) -> None:
    mock_setup_service.is_setup_complete.return_value = True
    service = SmartSetupService(workspace, setup_service=mock_setup_service)
    assert service.is_first_time() is False


@pytest.mark.unit
def test_is_first_time_reads_complete_json(workspace: Path) -> None:
    state_dir = workspace / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "lumina_setup_complete.json").write_text(
        json.dumps({"completed": True}),
        encoding="utf-8",
    )
    service = SmartSetupService(workspace)
    assert service.is_first_time() is False


@pytest.mark.unit
def test_get_setup_status_missing_ollama_and_model(
    smart_setup: SmartSetupService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ollama" if name == "ollama" else None)
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.ModelCatalog.installed_ollama_models",
        lambda: [],
    )
    status = smart_setup.get_setup_status()
    assert status["first_time"] is True
    assert status["setup_complete"] is False
    assert status["ready"] is False
    assert "setup_complete" in status["missing"]
    assert "model:qwen3.5:9b" in status["missing"]


@pytest.mark.unit
def test_get_setup_status_ready_when_complete(
    workspace: Path,
    mock_intelligence_manager: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_setup = MagicMock()
    mock_setup.is_setup_complete.return_value = True
    service = SmartSetupService(
        workspace,
        setup_service=mock_setup,
        intelligence_manager=mock_intelligence_manager,
    )
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ollama" if name == "ollama" else None)
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.ModelCatalog.installed_ollama_models",
        lambda: ["qwen3.5:9b"],
    )
    status = service.get_setup_status()
    assert status["ready"] is True
    assert status["missing"] == []


@pytest.mark.unit
def test_get_install_instructions_includes_ollama_pull(
    smart_setup: SmartSetupService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.ModelCatalog.installed_ollama_models",
        lambda: [],
    )
    instructions = smart_setup.get_install_instructions()
    commands = [step.get("command", "") for step in instructions["steps"]]
    assert any("ollama pull qwen3.5:9b" in cmd for cmd in commands)
    assert "tier standard" in instructions["summary"]


@pytest.mark.unit
def test_get_install_instructions_vllm_no_pull(
    workspace: Path,
    mock_setup_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MagicMock()
    status = _make_intelligence_status(
        tier="high",
        recommended_model="qwen3.5-35b",
        recommended_provider="vllm",
        reasoning_mode="hybrid_deep",
    )
    manager.refresh.return_value = status
    manager.get_status.return_value = status
    hardware_snapshot = MagicMock()
    hardware_snapshot.to_dict.return_value = {
        "profile_tier": "beast",
        "intelligence_tier": "high",
        "recommended_model_key": "qwen3.5-35b",
        "recommended_provider": "vllm",
        "recommended_context_length": 32768,
        "ram_gb": 64.0,
        "gpu_vram_gb": 24.0,
        "vllm_supported": True,
    }
    manager.hardware_manager.latest.return_value = hardware_snapshot
    descriptor = ModelDescriptor(
        key="qwen3.5-35b",
        display_name="Qwen3.5 35B",
        family="qwen3.5",
        ollama_tag="qwen3.5:35b",
        parameter_size_b=35.0,
        vram_min_gb=20.0,
        ram_min_gb=64.0,
        recommended_tier="beast",
        recommended_provider="vllm",
        tested_by_lumina=True,
        upgrade_notes="",
        supports_unsloth=True,
        context_length=32768,
    )
    manager.hardware_manager.catalog.get.return_value = descriptor

    service = SmartSetupService(
        workspace,
        setup_service=mock_setup_service,
        intelligence_manager=manager,
    )
    monkeypatch.setattr("shutil.which", lambda _name: None)
    instructions = service.get_install_instructions()
    commands = [step.get("command", "") for step in instructions["steps"]]
    assert not any("ollama pull" in cmd for cmd in commands)
    assert any(step.get("id") == "vllm_requirements" for step in instructions["steps"])


@pytest.mark.unit
def test_run_smart_setup_success_emits_progress_and_marks_complete(
    smart_setup: SmartSetupService,
    mock_setup_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.HardwareInspector.capture",
        _make_hardware_snapshot,
    )
    _patch_ollama_ready(monkeypatch)
    progress: list[SetupProgressEvent] = []
    result = smart_setup.run_smart_setup(on_progress=progress.append, mark_complete=True)
    assert result.success is True
    assert result.degraded is False
    phases = [event.phase for event in progress]
    assert phases == [
        "detect",
        "launcher_deps",
        "runtime_deps",
        "ollama",
        "ollama_verify",
        "model_pull",
        "config",
        "complete",
    ]
    mock_setup_service.mark_complete.assert_called_once()
    mock_setup_service.save_status.assert_called()
    mock_setup_service.ensure_ollama.assert_not_called()
    mock_setup_service.pull_model.assert_not_called()


@pytest.mark.unit
def test_run_smart_setup_mark_complete_false_skips_complete_file(
    smart_setup: SmartSetupService,
    mock_setup_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.HardwareInspector.capture",
        _make_hardware_snapshot,
    )
    _patch_ollama_ready(monkeypatch)
    result = smart_setup.run_smart_setup(mark_complete=False)
    assert result.success is True
    mock_setup_service.mark_complete.assert_not_called()
    save_args = mock_setup_service.save_status.call_args[0][0]
    assert save_args.get("smart_setup") is True
    assert save_args.get("degraded") is False


@pytest.mark.unit
def test_is_intelligence_stack_ready_when_ollama_and_model_present(
    workspace: Path,
    mock_intelligence_manager: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_setup = MagicMock()
    mock_setup.is_setup_complete.return_value = False
    mock_setup.load_status.return_value = {"smart_setup": True}
    service = SmartSetupService(
        workspace,
        setup_service=mock_setup,
        intelligence_manager=mock_intelligence_manager,
    )
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ollama" if name == "ollama" else None)
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.ModelCatalog.installed_ollama_models",
        lambda: ["qwen3.5:9b"],
    )
    assert service.is_intelligence_stack_ready() is True


@pytest.mark.unit
def test_run_smart_setup_skips_ollama_when_option_disabled(
    smart_setup: SmartSetupService,
    mock_setup_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.HardwareInspector.capture",
        _make_hardware_snapshot,
    )
    options = SmartSetupOptions(install_ollama=False, download_recommended_model=False)
    result = smart_setup.run_smart_setup(options=options, mark_complete=False)
    assert result.success is True
    mock_setup_service.ensure_ollama.assert_not_called()
    mock_setup_service.pull_model.assert_not_called()
    assert any(step.get("name") == "ollama_skipped" for step in result.steps)


@pytest.mark.unit
def test_run_smart_setup_stops_on_failure(
    smart_setup: SmartSetupService,
    mock_setup_service: MagicMock,
) -> None:
    mock_setup_service.install_runtime_dependencies.return_value = SetupStepResult(
        "runtime_dependencies",
        False,
        "pip failed",
        "pip install -r requirements.txt",
    )
    progress: list[SetupProgressEvent] = []
    result = smart_setup.run_smart_setup(on_progress=progress.append)
    assert result.success is False
    assert progress[-1].phase == "failed"
    mock_setup_service.mark_complete.assert_not_called()
    mock_setup_service.pull_model.assert_not_called()


@pytest.mark.unit
def test_run_smart_setup_skips_ollama_for_vllm(
    workspace: Path,
    mock_setup_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MagicMock()
    status = _make_intelligence_status(
        tier="high",
        recommended_model="qwen3.5-35b",
        recommended_provider="vllm",
        reasoning_mode="hybrid_deep",
    )
    manager.refresh.return_value = status
    manager.get_status.return_value = status
    hardware_snapshot = MagicMock()
    hardware_snapshot.to_dict.return_value = {
        "profile_tier": "beast",
        "intelligence_tier": "high",
        "recommended_model_key": "qwen3.5-35b",
        "recommended_provider": "vllm",
        "recommended_context_length": 32768,
        "ram_gb": 64.0,
        "gpu_vram_gb": 24.0,
        "vllm_supported": True,
    }
    hardware_snapshot.intelligence_tier = "high"
    manager.hardware_manager.latest.return_value = hardware_snapshot
    descriptor = ModelDescriptor(
        key="qwen3.5-35b",
        display_name="Qwen3.5 35B",
        family="qwen3.5",
        ollama_tag="qwen3.5:35b",
        parameter_size_b=35.0,
        vram_min_gb=20.0,
        ram_min_gb=64.0,
        recommended_tier="beast",
        recommended_provider="vllm",
        tested_by_lumina=True,
        upgrade_notes="",
        supports_unsloth=True,
        context_length=32768,
    )
    manager.hardware_manager.catalog.get.return_value = descriptor

    service = SmartSetupService(
        workspace,
        setup_service=mock_setup_service,
        intelligence_manager=manager,
    )
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.HardwareInspector.capture",
        _make_hardware_snapshot,
    )
    progress: list[SetupProgressEvent] = []
    result = service.run_smart_setup(on_progress=progress.append)
    assert result.success is True
    assert "skipped_vllm_provider" in [event.phase for event in progress]
    mock_setup_service.ensure_ollama.assert_not_called()
    mock_setup_service.pull_model.assert_not_called()


@pytest.mark.unit
def test_install_ollama_already_present_skips_subprocess(
    smart_setup: SmartSetupService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smart_setup, "_ollama_on_path", lambda: True)
    run_mock = MagicMock()
    monkeypatch.setattr(smart_setup, "_run_subprocess_step", run_mock)
    result, manual = smart_setup._install_ollama_subprocess()
    assert result.success is True
    run_mock.assert_not_called()
    assert manual == []


@pytest.mark.unit
def test_pull_model_subprocess_emits_progress_lines(
    smart_setup: SmartSetupService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smart_setup, "_ollama_on_path", lambda: True)
    monkeypatch.setattr(smart_setup, "_ollama_model_installed", lambda _tag: False)

    class FakeCompleted:
        returncode = 0
        stdout = "pulling manifest\nlayer 1/2 complete\n"
        stderr = ""

    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.subprocess.run",
        lambda *args, **kwargs: FakeCompleted(),
    )
    progress: list[SetupProgressEvent] = []
    result = smart_setup._pull_model_subprocess(_make_descriptor(), on_progress=progress.append)
    assert result.success is True
    assert any(event.phase == "model_pull_progress" for event in progress)


@pytest.mark.unit
def test_run_smart_setup_graceful_ollama_fail_continues(
    smart_setup: SmartSetupService,
    mock_setup_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.HardwareInspector.capture",
        _make_hardware_snapshot,
    )
    fail = SubprocessStepResult("ollama", False, "install mislukt", "winget install")
    manual = [{"id": "ollama_install", "title": "Installeer Ollama", "command": "winget", "manual": ""}]
    monkeypatch.setattr(
        smart_setup,
        "_install_ollama_subprocess",
        lambda: (fail, manual),
    )
    monkeypatch.setattr(
        smart_setup,
        "_verify_ollama_runtime",
        lambda: SubprocessStepResult("ollama_verify", False, "daemon niet bereikbaar", ""),
    )
    monkeypatch.setattr(
        smart_setup,
        "_pull_model_subprocess",
        lambda descriptor, on_progress=None: SubprocessStepResult(
            "model_pull", False, "pull mislukt", "ollama pull"
        ),
    )
    options = SmartSetupOptions(graceful_degrade=True)
    result = smart_setup.run_smart_setup(options=options, mark_complete=False)
    assert result.success is True
    assert result.degraded is True
    assert result.warnings
    assert result.manual_steps
    mock_setup_service.apply_recommended_config.assert_called_once()


@pytest.mark.unit
def test_run_smart_setup_strict_ollama_fail_stops(
    smart_setup: SmartSetupService,
    mock_setup_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.HardwareInspector.capture",
        _make_hardware_snapshot,
    )
    fail = SubprocessStepResult("ollama", False, "install mislukt", "winget install")
    monkeypatch.setattr(
        smart_setup,
        "_install_ollama_subprocess",
        lambda: (fail, [{"id": "ollama_install", "title": "Installeer Ollama", "command": "x", "manual": ""}]),
    )
    options = SmartSetupOptions(graceful_degrade=False)
    result = smart_setup.run_smart_setup(options=options, mark_complete=False)
    assert result.success is False
    assert result.degraded is True
    mock_setup_service.apply_recommended_config.assert_not_called()


@pytest.mark.unit
def test_finalize_includes_manual_steps_on_ollama_fail(
    smart_setup: SmartSetupService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smart_setup, "_ollama_on_path", lambda: False)
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        "lumina_launcher.services.smart_setup_service.shutil.which",
        lambda name: None,
    )
    monkeypatch.setattr(
        smart_setup,
        "_run_subprocess_step",
        lambda *args, **kwargs: SubprocessStepResult("ollama", False, "winget exit 1", "winget"),
    )
    result, manual = smart_setup._install_ollama_subprocess()
    assert result.success is False
    assert manual
    assert any(step.get("id") == "ollama_install" for step in manual)
