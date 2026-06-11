"""Tests for PreDreamVisionCycleService (D2 sub-slice 22)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.schemas import TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC
from lumina_core.engine.pre_dream_vision_cycle import PreDreamVisionCycleService


def _vision_inputs(**overrides: object) -> dict:
    base = {
        "consensus": {"signal": "BUY", "confidence": 0.8},
        "meta": {"meta_reasoning": "meta", "meta_score": 0.6, "counterfactuals": []},
        "rl_context": "RL signal BUY",
        "past_experiences": [],
        "chart_base64": "abc",
        "min_conf": 0.7,
        "macro_news_sentiment": "neutral",
        "macro_news_score": 0.0,
        "news_data": {"impact": "medium"},
        "macro_news_multiplier": 1.0,
        "avoid_active": False,
    }
    base.update(overrides)
    return base


def _base_app(*, infer_return: object, event_bus: object | None = None) -> SimpleNamespace:
    fields_calls: list = []

    return SimpleNamespace(
        engine=SimpleNamespace(
            config=SimpleNamespace(vision_model="dummy", trade_mode="paper"),
            emotional_twin=None,
            event_bus=event_bus,
        ),
        world_model={
            "macro": {"vix": 1.0, "dxy": 1.0, "ten_year_yield": 1.0, "news_sentiment": "neutral"},
            "micro": {"regime": "TRENDING", "orderflow_bias": "NEUTRAL"},
        },
        infer_json=lambda *_a, **_k: infer_return,
        set_current_dream_fields=lambda d: fields_calls.append(d),
        set_current_dream_value=lambda *_a, **_k: None,
        get_current_dream_snapshot=lambda: {"chosen_strategy": "event_driven", "signal": "BUY", "confluence_score": 0.8},
        AI_DRAWN_FIBS={},
        speak=lambda *_a, **_k: None,
        store_experience_to_vector_db=lambda *_a, **_k: None,
        logger=SimpleNamespace(info=lambda *_a, **_k: None),
        _fields_calls=fields_calls,
    )


@pytest.mark.unit
def test_infer_none_should_continue():
    app = _base_app(infer_return=None)
    result = PreDreamVisionCycleService(app=app).run_cycle(**_vision_inputs())
    assert result.should_continue is True


@pytest.mark.unit
def test_infer_dict_sets_dream_fields_without_bus():
    dream = {
        "signal": "BUY",
        "confluence_score": 0.8,
        "chosen_strategy": "event_driven",
        "fib_levels_drawn": {},
        "narrative_reasoning": "hello",
    }
    app = _base_app(infer_return=dream)
    result = PreDreamVisionCycleService(app=app).run_cycle(**_vision_inputs())
    assert result.should_continue is False
    assert len(app._fields_calls) == 1
    print("MANUAL_SMOKE_SUB22_VISION_SUCCESS")


@pytest.mark.unit
def test_avoid_active_forces_hold():
    dream = {"signal": "BUY", "confluence_score": 0.8, "narrative_reasoning": ""}
    app = _base_app(infer_return=dream)
    PreDreamVisionCycleService(app=app).run_cycle(**_vision_inputs(avoid_active=True))
    assert app._fields_calls[0]["signal"] == "HOLD"
    assert app._fields_calls[0]["why_no_trade"] == "News avoidance window active"


@pytest.mark.unit
def test_twin_apply_correction_called():
    class Twin:
        def __init__(self) -> None:
            self.calls = 0

        def apply_correction(self, dream_json: dict) -> dict:
            self.calls += 1
            out = dict(dream_json)
            out["signal"] = "HOLD"
            return out

    twin = Twin()
    dream = {"signal": "BUY", "confluence_score": 0.8, "narrative_reasoning": ""}
    app = _base_app(infer_return=dream)
    app.engine.emotional_twin = twin
    PreDreamVisionCycleService(app=app).run_cycle(**_vision_inputs())
    assert twin.calls == 1
    assert app._fields_calls[0]["signal"] == "HOLD"


@pytest.mark.unit
def test_event_bus_publish_aggregate():
    published: list = []

    class Bus:
        def publish(self, **kwargs: object) -> None:
            published.append(kwargs)

    dream = {
        "signal": "BUY",
        "confluence_score": 0.8,
        "confidence": 0.8,
        "chosen_strategy": "event_driven",
        "fib_levels_drawn": {},
        "narrative_reasoning": "n",
    }
    app = _base_app(infer_return=dream, event_bus=Bus())
    PreDreamVisionCycleService(app=app).run_cycle(**_vision_inputs())
    assert len(published) == 1
    assert published[0]["topic"] == TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC
    assert published[0]["producer"] == "runtime_workers.pre_dream_daemon"
