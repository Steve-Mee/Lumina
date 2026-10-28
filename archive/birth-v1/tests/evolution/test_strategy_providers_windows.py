from __future__ import annotations

import os

import pytest

from lumina_core.engine.setup_service import SetupService
from lumina_core.evolution.strategy_generator import StrategyGenerator
from lumina_core.intelligence.organs import default_strategy_provider_chain

pytestmark = pytest.mark.unit


def test_default_chain_on_windows_starts_with_ollama_not_vllm(monkeypatch: pytest.MonkeyPatch) -> None:
    # gegeven
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.delenv("LUMINA_STRATEGY_PROVIDERS", raising=False)

    # wanneer
    chain = default_strategy_provider_chain(os_name="nt")
    generator = StrategyGenerator()

    # dan
    assert chain.startswith("ollama")
    assert not chain.startswith("vllm")
    assert generator._providers[0] == "ollama"
    assert generator._providers[0] != "vllm"


def test_setup_provider_order_windows_never_leads_with_vllm() -> None:
    # gegeven / wanneer
    order = SetupService._build_provider_order(
        "vllm",
        os_name="Windows",
        vllm_supported=True,
        vllm_health_ok=True,
    )

    # dan
    assert order[0] != "vllm"
    assert "vllm" not in order
    assert order[0] == "ollama"
