from __future__ import annotations

import pytest

from lumina_core.intelligence.organs import OrgansProbe, build_organs_truth
from lumina_core.intelligence.resolve import VoiceWorkload, resolve_provider

pytestmark = pytest.mark.unit


def _windows_probe(**overrides: object) -> OrgansProbe:
    values: dict[str, object] = {
        "os_name": "Windows",
        "vllm_supported": True,
        "vllm_health_ok": True,
        "vllm_importable": False,
        "cuda_available": True,
        "gpu_name": "NVIDIA GeForce RTX 5070 Ti",
        "torch_ok": True,
        "sb3_ok": True,
        "ollama_installed": True,
        "grok_key_present": True,
        "requested_provider": "ollama",
        "intelligence_mode": "auto",
        "profile_tier": "sweet",
        "ladder_phase": "genesis",
    }
    values.update(overrides)
    return OrgansProbe(**values)  # type: ignore[arg-type]


def test_os_name_nt_is_windows() -> None:
    from lumina_core.intelligence.organs import is_windows

    assert is_windows("Windows") is True
    assert is_windows("nt") is True
    assert is_windows("Linux") is False
    truth = build_organs_truth(_windows_probe(os_name="nt", vllm_supported=True, requested_provider="vllm"))
    assert "vllm" not in truth.voice.allowed_providers
    assert truth.voice.selected_provider != "vllm"


def test_windows_blocks_vllm_and_keeps_lungs_independent() -> None:
    # gegeven
    probe = _windows_probe(requested_provider="vllm", cuda_available=True)

    # wanneer
    truth = build_organs_truth(probe)

    # dan
    assert "vllm" not in truth.voice.allowed_providers
    assert any(item.id == "vllm" for item in truth.voice.blocked_providers)
    assert truth.voice.selected_provider in {"ollama", "grok_remote", "off"}
    assert truth.lungs.cuda_available is True
    assert truth.lungs.status == "ready"
    assert truth.news.order_path_coupled is False


def test_windows_voice_off_does_not_require_ready_voice() -> None:
    # gegeven
    probe = _windows_probe(requested_provider="off", ollama_installed=False, grok_key_present=False)

    # wanneer
    truth = build_organs_truth(probe)

    # dan
    assert truth.voice.selected_provider == "off"
    assert truth.voice.status == "off"
    assert truth.lungs.status == "ready"


def test_linux_beast_healthy_vllm_allowed_not_required() -> None:
    # gegeven
    probe = OrgansProbe(
        os_name="Linux",
        vllm_supported=True,
        vllm_health_ok=True,
        vllm_importable=False,
        cuda_available=True,
        gpu_name="RTX 4090",
        torch_ok=True,
        sb3_ok=True,
        ollama_installed=True,
        grok_key_present=True,
        requested_provider="off",
        intelligence_mode="auto",
        profile_tier="beast",
        ladder_phase="genesis",
    )

    # wanneer
    truth = build_organs_truth(probe)

    # dan
    assert "vllm" in truth.voice.allowed_providers
    assert truth.voice.selected_provider == "off"
    vllm_choice = next(item for item in truth.operator_choices if item.id == "vllm")
    assert vllm_choice.visible is True
    assert vllm_choice.enabled is True


def test_force_high_on_windows_never_selects_vllm() -> None:
    # gegeven
    probe = _windows_probe(requested_provider="vllm", intelligence_mode="force_high")

    # wanneer
    truth = build_organs_truth(probe)

    # dan
    assert truth.voice.selected_provider != "vllm"
    assert "vllm" not in truth.voice.allowed_providers


def test_news_order_path_coupled_is_false() -> None:
    # gegeven / wanneer
    truth = build_organs_truth(_windows_probe())

    # dan
    assert truth.news.order_path_coupled is False
    dumped = truth.model_dump()
    assert dumped["news"]["order_path_coupled"] is False


def test_resolve_news_never_returns_lungs_installer() -> None:
    # gegeven
    allowed = ["ollama", "grok_remote", "vllm", "install_birth_physics_stack"]

    # wanneer
    provider = resolve_provider(
        VoiceWorkload.NEWS_INTERPRET,
        allowed_providers=allowed,
        selected_provider="ollama",
    )

    # dan
    assert provider == "grok_remote"
    assert provider not in {"install_birth_physics_stack", "torch", "stable_baselines3"}


def test_lungs_cuda_independent_of_voice_off() -> None:
    # gegeven
    probe = _windows_probe(requested_provider="off", cuda_available=True)

    # wanneer
    truth = build_organs_truth(probe)

    # dan
    assert truth.lungs.cuda_available is True
    assert truth.voice.selected_provider == "off"
