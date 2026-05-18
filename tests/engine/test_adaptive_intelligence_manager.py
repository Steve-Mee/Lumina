from __future__ import annotations

import pytest

from lumina_core.adaptive_intelligence import AdaptiveIntelligenceManager, build_status_signature
from lumina_core.agent_orchestration.schemas import AdaptiveIntelligenceState
from lumina_core.hardware_intelligence import HardwareIntelligenceManager


@pytest.mark.unit
def test_hardware_intelligence_maps_legacy_tiers_to_canonical() -> None:
    manager = HardwareIntelligenceManager()

    assert manager._canonical_tier("beast") == "high"
    assert manager._canonical_tier("sweet") == "standard"
    assert manager._canonical_tier("light") == "light"
    assert manager._canonical_tier("unknown") == "light"


@pytest.mark.unit
def test_adaptive_intelligence_force_high_degrades_when_hardware_not_high(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = AdaptiveIntelligenceManager()
    monkeypatch.setattr(
        "lumina_core.adaptive_intelligence.ConfigLoader.get",
        classmethod(lambda cls: {"intelligence": {"mode": "force_high"}}),
    )
    monkeypatch.setattr(
        manager.hardware_manager,
        "resolve",
        lambda refresh_hardware=False: type(
            "Snapshot",
            (),
            {
                "intelligence_tier": "standard",
                "recommended_model_key": "qwen3.5-9b",
                "recommended_provider": "ollama",
                "recommended_context_length": 16384,
            },
        )(),
    )

    status = manager.refresh()
    assert status.tier == "standard"
    assert status.degraded_state is True
    assert status.status_reason == "force_high_requested_but_hardware_insufficient"


@pytest.mark.unit
def test_adaptive_intelligence_auto_mode_uses_detected_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = AdaptiveIntelligenceManager()
    monkeypatch.setattr(
        "lumina_core.adaptive_intelligence.ConfigLoader.get",
        classmethod(lambda cls: {"intelligence": {"mode": "auto"}}),
    )
    monkeypatch.setattr(
        manager.hardware_manager,
        "resolve",
        lambda refresh_hardware=False: type(
            "Snapshot",
            (),
            {
                "intelligence_tier": "high",
                "recommended_model_key": "qwen3.5-35b",
                "recommended_provider": "vllm",
                "recommended_context_length": 32768,
            },
        )(),
    )

    status = manager.refresh()
    assert status.tier == "high"
    assert status.reasoning_mode == "hybrid_deep"
    assert status.degraded_state is False


@pytest.mark.unit
def test_adaptive_intelligence_status_validates_against_event_contract() -> None:
    status = {
        "tier": "standard",
        "mode": "auto",
        "reasoning_mode": "hybrid_balanced",
        "degraded_state": False,
        "status_reason": "auto_hardware_resolution",
        "recommended_model": "qwen3.5-9b",
        "recommended_provider": "ollama",
        "context_length": 16384,
        "last_probe_error": None,
        "source": "unit_test",
        "timestamp": "2026-05-18T00:00:00+00:00",
    }
    validated = AdaptiveIntelligenceState.model_validate(status)
    assert validated.tier == "standard"


@pytest.mark.unit
def test_build_status_signature_ignores_non_state_fields() -> None:
    base = {
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
    with_extra = {
        **base,
        "timestamp": "2026-05-18T00:00:00+00:00",
        "source": "container_status_poll",
    }
    assert build_status_signature(base) == build_status_signature(with_extra)


@pytest.mark.unit
def test_lumina_engine_exposes_adaptive_intelligence_slot() -> None:
    from dataclasses import fields

    from lumina_core.engine.engine_config import EngineConfig
    from lumina_core.engine.lumina_engine import LuminaEngine

    field_names = {field.name for field in fields(LuminaEngine)}
    assert "adaptive_intelligence" in field_names

    engine = LuminaEngine(config=EngineConfig())
    status = {"tier": "light", "mode": "auto"}
    engine.adaptive_intelligence = status
    assert engine.adaptive_intelligence == status
