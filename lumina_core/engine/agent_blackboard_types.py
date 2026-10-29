from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import BaseModel

from lumina_core.agent_orchestration.schemas_research import (
    CAPACITY_AGENT_ID,
    FILL_AGENT_ID,
    FILL_TRANSLATOR_AGENT_ID,
    GOVERNANCE_AGENT_ID,
    GUARDIAN_AGENT_ID,
    HYPOTHESIS_AGENT_ID,
    MONITOR_AGENT_ID,
    PROMOTION_AGENT_ID,
    REFLECTOR_AGENT_ID,
    REPLENISH_AGENT_ID,
    RESEARCH_BRIDGE_AGENT_ID,
    RESEARCH_CAPACITY_TOPIC,
    RESEARCH_DECAY_TOPIC,
    RESEARCH_DEWEIGHT_TOPIC,
    RESEARCH_EXECUTION_ALERT_TOPIC,
    RESEARCH_EXECUTION_FILL_TOPIC,
    RESEARCH_EXECUTION_ORDER_TOPIC,
    RESEARCH_EXECUTION_SIGNAL_TOPIC,
    RESEARCH_FILL_OBSERVED_TOPIC,
    RESEARCH_GOVERNANCE_TOPIC,
    RESEARCH_GUARDIAN_TOPIC,
    RESEARCH_HYPOTHESIS_TOPIC,
    RESEARCH_MUTATION_TOPIC,
    RESEARCH_ORDER_INTENT_TOPIC,
    RESEARCH_PROMOTION_TOPIC,
    RESEARCH_REPLENISH_TOPIC,
    RESEARCH_RETIRE_TOPIC,
    RESEARCH_SIGNAL_INTENT_TOPIC,
    RESEARCH_SUSPEND_TOPIC,
    RESEARCH_VALIDATION_TOPIC,
    SAFETY_AGENT_ID,
    SHADOW_AGENT_ID,
    VALIDATION_AGENT_ID,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BlackboardEvent:
    topic: str
    producer: str
    payload: dict[str, Any]
    confidence: float
    timestamp: str
    correlation_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    sequence: int = 0
    prev_hash: str = "GENESIS"
    event_hash: str = ""
    payload_instance: BaseModel | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        inst = data.pop("payload_instance", None)
        if isinstance(inst, BaseModel):
            canonical = inst.model_dump(mode="json", exclude_none=False)
            data["payload"] = canonical
            data["payload_instance"] = canonical
            data["payload_model"] = type(inst).__name__
        return data


@dataclass(slots=True)
class TopicPolicy:
    critical: bool = False
    overflow_strategy: str = "drop"


DEFAULT_ALLOWED_PRODUCERS: dict[str, set[str]] = {
    "agent.rl.proposal": {"rl_policy", "test"},
    "agent.news.proposal": {"news_agent", "runtime_workers.pre_dream_daemon", "test"},
    "agent.emotional_twin.proposal": {"emotional_twin_agent", "test"},
    "agent.swarm.proposal": {"swarm_manager", "test"},
    "agent.swarm.snapshot": {"swarm_manager", "test"},
    "agent.tape.proposal": {"market_data_service", "tape_reading_agent", "test"},
    "market.tape": {"market_data_service", "tape_reading_agent", "test"},
    "market.bar_integrity": {"market_data_service", "test"},
    "meta.reflection": {"meta_agent_orchestrator", "test"},
    "meta.hyperparameters": {"meta_agent_orchestrator", "test"},
    "meta.retraining": {"meta_agent_orchestrator", "test"},
    "meta.bible_update": {"meta_agent_orchestrator", "test"},
    "meta.evolution_result": {"meta_agent_orchestrator", "evolution_orchestrator", "test"},
    "meta.dna_lineage": {"meta_agent_orchestrator", "test"},
    "agent.meta.proposal": {"self_evolution_meta_agent", "test"},
    RESEARCH_HYPOTHESIS_TOPIC: {HYPOTHESIS_AGENT_ID},
    RESEARCH_VALIDATION_TOPIC: {VALIDATION_AGENT_ID},
    RESEARCH_PROMOTION_TOPIC: {PROMOTION_AGENT_ID},
    RESEARCH_MUTATION_TOPIC: {REFLECTOR_AGENT_ID},
    RESEARCH_GOVERNANCE_TOPIC: {GOVERNANCE_AGENT_ID},
    RESEARCH_DECAY_TOPIC: {MONITOR_AGENT_ID},
    RESEARCH_DEWEIGHT_TOPIC: {MONITOR_AGENT_ID},
    RESEARCH_SUSPEND_TOPIC: {MONITOR_AGENT_ID},
    RESEARCH_RETIRE_TOPIC: {MONITOR_AGENT_ID},
    RESEARCH_CAPACITY_TOPIC: {CAPACITY_AGENT_ID},
    RESEARCH_GUARDIAN_TOPIC: {GUARDIAN_AGENT_ID},
    RESEARCH_REPLENISH_TOPIC: {REPLENISH_AGENT_ID},
    RESEARCH_EXECUTION_SIGNAL_TOPIC: {RESEARCH_BRIDGE_AGENT_ID},
    RESEARCH_EXECUTION_ORDER_TOPIC: {RESEARCH_BRIDGE_AGENT_ID},
    RESEARCH_EXECUTION_FILL_TOPIC: {RESEARCH_BRIDGE_AGENT_ID, FILL_TRANSLATOR_AGENT_ID},
    RESEARCH_SIGNAL_INTENT_TOPIC: {SHADOW_AGENT_ID},
    RESEARCH_ORDER_INTENT_TOPIC: {SHADOW_AGENT_ID},
    RESEARCH_FILL_OBSERVED_TOPIC: {FILL_AGENT_ID, SHADOW_AGENT_ID},
    RESEARCH_EXECUTION_ALERT_TOPIC: {SAFETY_AGENT_ID},
}


DEFAULT_TOPIC_POLICIES: dict[str, TopicPolicy] = {
    "agent.rl.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.news.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.emotional_twin.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.swarm.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.tape.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.swarm.snapshot": TopicPolicy(critical=False, overflow_strategy="drop"),
    "market.tape": TopicPolicy(critical=False, overflow_strategy="drop"),
    "market.bar_integrity": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "meta.reflection": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.hyperparameters": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.retraining": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.bible_update": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.evolution_result": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.dna_lineage": TopicPolicy(critical=False, overflow_strategy="drop"),
    "agent.meta.proposal": TopicPolicy(critical=False, overflow_strategy="drop"),
    RESEARCH_HYPOTHESIS_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_VALIDATION_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_PROMOTION_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_MUTATION_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_GOVERNANCE_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_DECAY_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_DEWEIGHT_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_SUSPEND_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_RETIRE_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_CAPACITY_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_GUARDIAN_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_REPLENISH_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_EXECUTION_SIGNAL_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_EXECUTION_ORDER_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_EXECUTION_FILL_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_SIGNAL_INTENT_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_ORDER_INTENT_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_FILL_OBSERVED_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
    RESEARCH_EXECUTION_ALERT_TOPIC: TopicPolicy(critical=True, overflow_strategy="block_fail"),
}



__all__ = ['BlackboardEvent', 'TopicPolicy', 'DEFAULT_ALLOWED_PRODUCERS', 'DEFAULT_TOPIC_POLICIES']
