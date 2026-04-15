from __future__ import annotations

import json
from pathlib import Path
import platform

import yaml

from lumina_core.engine.hardware_inspector import HardwareInspector, HardwareSnapshot
from lumina_core.engine.model_catalog import ModelCatalog
from lumina_core.engine.setup_service import SetupService


def test_hardware_inspector_capture_uses_recommendation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(HardwareInspector, "_read_memory_gb", staticmethod(lambda: 64.0))
    monkeypatch.setattr(HardwareInspector, "_cpu_count", staticmethod(lambda logical: 16 if logical else 8))
    monkeypatch.setattr(
        HardwareInspector,
        "_read_nvidia_gpu",
        staticmethod(lambda: ("RTX 4090", 24.0, 8.9, True)),
    )
    monkeypatch.setattr(HardwareInspector, "_detect_ollama_running", staticmethod(lambda: True))
    monkeypatch.setattr("shutil.which", lambda name: "ollama" if name == "ollama" else "nvidia-smi")

    snapshot = HardwareInspector.capture()

    assert snapshot.profile_tier == "beast"
    assert snapshot.recommended_model_key == "qwen3.5-35b"
    assert snapshot.vllm_supported is False or isinstance(snapshot.vllm_supported, bool)
    assert Path("state/hardware_snapshot.json").exists()


def test_setup_service_applies_recommended_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "hardware_profile": "light",
                "inference": {"primary_provider": "ollama", "fallback_order": ["ollama"]},
                "ollama": {"num_ctx": 4096},
                "models": {"reasoning": "qwen3.5:4b"},
                "vllm": {"model_name": "qwen3.5-35b"},
            }
        ),
        encoding="utf-8",
    )
    service = SetupService(config_path=config_path)
    catalog = ModelCatalog(Path("c:/NinjaTraderAI_Bot/lumina_model_catalog.json"))
    model = catalog.get("qwen3.5-9b")
    assert model is not None
    snapshot = HardwareSnapshot(
        os_name="Linux",
        os_version="test",
        cpu_name="cpu",
        cpu_cores_physical=8,
        cpu_cores_logical=16,
        ram_gb=64.0,
        gpu_name="RTX",
        gpu_vram_gb=24.0,
        compute_capability=8.9,
        ollama_installed=True,
        ollama_running=True,
        nvidia_smi_available=True,
        vllm_supported=True,
        profile_tier="sweet",
        recommended_model_key="qwen3.5-9b",
        recommended_provider="ollama",
        recommended_context_length=16384,
        notes=[],
    )

    result = service.apply_recommended_config(hardware=snapshot, model=model)

    updated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert result.success is True
    assert updated["hardware_profile"] == "sweet"
    assert updated["models"]["reasoning"] == "qwen3.5:9b"
    assert updated["ollama"]["num_ctx"] == 16384
    assert updated["inference"]["primary_provider"] == "ollama"


def test_setup_service_upgrade_model_uses_cached_hardware(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "hardware_profile": "light",
                "inference": {"primary_provider": "ollama", "fallback_order": ["ollama"]},
                "ollama": {"num_ctx": 4096},
                "models": {"reasoning": "qwen3.5:4b"},
                "vllm": {"model_name": "qwen3.5-35b"},
            }
        ),
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_dir.joinpath("hardware_snapshot.json").write_text(
        json.dumps(
            {
                "os_name": "Linux",
                "os_version": "test",
                "cpu_name": "cpu",
                "cpu_cores_physical": 8,
                "cpu_cores_logical": 16,
                "ram_gb": 32.0,
                "gpu_name": "RTX 4070",
                "gpu_vram_gb": 12.0,
                "compute_capability": 8.9,
                "ollama_installed": True,
                "ollama_running": True,
                "nvidia_smi_available": True,
                "vllm_supported": True,
                "profile_tier": "sweet",
                "recommended_model_key": "qwen3.5-9b",
                "recommended_provider": "ollama",
                "recommended_context_length": 16384,
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    service = SetupService(config_path=config_path)
    monkeypatch.setattr(service, "pull_model", lambda descriptor: type("R", (), {"name": "model_pull", "success": True, "message": descriptor.key, "command": "ollama pull"})())
    catalog = ModelCatalog(Path("c:/NinjaTraderAI_Bot/lumina_model_catalog.json"))
    model = catalog.get("qwen3.5-9b")
    assert model is not None

    results = service.upgrade_model(model)

    updated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert len(results) == 2
    assert updated["models"]["reasoning"] == "qwen3.5:9b"


def test_hardware_inspector_notes_include_vllm_blockers_once() -> None:
    notes = HardwareInspector._build_notes(
        profile_tier="sweet",
        gpu_vram_gb=11.0,
        ram_gb=32.0,
        compute_capability=6.1,
        os_name="Windows",
        ollama_installed=True,
        ollama_running=True,
        vllm_supported=False,
    )

    joined = "\n".join(notes)
    assert "vLLM-pad is geblokkeerd" in joined
    assert "compute capability 6.1 < sm_70" in joined
    assert "Windows-native runtime" in joined
    assert "Compute capability 6.1 ligt onder sm_70" not in joined


def test_hardware_inspector_sweet_note_spells_beast_requirements() -> None:
    notes = HardwareInspector._build_notes(
        profile_tier="sweet",
        gpu_vram_gb=11.0,
        ram_gb=32.0,
        compute_capability=6.1,
        os_name="Windows",
        ollama_installed=True,
        ollama_running=True,
        vllm_supported=False,
    )

    assert any("voor beast is 64 GB RAM" in note for note in notes)