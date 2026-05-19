from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lumina_core.container import ApplicationContainer


@pytest.mark.unit
def test_smart_setup_service_lazy_singleton_property() -> None:
    container = ApplicationContainer.__new__(ApplicationContainer)
    container._smart_setup_service = None

    mock_service = MagicMock()
    with patch(
        "lumina_launcher.services.smart_setup_service.SmartSetupService",
        return_value=mock_service,
    ) as factory:
        first = container.smart_setup_service
        second = container.smart_setup_service

    assert first is second
    factory.assert_called_once()


@pytest.mark.unit
def test_container_get_status_includes_launcher_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    container = ApplicationContainer.__new__(ApplicationContainer)
    container.logger = MagicMock()
    container.engine = MagicMock()
    container.market_data_service = MagicMock()
    container.memory_service = MagicMock()
    container.reasoning_service = MagicMock()
    container.operations_service = MagicMock()
    container.analysis_service = MagicMock()
    container.dashboard_service = MagicMock()
    container.visualization_service = MagicMock()
    container.reporting_service = MagicMock()
    container.news_agent = MagicMock()
    container.ppo_trainer = MagicMock()
    container.emotional_twin_agent = MagicMock()
    container.infinite_simulator = MagicMock()
    container.trade_reconciler = MagicMock()
    container.swarm_manager = MagicMock()
    container.performance_validator = MagicMock()
    container.voice_recognizer = None
    container.tts_engine = None
    container.swarm_symbols = []
    container.primary_instrument = ""

    monkeypatch.setattr(
        ApplicationContainer,
        "_refresh_adaptive_intelligence",
        lambda self, **_: {"tier": "standard"},
    )
    container._smart_setup_service = MagicMock()
    monkeypatch.setattr(
        "lumina_launcher.core.setup_gate.launcher_setup_status_payload",
        lambda *args, **kwargs: {
            "setup_complete": True,
            "intelligence_stack_ready": True,
            "needs_smart_setup": False,
            "needs_guided_setup": False,
            "launcher_ready": True,
            "recommended_model": "qwen3.5-9b",
            "recommended_provider": "ollama",
        },
    )

    status = container.get_status()
    assert "launcher_setup" in status
    assert status["launcher_setup"]["setup_complete"] is True
    assert status["launcher_setup"]["recommended_model"] == "qwen3.5-9b"
