"""Research-side Execution Fabric ports: shadow only, no NT8 coupling, no orders."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    RESEARCH_SIGNAL_INTENT_TOPIC,
    ResearchFillEvent,
    ResearchOrderIntent,
    SignalIntent,
)
from lumina_core.risk.schemas import OrderIntent as LiveOrderIntent
from lumina_research.agents.generators import NoiseGenerator
from lumina_research.agents.hypothesis import HypothesisAgent
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.ports.fail_closed import decide_failure
from lumina_research.ports.fills import FillSink, PortRefused
from lumina_research.ports.shadow import ShadowBook
from lumina_research.ports.sim_safety import SimSafetyConfig, SimSafetyGate, SimSafetyRefused
from lumina_research.validation.trial_registry import TrialRegistry


def _fill(*, fabric: bool = False) -> ResearchFillEvent:
    return ResearchFillEvent(
        strategy_id="s1",
        fill_price=5000.0,
        qty=1.0,
        slippage=0.4,
        commission=0.1,
        timestamp="2026-10-28T00:00:00+00:00",
        fill_id="f1",
        instrument="MES",
        client_order_id="c1",
        source="fabric" if fabric else "cost_model",
        provenance_mac="a" * 64,
    )


@pytest.mark.unit
def test_sim_safety_refuses_live_and_sim_and_cannot_be_mutated() -> None:
    gate = SimSafetyGate()
    assert gate.config.live_release is False
    assert gate.config.sim_whitelist == frozenset()
    gate.admit(mode="shadow", account_id="SHADOW")
    with pytest.raises(SimSafetyRefused, match="LIVE_RELEASE"):
        gate.admit(mode="live", account_id="REAL1")
    with pytest.raises(SimSafetyRefused, match="whitelist"):
        gate.admit(mode="sim", account_id="SIM1")
    with pytest.raises(SimSafetyRefused, match="cannot mutate"):
        gate.set_whitelist({"SIM1"})
    with pytest.raises(SimSafetyRefused, match="cannot mutate"):
        gate.add_account("SIM1")
    with pytest.raises(SimSafetyRefused, match="LIVE_RELEASE"):
        gate.set_live_release(True, adr_path="docs/adr/9999-live.md")
    with pytest.raises(SimSafetyRefused, match="dedicated ADR"):
        gate.apply_live_release(review=object(), adr_path="docs/adr/9999-live.md")
    with pytest.raises(AttributeError):
        gate.config = SimSafetyConfig()  # type: ignore[misc]
    with pytest.raises(SimSafetyRefused, match="LIVE_RELEASE cannot be enabled"):
        SimSafetyConfig(live_release=True)
    with pytest.raises(SimSafetyRefused, match="shadow mode only"):
        SimSafetyConfig(allowed_modes=frozenset({"sim"}))
    with pytest.raises(SimSafetyRefused, match="whitelist"):
        SimSafetyConfig(sim_whitelist=frozenset({"SIM1"}))


@pytest.mark.unit
def test_sim_safety_from_mapping_and_stale_link() -> None:
    cfg = SimSafetyConfig.from_mapping({})
    assert cfg.live_release is False
    with pytest.raises(SimSafetyRefused, match="unknown"):
        SimSafetyConfig.from_mapping({"nope": 1})
    with pytest.raises(SimSafetyRefused, match="sequence"):
        SimSafetyConfig.from_mapping({"sim_whitelist": "SIM1"})
    with pytest.raises(SimSafetyRefused, match="live_release must be a bool"):
        SimSafetyConfig.from_mapping({"live_release": "yes"})
    with pytest.raises(SimSafetyRefused, match="LIVE_RELEASE cannot be enabled"):
        SimSafetyConfig.from_mapping({"live_release": True})
    gate = SimSafetyGate()
    with pytest.raises(SimSafetyRefused, match="stale data"):
        gate.admit(mode="shadow", account_id="SHADOW", stale_data=True)
    with pytest.raises(SimSafetyRefused, match="lost connection"):
        gate.admit(mode="shadow", account_id="SHADOW", lost_connection=True)


@pytest.mark.unit
def test_fail_closed_matrix() -> None:
    stale = decide_failure(
        stale_data=True,
        lost_connection=False,
        monitor_alarm=False,
        open_position=True,
        risk_core_limit=False,
    )
    assert stale.allow_new_orders is False
    assert stale.action == "broker_protect"
    assert stale.flatten_recommended is False
    lost = decide_failure(
        stale_data=False,
        lost_connection=True,
        monitor_alarm=False,
        open_position=False,
        risk_core_limit=False,
    )
    assert lost.action == "refuse_new_orders"
    alarm = decide_failure(
        stale_data=False,
        lost_connection=False,
        monitor_alarm=True,
        open_position=True,
        risk_core_limit=False,
    )
    assert alarm.action == "deweight_reduce"
    assert alarm.flatten_recommended is False
    hard = decide_failure(
        stale_data=False,
        lost_connection=False,
        monitor_alarm=True,
        open_position=True,
        risk_core_limit=True,
    )
    assert hard.action == "flatten_hard_limit"
    assert hard.flatten_recommended is True


@pytest.mark.unit
def test_fill_sink_refuses_fabric_and_connect() -> None:
    sink = FillSink()
    sink.ingest(_fill())
    assert len(sink.fills()) == 1
    with pytest.raises(PortRefused, match="NT8 coupling"):
        sink.ingest(_fill(fabric=True))
    with pytest.raises(PortRefused, match="NT8 coupling"):
        sink.connect_fabric()
    with pytest.raises(AttributeError):
        sink._fills = []  # noqa: SLF001


@pytest.mark.unit
def test_shadow_book_logs_hypothetical_fill_and_never_orders(tmp_path: Path) -> None:
    bus = EventBus()
    book = ShadowBook(
        bus=bus,
        authority=ProvenanceAuthority(),
        experiment_log_path=tmp_path / "exp.jsonl",
    )
    signal, fill, decision = book.observe_signal(
        strategy_id="hyp-1",
        direction="buy",
        size=1.0,
        expected_horizon="intraday",
        instrument="MES",
        limit_price=5000.25,
    )
    assert signal.mode == "shadow"
    assert fill is not None
    assert fill.source == "cost_model"
    assert fill.slippage > 0.0 or fill.commission >= 0.0
    assert decision.allow_new_orders is True
    assert len(book.signals()) == 1
    assert len(book.orders()) == 1
    assert len(book.fills()) == 1
    with pytest.raises(PortRefused, match="does not place orders"):
        book.place_order()
    with pytest.raises(PortRefused, match="does not place orders"):
        book.submit_order(strategy_id="hyp-1")
    with pytest.raises(PortRefused, match="flatten"):
        book.flatten()
    with pytest.raises(PortRefused, match="NT8 coupling"):
        book.connect_fabric()
    with pytest.raises(PortRefused, match="fail-closed"):
        book.observe_signal(
            strategy_id="hyp-2",
            direction="sell",
            size=1.0,
            expected_horizon="session",
            instrument="ES",
            limit_price=5000.0,
            stale_data=True,
            open_position=True,
        )
    assert book.alerts()
    with pytest.raises(PortRefused, match="live"):
        book.observe_signal(
            strategy_id="hyp-3",
            direction="buy",
            size=1.0,
            expected_horizon="swing",
            instrument="NQ",
            limit_price=16000.0,
            mode="live",
        )
    with pytest.raises(PermissionError):
        bus.publish(
            topic=RESEARCH_SIGNAL_INTENT_TOPIC,
            producer="rogue_agent",
            payload=signal.model_dump(mode="json"),
        )


@pytest.mark.unit
def test_hypothesis_agent_cannot_mutate_sim_safety(tmp_path: Path) -> None:
    gate = SimSafetyGate()
    agent = HypothesisAgent(
        bus=EventBus(),
        registry=TrialRegistry(tmp_path / "t.jsonl"),
        generators=(NoiseGenerator(),),
        experiment_log_path=tmp_path / "e.jsonl",
    )
    with pytest.raises(SimSafetyRefused):
        gate.set_whitelist({"SIM-HYP"})
    assert not hasattr(agent, "set_whitelist")
    assert not hasattr(agent, "set_live_release")


@pytest.mark.unit
def test_signal_intent_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        SignalIntent.model_validate(
            {
                "strategy_id": "s",
                "direction": "buy",
                "size": 1.0,
                "timestamp": "t",
                "expected_horizon": "intraday",
                "instrument": "MES",
                "account_id": "SHADOW",
                "mode": "shadow",
                "client_order_id": "c",
                "provenance_mac": "a" * 64,
                "broker_account": "bypass",
            }
        )


@pytest.mark.unit
def test_unknown_mode_and_lost_connection_alert(tmp_path: Path) -> None:
    book = ShadowBook(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        experiment_log_path=tmp_path / "exp.jsonl",
    )
    with pytest.raises(PortRefused, match="unknown mode"):
        book.observe_signal(
            strategy_id="hyp-x",
            direction="buy",
            size=1.0,
            expected_horizon="intraday",
            instrument="MES",
            limit_price=1.0,
            mode="paper",
        )
    with pytest.raises(PortRefused, match="fail-closed"):
        book.observe_signal(
            strategy_id="hyp-y",
            direction="buy",
            size=1.0,
            expected_horizon="intraday",
            instrument="MES",
            limit_price=1.0,
            lost_connection=True,
        )
    with pytest.raises(PortRefused, match="fail-closed"):
        book.observe_signal(
            strategy_id="hyp-z",
            direction="buy",
            size=1.0,
            expected_horizon="intraday",
            instrument="MES",
            limit_price=1.0,
            monitor_alarm=True,
            open_position=True,
        )
    with pytest.raises(PortRefused, match="fail-closed"):
        book.observe_signal(
            strategy_id="hyp-r",
            direction="buy",
            size=1.0,
            expected_horizon="intraday",
            instrument="MES",
            limit_price=1.0,
            risk_core_limit=True,
        )
    kinds = {item.kind for item in book.alerts()}
    assert "lost_connection" in kinds
    assert "monitor_alarm" in kinds
    assert "risk_core_limit" in kinds


@pytest.mark.unit
def test_research_order_intent_is_not_live_risk_order_intent() -> None:
    assert ResearchOrderIntent is not LiveOrderIntent
    assert "strategy_id" in ResearchOrderIntent.model_fields
    assert "strategy_id" not in LiveOrderIntent.model_fields
    assert "expected_horizon" in ResearchOrderIntent.model_fields
