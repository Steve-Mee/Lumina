from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration import EventBus
from lumina_core.audit.audit_log_service import AuditLogService
from lumina_core.broker.broker_bridge import PaperBroker
from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.market_data_service import MarketDataIngestService
from lumina_core.ports import (
    AuditPort,
    BrokerPort,
    DreamStatePort,
    ExecutionPort,
    MarketDataPort,
    OrchestrationPort,
    ReasoningPort,
    RiskPort,
)
from lumina_core.reasoning.reasoning_service import ReasoningService


@pytest.mark.unit
def test_runtime_implementations_satisfy_port_protocols(tmp_path: Path) -> None:
    # gegeven
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live_stream.jsonl",
        trade_decision_audit_log=tmp_path / "trade_decision_audit.jsonl",
    )
    engine = LuminaEngine(config=cfg)
    audit = AuditLogService(path=tmp_path / "trade_decision_audit.jsonl", enabled=True)
    broker = PaperBroker(engine=engine)
    event_bus = EventBus()
    market_data = MarketDataIngestService(engine=engine)
    reasoning = ReasoningService(engine=engine)

    # wanneer/dan
    assert engine.risk_orchestrator is not None
    assert isinstance(engine.risk_orchestrator, RiskPort)
    assert isinstance(audit, AuditPort)
    assert isinstance(broker, BrokerPort)
    assert isinstance(event_bus, OrchestrationPort)
    assert isinstance(market_data, MarketDataPort)
    assert engine.execution_service is not None
    assert isinstance(engine.execution_service, ExecutionPort)
    assert isinstance(engine, DreamStatePort)
    assert isinstance(reasoning, ReasoningPort)
