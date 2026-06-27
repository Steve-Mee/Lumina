from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.hardware_intelligence import (
    HARDWARE_PROFILES,
    detect_hardware_profile,
    get_or_create_hardware_profile,
)


@pytest.mark.unit
def test_detect_hardware_profile_cpu_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lumina_core.hardware_intelligence._cuda_available", lambda: False)
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence._read_gpu_via_torch",
        lambda: (None, 0.0),
    )
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence.HardwareInspector._read_nvidia_gpu",
        staticmethod(lambda: (None, 0.0, 0.0, False)),
    )
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence.HardwareInspector._cpu_count",
        staticmethod(lambda logical: 8),
    )
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence.HardwareInspector._read_memory_gb",
        staticmethod(lambda: 16.0),
    )

    result = detect_hardware_profile()

    assert result["has_cuda"] is False
    assert result["gpu_name"] is None
    assert result["vram_gb"] == 0.0
    assert result["cpu_cores"] == 8
    assert result["ram_gb"] == 16.0
    assert result["recommended_profile"] == "cpu_efficient"


@pytest.mark.unit
def test_detect_hardware_profile_gpu_accelerated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lumina_core.hardware_intelligence._cuda_available", lambda: True)
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence._read_gpu_via_torch",
        lambda: ("NVIDIA GeForce RTX 4090", 11.0),
    )
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence.HardwareInspector._cpu_count",
        staticmethod(lambda logical: 16),
    )
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence.HardwareInspector._read_memory_gb",
        staticmethod(lambda: 64.0),
    )

    result = detect_hardware_profile()

    assert result["has_cuda"] is True
    assert result["gpu_name"] == "NVIDIA GeForce RTX 4090"
    assert result["vram_gb"] == 11.0
    assert result["recommended_profile"] == "gpu_accelerated"


@pytest.mark.unit
def test_detect_hardware_profile_gpu_low_vram(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lumina_core.hardware_intelligence._cuda_available", lambda: True)
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence._read_gpu_via_torch",
        lambda: ("NVIDIA GeForce GTX 1650", 4.0),
    )
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence.HardwareInspector._cpu_count",
        staticmethod(lambda logical: 8),
    )
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence.HardwareInspector._read_memory_gb",
        staticmethod(lambda: 32.0),
    )

    result = detect_hardware_profile()

    assert result["has_cuda"] is True
    assert result["vram_gb"] == 4.0
    assert result["recommended_profile"] == "cpu_efficient"


@pytest.mark.unit
def test_get_or_create_hardware_profile_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cached_payload = {
        "profile": "gpu_accelerated",
        "detection": {
            "has_cuda": True,
            "gpu_name": "Cached GPU",
            "vram_gb": 24.0,
            "cpu_cores": 16,
            "ram_gb": 64.0,
            "recommended_profile": "gpu_accelerated",
        },
        "tuning": HARDWARE_PROFILES["gpu_accelerated"].to_dict(),
        "created_at": "2026-06-27T00:00:00+00:00",
    }
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "hardware_profile.json").write_text(json.dumps(cached_payload), encoding="utf-8")

    def fail_detect() -> dict[str, object]:
        raise AssertionError("detect_hardware_profile should not be called on cache hit")

    monkeypatch.setattr("lumina_core.hardware_intelligence.detect_hardware_profile", fail_detect)

    result = get_or_create_hardware_profile(tmp_path)

    assert result == cached_payload


@pytest.mark.unit
def test_get_or_create_hardware_profile_create(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "lumina_core.hardware_intelligence.detect_hardware_profile",
        lambda: {
            "has_cuda": False,
            "gpu_name": None,
            "vram_gb": 0.0,
            "cpu_cores": 8,
            "ram_gb": 16.0,
            "recommended_profile": "cpu_efficient",
        },
    )

    result = get_or_create_hardware_profile(tmp_path)

    assert result["profile"] == "cpu_efficient"
    assert result["detection"]["recommended_profile"] == "cpu_efficient"
    assert result["tuning"] == HARDWARE_PROFILES["cpu_efficient"].to_dict()
    assert "created_at" in result

    state_path = tmp_path / "state" / "hardware_profile.json"
    assert state_path.exists()
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["profile"] == "cpu_efficient"
