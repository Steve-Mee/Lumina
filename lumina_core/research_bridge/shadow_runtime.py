"""KEEP ResearchBridge: PromotionCandidate → logged SignalIntent + ADR-0055 hypothetical fill.

Zero PlaceOrderCommand. Zero risk-increasing place_order. Fail-closed on stale
data or lost connection (no new SignalIntent).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

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
    ResearchExecutionFill,
    ResearchExecutionOrderIntent,
    SignalIntent,
    guard_research_execution,
    guard_research_execution_fill,
)
from lumina_core.engine.trade_reconciler.schemas import FillEvent
from lumina_core.logging_utils import get_logger
from lumina_core.research_bridge.alerts import AlertSink, LoggingAlertSink
from lumina_core.research_bridge.costs import hypothetical_execution_costs
from lumina_core.research_bridge.horizon import HorizonRefused, require_expected_horizon_bars
from lumina_core.research_bridge.jsonl import append_shadow_record
from lumina_core.research_bridge.market_health import (
    LOST_CONNECTION,
    STALE_OR_MISSING,
    MarketHealth,
)
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.provenance import ProvenanceAuthority

logger = get_logger("lumina.research_bridge.shadow")

TapeKind = Literal["synthetic", "nt_pit"]


class ObserveSink(Protocol):
    def observe(self, signal_id: str, metric: object) -> object: ...


class ShadowRuntime:
    """Subscriber of ``research.promotion.candidate``. Never imports the NT broker."""

    def __init__(
        self,
        *,
        bus: EventBus,
        authority: ProvenanceAuthority,
        jsonl_path: Path,
        market: MarketHealth,
        tape_kind: TapeKind,
        observe_sink: ObserveSink | None = None,
        alert_sink: AlertSink | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._bus = bus
        self._authority = authority
        self._jsonl_path = jsonl_path
        self._market = market
        self._tape_kind = tape_kind
        self._observe = observe_sink
        self._alerts = alert_sink if alert_sink is not None else LoggingAlertSink()
        self._clock = clock if clock is not None else (lambda: datetime.now(timezone.utc))
        self._intents: list[SignalIntent] = []
        self._fills: list[FillEvent] = []
        self._broker_submits = 0
        self._observe_calls = 0
        bus.register_topic_guard(RESEARCH_EXECUTION_SIGNAL_TOPIC, guard_research_execution)
        bus.register_topic_guard(RESEARCH_EXECUTION_ORDER_TOPIC, guard_research_execution)
        bus.register_topic_guard(RESEARCH_EXECUTION_FILL_TOPIC, guard_research_execution_fill)
        bus.subscribe(RESEARCH_PROMOTION_TOPIC, self._on_bus_candidate)

    def replace_market(self, market: MarketHealth) -> None:
        self._market = market

    def issued_intents(self) -> tuple[SignalIntent, ...]:
        return tuple(self._intents)

    def issued_fills(self) -> tuple[FillEvent, ...]:
        return tuple(self._fills)

    def observe_call_count(self) -> int:
        return self._observe_calls

    def assert_no_broker_submit(self) -> None:
        if self._broker_submits != 0:
            raise AssertionError("research_bridge recorded a broker submit")

    def on_candidate(self, candidate: PromotionCandidate) -> SignalIntent | None:
        dumped = dump_json(candidate)
        if not self._authority.verify_issue(dumped):
            self._refuse("unsigned_or_forged_candidate", {"hypothesis_id": candidate.hypothesis_id})
            return None
        try:
            horizon = require_expected_horizon_bars(candidate.expected_horizon_bars)
        except HorizonRefused as exc:
            self._refuse("expected_horizon_missing", {"hypothesis_id": candidate.hypothesis_id, "error": str(exc)})
            return None
        allowed, health_reason = self._market.allow_new_intents()
        if not allowed:
            code = "shadow_fill_refused:" + health_reason
            self._refuse(
                code,
                {
                    "hypothesis_id": candidate.hypothesis_id,
                    "health_reason": health_reason,
                    "fill": "refused",
                },
            )
            return None
        now = self._clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        intent = SignalIntent(
            strategy_id=str(candidate.hypothesis_id),
            config_id=str(candidate.config_id),
            trial_id=int(candidate.trial_id),
            instrument=candidate.instrument,
            direction=candidate.direction,
            size=float(candidate.quantity),
            timestamp=now,
            expected_horizon=horizon,
            validation_mac=str(candidate.validation_mac),
            issue_mac=str(candidate.issue_mac),
            source=RESEARCH_BRIDGE_AGENT_ID,
        )
        self._publish_signal(intent)
        self._publish_logged_order(intent)
        self._intents.append(intent)
        append_shadow_record(
            self._jsonl_path,
            {
                "event": "signal_intent",
                "strategy_id": intent.strategy_id,
                "direction": intent.direction,
                "size": intent.size,
                "timestamp": intent.timestamp.isoformat(),
                "expected_horizon": intent.expected_horizon,
                "instrument": intent.instrument,
                "tape_kind": self._tape_kind,
                "fill": "pending",
            },
        )
        fill = self.shadow_fill(intent)
        if fill is None:
            append_shadow_record(
                self._jsonl_path,
                {
                    "event": "shadow_fill_refused",
                    "strategy_id": intent.strategy_id,
                    "fill": "refused",
                    "tape_kind": self._tape_kind,
                },
            )
        return intent

    def shadow_fill(self, intent: SignalIntent) -> FillEvent | None:
        allowed, health_reason = self._market.allow_new_intents()
        reference = self._market.reference_price()
        if not allowed or reference is None:
            self._refuse(
                "shadow_fill_refused:" + health_reason,
                {"strategy_id": intent.strategy_id, "fill": "refused"},
            )
            return None
        try:
            costs = hypothetical_execution_costs(
                instrument=intent.instrument,
                direction=intent.direction,
                size=intent.size,
                reference_price=reference,
            )
        except ValueError as exc:
            self._refuse(
                "shadow_fill_refused:invalid_cost_inputs",
                {"strategy_id": intent.strategy_id, "fill": "refused", "error": str(exc)},
            )
            return None
        if costs.discrepancy:
            logger.warning(
                "cost_discrepancy",
                extra={
                    "event_data": {
                        "event": "cost_discrepancy",
                        "strategy_id": intent.strategy_id,
                        "execution_commission_usd": costs.commission_usd,
                        "execution_slippage_usd": costs.slippage_usd,
                        "research_total_usd": costs.research_total_usd,
                        "winner": "execution_side",
                    }
                },
            )
        now = intent.timestamp
        fill = FillEvent(
            fill_id=f"shadow-{uuid.uuid4().hex[:16]}",
            symbol=str(intent.instrument),
            side=str(intent.direction),
            quantity=int(intent.size) if int(intent.size) >= 1 else 1,
            price=float(costs.fill_price),
            commission=float(costs.commission_usd),
            event_ts=now if now.tzinfo else now.replace(tzinfo=timezone.utc),
            slippage_ticks=float(costs.slippage_ticks),
            slippage_usd=float(costs.slippage_usd),
            commission_ticks=float(costs.commission_ticks),
            source="hypothetical_adr0055",
        )
        self._fills.append(fill)
        self._publish_fill(intent, fill)
        append_shadow_record(
            self._jsonl_path,
            {
                "event": "hypothetical_fill",
                "strategy_id": intent.strategy_id,
                "fill_id": fill.fill_id,
                "fill_price": fill.fill_price,
                "qty": fill.qty,
                "commission_usd": fill.commission,
                "commission_ticks": fill.commission_ticks,
                "slippage_ticks": fill.slippage_ticks,
                "slippage_usd": fill.slippage_usd,
                "source": fill.source,
                "instrument": fill.symbol,
                "tape_kind": self._tape_kind,
                "research_total_usd": costs.research_total_usd,
                "cost_discrepancy": costs.discrepancy,
            },
        )
        if self._observe is not None:
            metric = float(-(fill.commission + fill.slippage_usd))
            self._observe.observe(intent.strategy_id, metric)
            self._observe_calls += 1
        self.assert_no_broker_submit()
        return fill

    def _on_bus_candidate(self, event: DomainEvent) -> None:
        try:
            candidate = event.typed_payload(PromotionCandidate)
            self.on_candidate(candidate)
        except Exception as exc:
            logger.error(
                "shadow_candidate_handler_failed",
                extra={
                    "event_data": {
                        "event": "shadow_candidate_handler_failed",
                        "error": str(exc),
                    }
                },
            )
            self._refuse("shadow_candidate_handler_failed", {"error": str(exc), "fill": "refused"})

    def _publish_signal(self, intent: SignalIntent) -> None:
        self._bus.publish(
            topic=RESEARCH_EXECUTION_SIGNAL_TOPIC,
            producer=RESEARCH_BRIDGE_AGENT_ID,
            payload=intent.model_dump(mode="json"),
        )

    def _publish_logged_order(self, intent: SignalIntent) -> None:
        order = ResearchExecutionOrderIntent(
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
            payload=order.model_dump(mode="json"),
        )

    def _publish_fill(self, intent: SignalIntent, fill: FillEvent) -> None:
        payload = ResearchExecutionFill(
            fill_id=fill.fill_id,
            symbol=fill.symbol,
            side="BUY" if str(fill.side).upper() == "BUY" else "SELL",
            quantity=int(fill.quantity),
            price=float(fill.price),
            commission=float(fill.commission),
            event_ts=fill.event_ts,
            slippage_ticks=float(fill.slippage_ticks),
            slippage_usd=float(fill.slippage_usd),
            commission_ticks=float(fill.commission_ticks),
            source="hypothetical_adr0055",
            strategy_id=intent.strategy_id,
            expected_horizon=intent.expected_horizon,
        )
        self._bus.publish(
            topic=RESEARCH_EXECUTION_FILL_TOPIC,
            producer=RESEARCH_BRIDGE_AGENT_ID,
            payload=payload.model_dump(mode="json"),
        )

    def _refuse(self, code: str, details: dict[str, object]) -> None:
        message = code
        if code.endswith(LOST_CONNECTION) or code == LOST_CONNECTION or LOST_CONNECTION in code:
            message = "lost connection: no new research signals or intents"
        elif STALE_OR_MISSING in code:
            message = "stale or missing market: no new research signals or intents"
        self._alerts.alert(code=code, message=message, details=details)
        append_shadow_record(
            self._jsonl_path,
            {"event": "refused", "code": code, "fill": details.get("fill", "refused"), **details},
        )
