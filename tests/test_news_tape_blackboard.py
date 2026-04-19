from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from lumina_agents.news_agent import NewsAgent
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_core.engine.market_data_service import MarketDataService


def test_news_agent_publishes_blackboard_proposal(tmp_path) -> None:
    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    app = SimpleNamespace(
        get_high_impact_news=lambda: {
            "events": [{"event": "FOMC Rate Decision", "impact": "high", "date": "2099-01-01", "time": "14:00"}],
            "overall_sentiment": "neutral",
            "impact": "high",
        },
        world_model={},
        logger=SimpleNamespace(info=lambda *_a, **_k: None),
    )
    engine = SimpleNamespace(
        app=app,
        blackboard=bus,
        config=SimpleNamespace(
            xai_model="grok-4.1-fast",
            xai_key="",
            xai_update_interval_sec=60,
            news_avoidance_minutes=3,
            news_avoidance_post_minutes=5,
            news_avoidance_high_impact_pre_minutes=15,
            news_avoidance_high_impact_post_minutes=10,
            news_impact_multipliers={},
        ),
        decision_log=None,
        get_current_dream_snapshot=lambda: {"signal": "BUY"},
    )

    agent = NewsAgent(engine=cast(Any, engine))
    result = agent.run_news_cycle()

    assert isinstance(result, dict)
    proposal = bus.latest("agent.news.proposal")
    assert proposal is not None
    assert proposal.producer == "news_agent"
    assert "news_impact" in proposal.payload


def test_market_data_service_publishes_tape_topics(tmp_path) -> None:
    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    engine = SimpleNamespace(app=SimpleNamespace(), blackboard=bus)
    service = MarketDataService(engine=cast(Any, engine))

    service._publish_tape_signal(
        {
            "signal": "BUY",
            "direction": "BUY",
            "confidence": 0.88,
            "reason": "strong tape buy",
            "fast_path_trigger": True,
            "cumulative_delta_10": 1200.0,
            "bid_ask_imbalance": 1.9,
        }
    )

    proposal = bus.latest("agent.tape.proposal")
    market = bus.latest("market.tape")
    assert proposal is not None
    assert market is not None
    assert proposal.payload["tape_signal"] == "BUY"
    assert market.payload["signal"] == "BUY"
