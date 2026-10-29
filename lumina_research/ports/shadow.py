"""Shadow execution: log SignalIntent, hypothetical fills via CostModel, no orders."""

from __future__ import annotations

from pathlib import Path

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    FILL_AGENT_ID,
    RESEARCH_EXECUTION_ALERT_TOPIC,
    RESEARCH_FILL_OBSERVED_TOPIC,
    RESEARCH_ORDER_INTENT_TOPIC,
    RESEARCH_SIGNAL_INTENT_TOPIC,
    SAFETY_AGENT_ID,
    SHADOW_AGENT_ID,
    ExecutionAlert,
    ExecutionMode,
    ExpectedHorizon,
    IntentDirection,
    ResearchFillEvent,
    ResearchOrderIntent,
    SignalIntent,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.experiment_log import log_experiment
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.ports.fail_closed import FailClosedDecision, decide_failure
from lumina_research.ports.fills import FillSink, PortRefused
from lumina_research.ports.seal import (
    accept_mac,
    canonical_alert,
    canonical_fill,
    canonical_order,
    canonical_signal,
)
from lumina_research.ports.sim_safety import SimSafetyGate, SimSafetyRefused
from lumina_research.validation.audit import utc_now_iso
from lumina_research.validation.contracts import spec_for
from lumina_research.validation.cost_model import CostModel, MarketSnapshot


