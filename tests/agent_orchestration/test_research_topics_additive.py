"""Additive research topics must not change existing Event Bus / Blackboard behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from lumina_core.agent_orchestration import event_bus as event_bus_mod
from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import (
    EVENT_BUS_TOPIC_MODELS,
    RESEARCH_HYPOTHESIS_TOPIC,
    RESEARCH_PROMOTION_TOPIC,
    RESEARCH_VALIDATION_TOPIC,
)
from lumina_core.engine.agent_blackboard_types import DEFAULT_ALLOWED_PRODUCERS
from lumina_core.agent_orchestration.schemas_research import EVENT_BUS_GUARDED_TOPICS
from lumina_core.agent_orchestration.schemas_research import (
    EconomicRationale,
    HypothesisProposed,
    PROMOTION_AGENT_ID,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard


@pytest.mark.unit
def test_existing_untyped_topic_still_accepts_arbitrary_payload() -> None:
    bus = EventBus()
    event = bus.publish(
        topic="legacy.custom.topic",
        producer="legacy_migrator",
        payload={"field": "value", "count": "not_typed"},
    )
    assert event.payload == {"field": "value", "count": "not_typed"}
    assert event.producer == "legacy_migrator"


@pytest.mark.unit
def test_existing_critical_topic_still_fail_closes_on_unknown_fields() -> None:
    bus = EventBus()
    with pytest.raises(ValidationError):
        bus.publish(
            topic="risk.policy.decision",
            producer="risk_controller",
            payload={"approved": True, "novel_untyped_field": "blocked"},
        )


@pytest.mark.unit
def test_guard_cannot_be_attached_to_existing_topic() -> None:
    bus = EventBus()
    with pytest.raises(ValueError, match="existing Event Bus topics stay unguarded"):
        bus.register_topic_guard("risk.policy.decision", lambda _p, _d: True)


@pytest.mark.unit
def test_research_topics_are_registered_and_guarded_additively() -> None:
    assert RESEARCH_HYPOTHESIS_TOPIC in EVENT_BUS_TOPIC_MODELS
    assert RESEARCH_VALIDATION_TOPIC in EVENT_BUS_TOPIC_MODELS
    assert RESEARCH_PROMOTION_TOPIC in EVENT_BUS_TOPIC_MODELS
    assert EVENT_BUS_GUARDED_TOPICS == frozenset({RESEARCH_PROMOTION_TOPIC, RESEARCH_VALIDATION_TOPIC})


@pytest.mark.unit
def test_unauthorized_producer_cannot_publish_hypothesis() -> None:
    bus = EventBus()
    rationale = EconomicRationale(
        mechanism="Inventory premium on a drift tape after costs xx",
        why_edge_exists="Impatient flow pays spread so inventory can earn drift",
        other_side="Noise traders demanding immediacy in the tape",
        expected_regime="trend-up moderate volatility regime",
        falsification_criterion="median OOS after costs <= 0 or PBO > 0.50",
    )
    payload = HypothesisProposed(
        hypothesis_id="hyp-x",
        config_id="cfg-x",
        trial_id=1,
        agent_id="hypothesis_agent",
        generator_id="noise",
        kind="noise",
        instrument="MES",
        seed=1,
        n_obs=360,
        mu=0.0,
        sigma=0.01,
        planted=False,
        proposed_quantity=1.0,
        proposed_price=5000.0,
        proposed_notional=5000.0,
        rationale=rationale,
    ).model_dump(mode="json")
    with pytest.raises(PermissionError):
        bus.publish(topic=RESEARCH_HYPOTHESIS_TOPIC, producer="rogue_agent", payload=payload)


@pytest.mark.unit
def test_promotion_candidate_without_guard_is_rejected() -> None:
    bus = EventBus()
    with pytest.raises(PermissionError, match="issuer guard"):
        bus.publish(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer=PROMOTION_AGENT_ID,
            payload={
                "hypothesis_id": "hyp-x",
                "config_id": "cfg-x",
                "trial_id": 1,
                "agent_id": PROMOTION_AGENT_ID,
                "instrument": "MES",
                "decision_kind": "approved",
                "scaled": False,
                "quantity": 1.0,
                "notional": 1000.0,
                "risk_reason": "approved",
                "validation_report_sha256": "a" * 64,
                "validation_mac": "b" * 64,
                "issue_mac": "c" * 64,
            },
        )


@pytest.mark.unit
def test_event_bus_public_export_list_is_unchanged() -> None:
    assert event_bus_mod.__all__ == [
        "AgentReflection",
        "BirthAutonomyDecision",
        "BirthCertificateRemediationRequested",
        "BirthCurriculumStageAborted",
        "BirthCurriculumStageCompleted",
        "BirthCurriculumStageRequested",
        "BirthCurriculumStageStarted",
        "BirthCurriculumStarted",
        "BirthMetaPlan",
        "BirthPhoenixCycle",
        "BirthPlateauEntered",
        "BirthPlateauEvolutionStep",
        "BirthPlateauTrapDetected",
        "BirthStageRolloutSnapshot",
        "BirthStallRemediationCycle",
        "BirthStallRemediationStep",
        "CommunityKnowledgeSnippet",
        "ConstitutionAudit",
        "ConstitutionViolation",
        "DreamState",
        "DomainEvent",
        "EventBus",
        "EvolutionPromotionDecision",
        "EvolutionProposal",
        "FinalArbitrationResult",
        "LLMDecisionContext",
        "MetaAgentThought",
        "RiskVerdict",
        "ShadowResult",
        "TradeIntent",
    ]


@pytest.mark.unit
def test_existing_blackboard_test_producer_is_unchanged() -> None:
    assert "test" in DEFAULT_ALLOWED_PRODUCERS["agent.rl.proposal"]
    assert "test" not in DEFAULT_ALLOWED_PRODUCERS[RESEARCH_PROMOTION_TOPIC]


@pytest.mark.unit
def test_blackboard_rejects_rogue_promotion_producer(tmp_path: Path) -> None:
    board = AgentBlackboard(persistence_path=tmp_path / "bb.jsonl")
    with pytest.raises(PermissionError):
        board.publish_sync(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer="rogue_agent",
            payload={"hypothesis_id": "x"},
            confidence=1.0,
        )
