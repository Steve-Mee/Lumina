from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from lumina_agents.news_agent import NewsAgent
from lumina_core.intelligence.organs import OrgansProbe, build_organs_truth

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_provider_off_returns_neutral_multiplier_one(monkeypatch: pytest.MonkeyPatch) -> None:
    # gegeven
    truth = build_organs_truth(
        OrgansProbe(
            os_name="Windows",
            vllm_supported=False,
            vllm_health_ok=False,
            vllm_importable=False,
            cuda_available=True,
            gpu_name="GPU",
            torch_ok=True,
            sb3_ok=True,
            ollama_installed=False,
            grok_key_present=False,
            requested_provider="off",
        )
    )

    class _Manager:
        def organs_truth(self) -> object:
            return truth

    monkeypatch.setattr(
        "lumina_core.adaptive_intelligence.AdaptiveIntelligenceManager",
        lambda *args, **kwargs: _Manager(),
    )
    placed: list[str] = []
    app = SimpleNamespace(
        get_high_impact_news=lambda: {"events": []},
        world_model={},
        logger=SimpleNamespace(info=lambda *_a, **_k: None),
        place_order=lambda *_a, **_k: placed.append("place"),
        cancel_order=lambda *_a, **_k: placed.append("cancel"),
    )
    engine = SimpleNamespace(
        app=app,
        blackboard=None,
        config=SimpleNamespace(
            xai_model="grok-4.1-fast",
            xai_key="",
            xai_update_interval_sec=60,
            news_avoidance_minutes=3,
            news_avoidance_post_minutes=5,
            news_avoidance_high_impact_pre_minutes=15,
            news_avoidance_high_impact_post_minutes=10,
            news_impact_multipliers={},
            trade_mode="real",
        ),
        decision_log=None,
        get_current_dream_snapshot=lambda: {},
    )
    agent = NewsAgent(engine=cast(Any, engine))

    # wanneer
    result = agent.run_news_cycle()

    # dan
    assert result["sentiment_signal"] == "neutral"
    assert result["dynamic_multiplier"] == 1.0
    assert result["news_avoidance_window"] is False
    assert result["degraded"] is True
    assert result["order_path_coupled"] is False
    assert placed == []


def test_news_module_does_not_import_fabric_place_cancel() -> None:
    # gegeven
    source = (ROOT / "lumina_agents" / "news_agent.py").read_text(encoding="utf-8")

    # wanneer / dan
    assert "place_order" not in source
    assert "cancel_order" not in source
    assert "fabric_client" not in source
    assert "from lumina_core.broker" not in source


def test_news_provider_flip_does_not_place_real_order(monkeypatch: pytest.MonkeyPatch) -> None:
    # gegeven
    calls: list[str] = []

    def _place(*_a: object, **_k: object) -> None:
        calls.append("place")

    monkeypatch.setattr(
        "lumina_core.adaptive_intelligence.AdaptiveIntelligenceManager",
        lambda *args, **kwargs: SimpleNamespace(
            organs_truth=lambda: build_organs_truth(
                OrgansProbe(
                    os_name="Windows",
                    vllm_supported=False,
                    vllm_health_ok=False,
                    vllm_importable=False,
                    cuda_available=False,
                    gpu_name=None,
                    torch_ok=True,
                    sb3_ok=True,
                    ollama_installed=True,
                    grok_key_present=False,
                    requested_provider="ollama",
                )
            )
        ),
    )
    app = SimpleNamespace(
        get_high_impact_news=lambda: {"events": []},
        world_model={},
        logger=SimpleNamespace(info=lambda *_a, **_k: None),
    )
    engine = SimpleNamespace(
        app=app,
        blackboard=None,
        config=SimpleNamespace(
            xai_model="grok-4.1-fast",
            xai_key="",
            xai_update_interval_sec=60,
            news_avoidance_minutes=3,
            news_avoidance_post_minutes=5,
            news_avoidance_high_impact_pre_minutes=15,
            news_avoidance_high_impact_post_minutes=10,
            news_impact_multipliers={},
            trade_mode="real",
        ),
        decision_log=None,
        place_order=_place,
        cancel_order=lambda *_a, **_k: calls.append("cancel"),
    )
    agent = NewsAgent(engine=cast(Any, engine))
    monkeypatch.setattr(NewsAgent, "_call_xai", lambda *_a, **_k: None)

    # wanneer
    agent.run_news_cycle()
    monkeypatch.setattr(
        "lumina_core.adaptive_intelligence.AdaptiveIntelligenceManager",
        lambda *args, **kwargs: SimpleNamespace(
            organs_truth=lambda: build_organs_truth(
                OrgansProbe(
                    os_name="Windows",
                    vllm_supported=False,
                    vllm_health_ok=False,
                    vllm_importable=False,
                    cuda_available=False,
                    gpu_name=None,
                    torch_ok=True,
                    sb3_ok=True,
                    ollama_installed=False,
                    grok_key_present=False,
                    requested_provider="off",
                )
            )
        ),
    )
    agent._last_update_dt = datetime.now(timezone.utc).replace(year=2000)
    agent.run_news_cycle()

    # dan
    assert calls == []
