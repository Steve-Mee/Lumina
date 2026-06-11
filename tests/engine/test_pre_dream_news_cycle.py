"""Tests for PreDreamNewsCycleService (D2 sub-slice 21)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.engine.pre_dream_news_cycle import PreDreamNewsCycleService


def _base_app(*, blackboard_proposals: list | None = None, news_agent: object | None = None) -> SimpleNamespace:
    proposals: list = blackboard_proposals if blackboard_proposals is not None else []

    def _bb_add(**k: object) -> None:
        proposals.append(k)

    return SimpleNamespace(
        engine=SimpleNamespace(
            config=SimpleNamespace(news_impact_multipliers={}),
        ),
        world_model={"macro": {}},
        get_current_dream_snapshot=lambda: {"hold_until_ts": 0.0},
        resolve_news_multiplier=lambda *_a, **_k: 1.25,
        set_current_dream_value=lambda *_a, **_k: None,
        set_current_dream_fields=lambda *_a, **_k: None,
        get_high_impact_news=lambda: {"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        blackboard=SimpleNamespace(add_proposal=_bb_add),
        news_agent=news_agent,
        logger=SimpleNamespace(error=lambda *_a, **_k: None),
        _proposals=proposals,
    )


@pytest.mark.unit
def test_run_news_cycle_avoidance_emits_hold_proposal():
    proposals: list = []

    class NewsAgent:
        def run_news_cycle(self) -> dict:
            return {
                "news_avoidance_window": True,
                "news_avoidance_hold_until_ts": 9999999999.0,
                "news_avoidance_reason": "cpi",
                "confidence": 0.9,
                "news_data": {"events": [], "overall_sentiment": "bearish", "impact": "high"},
                "sentiment_signal": "bearish",
                "sentiment_score": -0.5,
                "dynamic_multiplier": 0.8,
            }

    app = _base_app(blackboard_proposals=proposals, news_agent=NewsAgent())
    ctx = "dream_cycle:abc123"
    result = PreDreamNewsCycleService(app=app).run_cycle(
        cycle_decision_context_id=ctx,
        cached_news_data={"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        last_news_update_ts=0.0,
        blackboard=app.blackboard,
    )
    assert any(
        p.get("payload", {}).get("signal") == "HOLD"
        and p.get("payload", {}).get("decision_context_id") == ctx
        and p.get("correlation_id") == ctx
        for p in proposals
    )
    assert result.avoid_active is False
    assert result.news_impact == 1.25
    print("MANUAL_SMOKE_SUB21_NEWS_SUCCESS")


@pytest.mark.unit
def test_no_agent_fallback_fetches_high_impact_news(monkeypatch):
    proposals: list = []
    calls = {"fetch": 0}

    app = _base_app(blackboard_proposals=proposals, news_agent=None)
    app.get_high_impact_news = lambda: calls.__setitem__("fetch", calls["fetch"] + 1) or {
        "events": [{"title": "x"}],
        "overall_sentiment": "neutral",
        "impact": "low",
    }

    monkeypatch.setattr("lumina_core.engine.pre_dream_news_cycle.time.time", lambda: 100.0)
    result = PreDreamNewsCycleService(app=app).run_cycle(
        cycle_decision_context_id="dream_cycle:ctx1",
        cached_news_data={"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        last_news_update_ts=0.0,
        blackboard=app.blackboard,
    )
    assert calls["fetch"] == 1
    assert result.last_news_update_ts == 100.0
    assert any("news_impact" in str(p.get("payload", {})) for p in proposals)


@pytest.mark.unit
def test_run_cycle_fallback_updates_cached_news_data():
    class LegacyNewsAgent:
        def run_cycle(self) -> dict:
            return {"news_data": {"events": [1], "overall_sentiment": "bullish", "impact": "high"}}

    app = _base_app(news_agent=LegacyNewsAgent())
    result = PreDreamNewsCycleService(app=app).run_cycle(
        cycle_decision_context_id="dream_cycle:ctx2",
        cached_news_data={"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        last_news_update_ts=0.0,
        blackboard=app.blackboard,
    )
    assert result.cached_news_data.get("overall_sentiment") == "bullish"


@pytest.mark.unit
def test_agent_exception_fail_closed_no_raise():
    class BrokenAgent:
        def run_news_cycle(self) -> dict:
            raise RuntimeError("news down")

    app = _base_app(news_agent=BrokenAgent())
    result = PreDreamNewsCycleService(app=app).run_cycle(
        cycle_decision_context_id="dream_cycle:ctx3",
        cached_news_data={"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        last_news_update_ts=0.0,
        blackboard=app.blackboard,
    )
    assert result.news_impact == 1.25
