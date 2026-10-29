"""S3 gated SIM orders: OrderIntent only after sim_gate, through existing admission.

Never re-arms supervisor_tick_exec. ES/NQ research orders refuse. LIVE_RELEASE
cannot enable REAL. Missing submitter → shadow (no Fabric).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas_research import (
    RESEARCH_PROMOTION_TOPIC,
    PromotionCandidate,
)
from lumina_core.agent_orchestration.schemas_research_execution import (
    RESEARCH_BRIDGE_AGENT_ID,
    RESEARCH_EXECUTION_FILL_TOPIC,
    RESEARCH_EXECUTION_ORDER_TOPIC,
    RESEARCH_EXECUTION_SIGNAL_TOPIC,
    ResearchExecutionOrderIntent,
    SignalIntent,
    guard_research_execution,
    guard_research_execution_fill,
)
from lumina_core.broker.broker_bridge.schemas import Order, OrderResult
from lumina_core.logging_utils import get_logger
from lumina_core.order_gatekeeper.gate import enforce_pre_trade_gate
from lumina_core.order_gatekeeper.ungated_place_block import gate_order
from lumina_core.research_bridge.alerts import AlertSink, LoggingAlertSink
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.protective_stop import (
    UNPROTECTED_ENTRY,
    companion_stop_order,
    default_stop_price,
    require_protective_stop,
)
from lumina_core.research_bridge.horizon import HorizonRefused, require_expected_horizon_bars
from lumina_core.research_bridge.jsonl import append_shadow_record
from lumina_core.research_bridge.market_health import MarketHealth
from lumina_core.research_bridge.sim_gate import (
    RESEARCH_BRIDGE_SOURCE,
    RESEARCH_SIM_GATED,
    SimGateContext,
    SimGateRefused,
    arm_research_place,
    bind_sim_gate,
    evaluate,
    evaluate_instrument,
)
from lumina_core.risk.schemas import OrderIntent
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.provenance import ProvenanceAuthority

logger = get_logger("lumina.research_bridge.sim")


class SimSubmitter(Protocol):
    def submit_order(self, order: Order) -> OrderResult: ...


class SimRuntime:
    """PromotionCandidate → OrderIntent → existing admission + broker submit."""

    def __init__(
        self,
        *,
        bus: EventBus,
        authority: ProvenanceAuthority,
        jsonl_path: Path,
        market: MarketHealth,
        fill_index: FillIndex,
        gate_ctx: SimGateContext,
        engine: object | None = None,
        submitter: SimSubmitter | None = None,
        alert_sink: AlertSink | None = None,
        clock: Callable[[], datetime] | None = None,
        pre_trade_gate: Callable[..., tuple[bool, str]] | None = None,
    ) -> None:
        self._bus = bus
        self._authority = authority
        self._jsonl_path = jsonl_path
        self._market = market
        self._fill_index = fill_index
        self._gate_ctx = gate_ctx
        self._engine = engine
        self._submitter = submitter
        self._alerts = alert_sink if alert_sink is not None else LoggingAlertSink()
        self._clock = clock if clock is not None else (lambda: datetime.now(timezone.utc))
        self._pre_trade = pre_trade_gate if pre_trade_gate is not None else enforce_pre_trade_gate
        self._intents: list[SignalIntent] = []
        self._orders: list[Order] = []
        self._results: list[OrderResult] = []
        self._broker_submits = 0
        bus.register_topic_guard(RESEARCH_EXECUTION_SIGNAL_TOPIC, guard_research_execution)
        bus.register_topic_guard(RESEARCH_EXECUTION_ORDER_TOPIC, guard_research_execution)
        bus.register_topic_guard(RESEARCH_EXECUTION_FILL_TOPIC, guard_research_execution_fill)
        bus.subscribe(RESEARCH_PROMOTION_TOPIC, self._on_bus_candidate)

    def issued_intents(self) -> tuple[SignalIntent, ...]:
        return tuple(self._intents)

    def submitted_orders(self) -> tuple[Order, ...]:
        return tuple(self._orders)

    def broker_submit_count(self) -> int:
        return int(self._broker_submits)

    def on_candidate(self, candidate: PromotionCandidate) -> OrderResult | None:
        dumped = dump_json(candidate)
        if not self._authority.verify_issue(dumped):
            self._refuse("unsigned_or_forged_candidate", {"hypothesis_id": candidate.hypothesis_id})
            return None
        try:
            horizon = require_expected_horizon_bars(candidate.expected_horizon_bars)
        except HorizonRefused as exc:
            self._refuse("expected_horizon_missing", {"error": str(exc)})
            return None
        allowed, health = self._market.allow_new_intents()
        if allowed is not True:
            self._refuse("shadow_fill_refused:" + health, {"health_reason": health})
            return None
        instrument = str(candidate.instrument).strip().upper()
        inst_ok, inst_reason = evaluate_instrument(instrument, self._gate_ctx)
        if inst_ok is not True:
            self._refuse(inst_reason, {"instrument": instrument})
            return None
        ok, reason = evaluate(self._gate_ctx)
        if ok is not True:
            self._refuse(reason, {"yaml_mode_now": self._gate_ctx.yaml_mode_now})
            return None
        if self._submitter is None or self._engine is None:
            self._refuse(RESEARCH_SIM_GATED, {"submitter": "missing"})
            return None
        intent = SignalIntent(
            strategy_id=candidate.hypothesis_id,
            config_id=candidate.config_id,
            trial_id=candidate.trial_id,
            instrument=candidate.instrument,  # type: ignore[arg-type]
            direction=candidate.direction,
            size=float(candidate.quantity),
            timestamp=self._clock(),
            expected_horizon=horizon,
            validation_mac=candidate.validation_mac,
            issue_mac=candidate.issue_mac,
            source=RESEARCH_BRIDGE_AGENT_ID,
        )
        self._intents.append(intent)
        logged = ResearchExecutionOrderIntent(
            strategy_id=intent.strategy_id,
            config_id=intent.config_id,
            trial_id=intent.trial_id,
            instrument=intent.instrument,
            direction=intent.direction,
            size=intent.size,
            timestamp=intent.timestamp,
            expected_horizon=intent.expected_horizon,
            validation_mac=intent.validation_mac,
            issue_mac=intent.issue_mac,
            source=RESEARCH_BRIDGE_AGENT_ID,
            admitted=False,
        )
        self._bus.publish(
            topic=RESEARCH_EXECUTION_ORDER_TOPIC,
            producer=RESEARCH_BRIDGE_AGENT_ID,
            payload=dump_json(logged),
        )
        qty = int(candidate.quantity)
        if qty < 1:
            self._refuse("quantity_invalid", {"quantity": candidate.quantity})
            return None
        live_intent = OrderIntent(
            instrument=instrument,
            side=str(candidate.direction).upper(),  # type: ignore[arg-type]
            quantity=qty,
            source_agent=RESEARCH_BRIDGE_SOURCE,
        )
        gate_ok, gate_reason = self._pre_trade(
            self._engine,
            symbol=live_intent.instrument,
            regime="NEUTRAL",
            proposed_risk=0.0,
            order_side=str(live_intent.side),
        )
        if gate_ok is not True:
            self._refuse("admission_blocked:" + str(gate_reason), {"reason": gate_reason})
            return None
        reference = self._market.reference_price()
        if reference is None:
            self._refuse(UNPROTECTED_ENTRY, {"reference": "missing"})
            return None
        try:
            stop_price = default_stop_price(side=str(live_intent.side), reference=float(reference))
        except ValueError as exc:
            self._refuse(str(exc), {"reference": float(reference)})
            return None
        client_order_id = f"s3-{uuid.uuid4()}"
        correlation = f"{candidate.hypothesis_id}:{client_order_id}"
        order = Order(
            symbol=live_intent.instrument,
            side=str(live_intent.side),
            quantity=int(live_intent.quantity),
            order_type="MARKET",
            stop_loss=stop_price,
            metadata={
                "clientOrderId": client_order_id,
                "correlation_id": correlation,
                "mode_context": "sim_real_guard",
                "source_agent": RESEARCH_BRIDGE_SOURCE,
                "strategy_id": candidate.hypothesis_id,
                "expected_horizon": horizon,
                "stop_price": stop_price,
                "protected": True,
            },
        )
        stop_ok, stop_reason = require_protective_stop(order)
        if stop_ok is not True:
            self._refuse(stop_reason, {"stop_price": stop_price})
            return None
        bind_sim_gate(self._gate_ctx)
        allowed_place, place_reason = gate_order(
            "ninjatrader.broker.submit_order",
            order,
            engine=self._engine,
            source_agent=RESEARCH_BRIDGE_SOURCE,
        )
        if allowed_place is not True:
            self._refuse("ungated_place:" + str(place_reason), {"reason": place_reason})
            return None
        try:
            with arm_research_place(self._gate_ctx):
                result = self._submitter.submit_order(order)
                self._orders.append(order)
                self._broker_submits += 1
                self._results.append(result)
                if result.accepted is True:
                    if self._submit_companion_stop(order, client_order_id) is not True:
                        return None
                    self._fill_index.remember(client_order_id, candidate.hypothesis_id, horizon)
        except SimGateRefused as exc:
            self._refuse(str(exc), {"armed": False})
            return None
        append_shadow_record(
            self._jsonl_path,
            {
                "event": "research_sim.order",
                "accepted": bool(result.accepted),
                "strategy_id": candidate.hypothesis_id,
                "instrument": instrument,
                "client_order_id": client_order_id,
            },
        )
        return result

    def _on_bus_candidate(self, event: DomainEvent) -> None:
        try:
            candidate = event.typed_payload(PromotionCandidate)
        except Exception:
            self._refuse("candidate_payload_invalid", {})
            return
        self.on_candidate(candidate)

    def _submit_companion_stop(self, order: Order, client_order_id: str) -> bool:
        companion_id = f"{client_order_id}-stop"
        try:
            companion = companion_stop_order(order, client_order_id=companion_id)
        except ValueError as exc:
            self._refuse(str(exc), {"companion": "missing_stop"})
            return False
        allowed_stop, stop_gate = gate_order(
            "ninjatrader.broker.submit_order",
            companion,
            engine=self._engine,
            source_agent=RESEARCH_BRIDGE_SOURCE,
        )
        if allowed_stop is not True:
            self._refuse("companion_stop_gated:" + str(stop_gate), {"reason": stop_gate})
            return False
        companion_result = self._submitter.submit_order(companion) if self._submitter is not None else None
        if companion_result is None:
            self._refuse("companion_stop_rejected", {"reason": "submitter_missing"})
            return False
        self._orders.append(companion)
        self._broker_submits += 1
        self._results.append(companion_result)
        if companion_result.accepted is not True:
            self._refuse(
                "companion_stop_rejected",
                {"reason": str(companion_result.message or "submit_rejected")},
            )
            return False
        return True

    def _refuse(self, reason: str, extra: dict[str, object]) -> None:
        payload = {"event": "research_sim.refused", "reason": reason, **extra}
        append_shadow_record(self._jsonl_path, payload)
        self._alerts.alert(code=str(reason), message=f"research_sim refused: {reason}", details=payload)
        logger.error("research_sim.refused", extra={"event_data": payload})
