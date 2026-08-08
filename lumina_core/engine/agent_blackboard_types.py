from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from lumina_core.agent_orchestration.schemas import (
    BLACKBOARD_TOPIC_MODELS,
    model_validate_payload_with_instance,
)
from lumina_core.state.state_manager import safe_append_jsonl

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
    "meta.reflection": {"meta_agent_orchestrator", "test"},
    "meta.hyperparameters": {"meta_agent_orchestrator", "test"},
    "meta.retraining": {"meta_agent_orchestrator", "test"},
    "meta.bible_update": {"meta_agent_orchestrator", "test"},
    "meta.evolution_result": {"meta_agent_orchestrator", "evolution_orchestrator", "test"},
    "meta.dna_lineage": {"meta_agent_orchestrator", "test"},
    "agent.meta.proposal": {"self_evolution_meta_agent", "test"},
}


DEFAULT_TOPIC_POLICIES: dict[str, TopicPolicy] = {
    "agent.rl.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.news.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.emotional_twin.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.swarm.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.tape.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.swarm.snapshot": TopicPolicy(critical=False, overflow_strategy="drop"),
    "market.tape": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.reflection": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.hyperparameters": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.retraining": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.bible_update": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.evolution_result": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.dna_lineage": TopicPolicy(critical=False, overflow_strategy="drop"),
    "agent.meta.proposal": TopicPolicy(critical=False, overflow_strategy="drop"),
}



__all__ = ['BlackboardEvent', 'TopicPolicy', 'DEFAULT_ALLOWED_PRODUCERS', 'DEFAULT_TOPIC_POLICIES']