class ShadowBook(Frozen):
    """Phase 5 execution surface. Signals are logged. Nothing is sent to Fabric."""

    _bus: EventBus
    _authority: ProvenanceAuthority
    _gate: SimSafetyGate
    _sink: FillSink
    _log_path: Path
    _blackboard: AgentBlackboard | None
    _model: CostModel
    _signals: list[SignalIntent]
    _orders: list[ResearchOrderIntent]
    _alerts: list[ExecutionAlert]
    _seq: list[int]
    _seen: set[str]

    def __init_subclass__(cls) -> None:
        raise TypeError("ShadowBook cannot be subclassed")

    def __init__(
        self,
        *,
        bus: EventBus,
        authority: ProvenanceAuthority,
        experiment_log_path: Path,
        gate: SimSafetyGate | None = None,
        sink: FillSink | None = None,
        blackboard: AgentBlackboard | None = None,
        model: CostModel | None = None,
    ) -> None:
        self._bus = bus
        self._authority = authority
        self._gate = gate if gate is not None else SimSafetyGate()
        self._sink = sink if sink is not None else FillSink()
        self._log_path = experiment_log_path
        self._blackboard = blackboard
        self._model = model if model is not None else CostModel()
        self._signals = []
        self._orders = []
        self._alerts = []
        self._seq = [0]
        self._seen = set()
        self._freeze()
        bus.register_topic_guard(RESEARCH_SIGNAL_INTENT_TOPIC, self._guard_signal)
        bus.register_topic_guard(RESEARCH_ORDER_INTENT_TOPIC, self._guard_order)
        bus.register_topic_guard(RESEARCH_FILL_OBSERVED_TOPIC, self._guard_fill)
        bus.register_topic_guard(RESEARCH_EXECUTION_ALERT_TOPIC, self._guard_alert)
        if blackboard is not None:
            blackboard.register_topic_guard(RESEARCH_SIGNAL_INTENT_TOPIC, self._guard_signal_bb)
            blackboard.register_topic_guard(RESEARCH_ORDER_INTENT_TOPIC, self._guard_order_bb)
            blackboard.register_topic_guard(RESEARCH_FILL_OBSERVED_TOPIC, self._guard_fill_bb)
            blackboard.register_topic_guard(RESEARCH_EXECUTION_ALERT_TOPIC, self._guard_alert_bb)

    def signals(self) -> tuple[SignalIntent, ...]:
        return tuple(self._signals)

    def orders(self) -> tuple[ResearchOrderIntent, ...]:
        return tuple(self._orders)

    def fills(self) -> tuple[ResearchFillEvent, ...]:
        return self._sink.fills()

    def alerts(self) -> tuple[ExecutionAlert, ...]:
        return tuple(self._alerts)

    def place_order(self, *_args: object, **_kwargs: object) -> None:
        raise PortRefused("Phase 5 does not place orders")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise PortRefused("Phase 5 does not place orders")

    def flatten(self, *_args: object, **_kwargs: object) -> None:
        raise PortRefused("Phase 5 does not send flatten; broker is the source of truth")

    def connect_fabric(self) -> None:
        raise PortRefused("NT8 coupling is not implemented in this PR")

    def observe_signal(
        self,
        *,
        strategy_id: str,
        direction: IntentDirection,
        size: float,
        expected_horizon: ExpectedHorizon,
        instrument: str,
        account_id: str = "SHADOW",
        mode: str = "shadow",
        limit_price: float,
        volume: float = 10_000.0,
        average_volume: float = 10_000.0,
        volatility_price: float = 2.0,
        stale_data: bool = False,
        lost_connection: bool = False,
        monitor_alarm: bool = False,
        open_position: bool = False,
        risk_core_limit: bool = False,
    ) -> tuple[SignalIntent, ResearchFillEvent | None, FailClosedDecision]:
        """Log a shadow signal and a cost_model hypothetical fill. Never orders."""
        failure = decide_failure(
            stale_data=stale_data,
            lost_connection=lost_connection,
            monitor_alarm=monitor_alarm,
            open_position=open_position,
            risk_core_limit=risk_core_limit,
        )
        if not failure.allow_new_orders:
            self._emit_alert(failure, open_position=open_position)
            raise PortRefused("fail-closed: no new orders")
        mapped = _mode(mode)
        try:
            self._gate.admit(
                mode=mapped,
                account_id=account_id,
                stale_data=stale_data,
                lost_connection=lost_connection,
            )
        except SimSafetyRefused as exc:
            raise PortRefused(str(exc)) from exc
        if mapped != "shadow":
            raise PortRefused("Phase 5 allows shadow mode only")
        stamp = utc_now_iso()
        self._seq[0] += 1
        client_id = f"shadow-{self._seq[0]}-{strategy_id}"
        unsigned_signal: dict[str, object] = {
            "schema_version": "research.signal.intent.v1",
            "strategy_id": strategy_id,
            "direction": direction,
            "size": size,
            "timestamp": stamp,
            "expected_horizon": expected_horizon,
            "instrument": instrument,
            "account_id": account_id,
            "mode": mapped,
            "client_order_id": client_id,
        }
        mac = self._authority.mac(canonical_signal(unsigned_signal))
        signal = SignalIntent.model_validate({**unsigned_signal, "provenance_mac": mac})
        self._publish(RESEARCH_SIGNAL_INTENT_TOPIC, dump_json(signal), SHADOW_AGENT_ID)
        self._signals.append(signal)
        unsigned_order: dict[str, object] = {
            "schema_version": "research.order.intent.v1",
            "strategy_id": strategy_id,
            "direction": direction,
            "size": size,
            "timestamp": stamp,
            "expected_horizon": expected_horizon,
            "instrument": instrument,
            "account_id": account_id,
            "mode": mapped,
            "client_order_id": client_id,
            "order_type": "LIMIT",
            "limit_price": limit_price,
        }
        order_mac = self._authority.mac(canonical_order(unsigned_order))
        order = ResearchOrderIntent.model_validate({**unsigned_order, "provenance_mac": order_mac})
        self._publish(RESEARCH_ORDER_INTENT_TOPIC, dump_json(order), SHADOW_AGENT_ID)
        self._orders.append(order)
        fill = self._hypothetical_fill(
            strategy_id=strategy_id,
            instrument=instrument,
            qty=size,
            limit_price=limit_price,
            timestamp=stamp,
            client_order_id=client_id,
            volume=volume,
            average_volume=average_volume,
            volatility_price=volatility_price,
        )
        ingested = self._sink.ingest(fill)
        self._publish(RESEARCH_FILL_OBSERVED_TOPIC, dump_json(ingested), SHADOW_AGENT_ID)
        log_experiment(
            path=self._log_path,
            agent_id=SHADOW_AGENT_ID,
            event="shadow_signal",
            hypothesis_id=strategy_id,
            rationale=None,
            metrics={
                "client_order_id": client_id,
                "mode": "shadow",
                "fill_id": ingested.fill_id,
                "orders": False,
            },
            reject_reason=None,
            failed_checks=(),
        )
        return signal, ingested, failure

    def _hypothetical_fill(
        self,
        *,
        strategy_id: str,
        instrument: str,
        qty: float,
        limit_price: float,
        timestamp: str,
        client_order_id: str,
        volume: float,
        average_volume: float,
        volatility_price: float,
    ) -> ResearchFillEvent:
        spec = spec_for(instrument)
        market = MarketSnapshot(volume=volume, average_volume=average_volume, volatility_price=volatility_price)
        breakdown = self._model.ticks_for_fill(spec=spec, quantity=qty, market=market)
        unsigned: dict[str, object] = {
            "schema_version": "research.fill.observed.v1",
            "strategy_id": strategy_id,
            "fill_price": float(limit_price),
            "qty": float(qty),
            "slippage": float(breakdown.slippage_ticks),
            "commission": float(breakdown.commission_ticks),
            "timestamp": timestamp,
            "fill_id": f"fill-{client_order_id}",
            "instrument": spec.root,
            "client_order_id": client_order_id,
            "source": "cost_model",
        }
        mac = self._authority.mac(canonical_fill(unsigned))
        return ResearchFillEvent.model_validate({**unsigned, "provenance_mac": mac})

    def _emit_alert(self, failure: FailClosedDecision, *, open_position: bool) -> ExecutionAlert:
        self._seq[0] += 1
        unsigned: dict[str, object] = {
            "schema_version": "research.execution.alert.v1",
            "alert_id": f"alert-{self._seq[0]}",
            "kind": failure.kind,
            "action": failure.action,
            "allow_new_orders": failure.allow_new_orders,
            "flatten_recommended": failure.flatten_recommended,
            "open_position": open_position,
            "reason": failure.reason,
        }
        mac = self._authority.mac(canonical_alert(unsigned))
        alert = ExecutionAlert.model_validate({**unsigned, "provenance_mac": mac})
        self._publish(RESEARCH_EXECUTION_ALERT_TOPIC, dump_json(alert), SAFETY_AGENT_ID)
        self._alerts.append(alert)
        return alert

    def _publish(self, topic: str, payload: dict[str, object], producer: str) -> None:
        self._bus.publish(topic=topic, producer=producer, payload=dict(payload))
        if self._blackboard is not None:
            self._blackboard.publish_sync(topic=topic, producer=producer, payload=dict(payload), confidence=1.0)

    def _guard_signal(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check_signal(producer, payload, consume=True)

    def _guard_signal_bb(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check_signal(producer, payload, consume=False)

    def _guard_order(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check_order(producer, payload, consume=True)

    def _guard_order_bb(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check_order(producer, payload, consume=False)

    def _guard_fill(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check_fill(producer, payload, consume=True)

    def _guard_fill_bb(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check_fill(producer, payload, consume=False)

    def _guard_alert(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check_alert(producer, payload, consume=True)

    def _guard_alert_bb(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check_alert(producer, payload, consume=False)

    def _check_signal(self, producer: str, payload: dict[str, object], *, consume: bool) -> bool:
        if producer.strip() != SHADOW_AGENT_ID:
            return False
        try:
            parsed = SignalIntent.model_validate(payload)
        except Exception:
            return False
        if parsed.mode != "shadow":
            return False
        return accept_mac(
            self._authority,
            canonical_signal(payload),
            payload.get("provenance_mac"),
            self._seen if consume else None,
        )

    def _check_order(self, producer: str, payload: dict[str, object], *, consume: bool) -> bool:
        if producer.strip() != SHADOW_AGENT_ID:
            return False
        try:
            parsed = ResearchOrderIntent.model_validate(payload)
        except Exception:
            return False
        if parsed.mode != "shadow":
            return False
        return accept_mac(
            self._authority,
            canonical_order(payload),
            payload.get("provenance_mac"),
            self._seen if consume else None,
        )

    def _check_fill(self, producer: str, payload: dict[str, object], *, consume: bool) -> bool:
        if producer.strip() not in {SHADOW_AGENT_ID, FILL_AGENT_ID}:
            return False
        try:
            parsed = ResearchFillEvent.model_validate(payload)
        except Exception:
            return False
        if parsed.source != "cost_model":
            return False
        return accept_mac(
            self._authority,
            canonical_fill(payload),
            payload.get("provenance_mac"),
            self._seen if consume else None,
        )

    def _check_alert(self, producer: str, payload: dict[str, object], *, consume: bool) -> bool:
        if producer.strip() != SAFETY_AGENT_ID:
            return False
        try:
            ExecutionAlert.model_validate(payload)
        except Exception:
            return False
        return accept_mac(
            self._authority,
            canonical_alert(payload),
            payload.get("provenance_mac"),
            self._seen if consume else None,
        )


_MODES: dict[str, ExecutionMode] = {"shadow": "shadow", "sim": "sim", "live": "live"}


def _mode(value: str) -> ExecutionMode:
    mapped = _MODES.get(value.strip().lower())
    if mapped is None:
        raise PortRefused(f"unknown mode {value!r}")
    return mapped
