"""D7/D9/D10 executor in the Risk Core context. Research only proposes.

Deweight/suspend → 50% of that strategy (reduce_only). Disable/retired/critical
→ flatten 100% of that strategy. First SLA miss retries once; second miss or
>10 min escalates. No infinite silent retry. Broker SSOT after.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas_research_continuity import (
    RESEARCH_DEWEIGHT_TOPIC,
    RESEARCH_GUARDIAN_TOPIC,
    RESEARCH_RETIRE_TOPIC,
    RESEARCH_SUSPEND_TOPIC,
)
from lumina_core.broker.broker_bridge.schemas import Order, OrderResult
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.logging_utils import get_logger
from lumina_core.order_gatekeeper.ungated_place_block import gate_order
from lumina_core.research_bridge.alerts import AlertSink, LoggingAlertSink
from lumina_core.research_bridge.binding_policy import (
    D7_CRITICAL_SLA_SECONDS,
    D7_DEFAULT_SLA_SECONDS,
    SLA_ESCALATE_AFTER_SECONDS,
    BindingPolicyRefused,
    reduce_qty,
    sla_decision,
)
from lumina_core.research_bridge.jsonl import append_shadow_record
from lumina_core.research_bridge.sim_gate import S3_INSTRUMENTS
from lumina_core.risk.prolonged_disconnect import should_flatten_unprotected

logger = get_logger("lumina.risk.alarm_executor")

ALARM_EXECUTOR_ID = "alarm_executor"
_REDUCE_TOPICS = frozenset({RESEARCH_DEWEIGHT_TOPIC, RESEARCH_SUSPEND_TOPIC})
_FLATTEN_TOPICS = frozenset({RESEARCH_RETIRE_TOPIC})


class AlarmSubmitter(Protocol):
    def submit_order(self, order: Order) -> OrderResult: ...


@dataclass
class AlarmJob:
    strategy_id: str
    stage: str
    instrument: str
    proposed_at: datetime
    miss_count: int = 0
    retried: bool = False
    executed: bool = False
    closed: bool = False
    last_reason: str = ""


@dataclass
class AlarmExecutor:
    """Executes research proposals through AdmissionChain. Never imported by research."""

    bus: EventBus
    positions: LivePositionManager
    submitter: AlarmSubmitter
    jsonl_path: Path
    clock: Callable[[], datetime] = field(default_factory=lambda: (lambda: datetime.now(timezone.utc)))
    jobs: list[AlarmJob] = field(default_factory=list)
    reconciles: int = 0
    prolonged_flattens: int = 0
    alert_sink: AlertSink | None = None

    def install(self) -> None:
        self.bus.subscribe(RESEARCH_DEWEIGHT_TOPIC, self._on_deweight)
        self.bus.subscribe(RESEARCH_SUSPEND_TOPIC, self._on_suspend)
        self.bus.subscribe(RESEARCH_RETIRE_TOPIC, self._on_retire)
        self.bus.subscribe(RESEARCH_GUARDIAN_TOPIC, self._on_guardian)

    def tick(self, now: datetime | None = None) -> None:
        clock = now if now is not None else self.clock()
        for job in list(self.jobs):
            if job.executed is True or job.closed is True:
                continue
            self._advance(job, clock)

    def reconcile_on_reconnect(self) -> None:
        self.positions.sync_from_broker()
        self.reconciles += 1
        append_shadow_record(
            self.jsonl_path,
            {"event": "alarm_executor.reconcile", "actor": ALARM_EXECUTOR_ID, "count": self.reconciles},
        )

    def flatten_on_prolonged_disconnect(self, *, instrument: str = "MES") -> None:
        """Flatten open qty after a prolonged disconnect. Broker is SoT after reconcile.

        Research team decision (relayed by Steve 2026-10-29). Follow-up 23:09
        sha cc904288 Accepted the policy. Callers that already know the
        disconnect was prolonged use this action. Threshold gating lives on
        maybe_flatten_after_disconnect (Risk Core proposal).
        """
        self.reconcile_on_reconnect()
        for strategy_id, qty in self._open_strategy_book().items():
            self._flatten_one_prolonged(strategy_id=str(strategy_id), qty=int(qty), instrument=instrument)

    def maybe_flatten_after_disconnect(
        self,
        *,
        instrument: str = "MES",
        disconnected_ms: int,
        confirmed_server_stop_by_strategy: Mapping[str, bool] | None = None,
    ) -> int:
        """PROPOSAL — ADR-0064 item 8 Accepted (research team 23:09 sha cc904288).

        Risk Core apply needs signed human review. Live stays closed.
        Flatten only strategies with no confirmed server-side stop after the
        pre-registered 30000 ms disconnect. Unknown stop status fail-closes.
        """
        stops: Mapping[str, bool] = (
            confirmed_server_stop_by_strategy if isinstance(confirmed_server_stop_by_strategy, Mapping) else {}
        )
        self.reconcile_on_reconnect()
        before = int(self.prolonged_flattens)
        for strategy_id, qty in self._open_strategy_book().items():
            key = str(strategy_id)
            has_stop = stops.get(key)
            if should_flatten_unprotected(
                disconnected_ms=disconnected_ms,
                has_confirmed_server_stop=has_stop if isinstance(has_stop, bool) else None,
            ) is not True:
                continue
            self._flatten_one_prolonged(strategy_id=key, qty=int(qty), instrument=instrument)
        return int(self.prolonged_flattens) - before

    def _open_strategy_book(self) -> dict[str, int]:
        open_book = self.positions.open_strategy_qtys()
        if open_book:
            return {str(key): int(qty) for key, qty in open_book.items()}
        live_qty = int(self.positions.get_live_qty())
        if live_qty == 0:
            return {}
        return {"broker_sot": live_qty}

    def _flatten_one_prolonged(self, *, strategy_id: str, qty: int, instrument: str) -> None:
        if int(qty) == 0:
            return
        sink = self.alert_sink if self.alert_sink is not None else LoggingAlertSink()
        key = str(strategy_id)
        if int(self.positions.strategy_qty(key)) == 0:
            self.positions.set_strategy_qty(key, int(qty))
        root = str(instrument or "MES").strip().upper()
        if root not in S3_INSTRUMENTS:
            root = "MES"
        job = AlarmJob(
            strategy_id=key,
            stage="prolonged_disconnect",
            instrument=root,
            proposed_at=self.clock(),
        )
        self.jobs.append(job)
        self._execute(job, now=job.proposed_at, escalate=True)
        if job.executed is True:
            self.prolonged_flattens += 1
        sink.alert(
            code="prolonged_disconnect_flatten",
            message="prolonged disconnect: flatten via Risk Core; broker is SoT",
            details={"strategy_id": key, "qty": int(qty), "instrument": root},
        )

    def flatten_unconfirmed_protective_stop(
        self, *, instrument: str, strategy_id: str, qty: int
    ) -> None:
        """Accepted (ADR-0064 item 9 / 22:08). Companion STOP unconfirmed → flatten.

        Research team decision (relayed by Steve 2026-10-29): companion STOP
        (option C) that is not confirmed within the hard timeout → Risk Core
        flatten. Residual: MARKET may already be filled (fill-before-ATM race).
        """
        sink = self.alert_sink if self.alert_sink is not None else LoggingAlertSink()
        key = str(strategy_id or "").strip() or "broker_sot"
        size = int(qty)
        if size < 1:
            size = int(self.positions.strategy_qty(key)) or int(self.positions.get_live_qty())
        if size < 1:
            return
        if int(self.positions.strategy_qty(key)) == 0:
            self.positions.set_strategy_qty(key, size)
        root = str(instrument or "MES").strip().upper()
        if root not in S3_INSTRUMENTS:
            root = "MES"
        job = AlarmJob(
            strategy_id=key,
            stage="unconfirmed_protective_stop",
            instrument=root,
            proposed_at=self.clock(),
        )
        self.jobs.append(job)
        self._execute(job, now=job.proposed_at, escalate=True)
        sink.alert(
            code="unconfirmed_protective_stop_flatten",
            message="unconfirmed companion STOP: flatten via Risk Core",
            details={"strategy_id": key, "qty": size, "instrument": root},
        )

    def _on_deweight(self, event: DomainEvent) -> None:
        self._propose(event, stage="deweighted")

    def _on_suspend(self, event: DomainEvent) -> None:
        self._propose(event, stage="suspended")

    def _on_retire(self, event: DomainEvent) -> None:
        self._propose(event, stage="retired")

    def _on_guardian(self, event: DomainEvent) -> None:
        payload = dict(event.payload)
        severity = str(payload.get("severity") or "").strip().lower()
        if severity == "critical" or payload.get("suspend_proposed") is True:
            stage = "critical" if severity == "critical" else "suspended"
            self._propose(event, stage=stage)

    def _propose(self, event: DomainEvent, *, stage: str) -> None:
        payload = dict(event.payload)
        strategy_id = str(payload.get("hypothesis_id") or payload.get("signal_id") or "").strip()
        instrument = str(payload.get("instrument") or "MES").strip().upper()
        if not strategy_id:
            self._log("alarm_executor.proposal_refused", {"reason": "strategy_id_missing", "stage": stage})
            sink = self.alert_sink if self.alert_sink is not None else LoggingAlertSink()
            sink.alert(
                code="alarm_executor.proposal_refused",
                message="alarm proposal refused: strategy_id_missing",
                details={"reason": "strategy_id_missing", "stage": stage},
            )
            return
        job = AlarmJob(
            strategy_id=strategy_id,
            stage=stage,
            instrument=instrument if instrument in S3_INSTRUMENTS else "MES",
            proposed_at=self.clock(),
        )
        self.jobs.append(job)
        self._log(
            "alarm_executor.proposal",
            {"strategy_id": strategy_id, "stage": stage, "source": "research_proposal"},
        )
        self._advance(job, job.proposed_at)

    def _advance(self, job: AlarmJob, now: datetime) -> None:
        elapsed = (now - job.proposed_at).total_seconds()
        sla = D7_CRITICAL_SLA_SECONDS if job.stage in {"critical", "retired", "disabled", "hard_limit"} else D7_DEFAULT_SLA_SECONDS
        if elapsed <= float(sla) and job.miss_count == 0:
            self._execute(job, now=now, escalate=False)
            return
        if job.executed is True or job.closed is True:
            return
        job.miss_count += 1
        self._log(
            "alarm_executor.sla_miss",
            {
                "strategy_id": job.strategy_id,
                "miss_count": job.miss_count,
                "elapsed_seconds": elapsed,
            },
        )
        try:
            decision = sla_decision(job.miss_count, elapsed)
        except BindingPolicyRefused:
            decision = "escalate"
        if decision == "retry" and job.retried is not True:
            job.retried = True
            self._execute(job, now=now, escalate=False)
            return
        if elapsed > float(SLA_ESCALATE_AFTER_SECONDS) or decision == "escalate":
            self._execute(job, now=now, escalate=True)
            job.closed = True

    def _execute(self, job: AlarmJob, *, now: datetime, escalate: bool) -> None:
        del now, escalate
        open_qty = int(self.positions.strategy_qty(job.strategy_id))
        if open_qty < 1:
            job.executed = True
            job.last_reason = "already_flat"
            self._log("alarm_executor.skip_flat", {"strategy_id": job.strategy_id})
            return
        try:
            qty = reduce_qty(job.stage, open_qty)
        except BindingPolicyRefused as exc:
            job.last_reason = str(exc)
            self._log("alarm_executor.reduce_refused", {"strategy_id": job.strategy_id, "error": str(exc)})
            return
        side = "SELL" if open_qty > 0 else "BUY"
        flatten = qty >= abs(open_qty)
        order = Order(
            symbol=job.instrument,
            side=side,
            quantity=int(qty),
            order_type="MARKET",
            metadata={
                "reduce_only": True,
                "reason": "alarm_executor",
                "strategy_id": job.strategy_id,
                "mode_context": "sim_real_guard",
                "correlation_id": f"{job.strategy_id}:alarm",
                "protected": False,
            },
        )
        allowed, gate_reason = gate_order(
            "alarm_executor.execute",
            order,
            live_position_qty=open_qty,
        )
        if allowed is not True:
            job.last_reason = str(gate_reason)
            self._log(
                "alarm_executor.gated",
                {"strategy_id": job.strategy_id, "reason": str(gate_reason)},
            )
            sink = self.alert_sink if self.alert_sink is not None else LoggingAlertSink()
            sink.alert(
                code="alarm_executor.gated",
                message=f"alarm execute gated: {gate_reason}",
                details={"strategy_id": job.strategy_id, "reason": str(gate_reason)},
            )
            return
        result = self.submitter.submit_order(order)
        if result.accepted is True:
            remaining = abs(open_qty) - int(qty)
            self.positions.set_strategy_qty(job.strategy_id, remaining if remaining > 0 else 0)
            job.executed = True
            job.last_reason = "flatten" if flatten else "reduce_50"
            self._log(
                "alarm_executor.executed",
                {
                    "strategy_id": job.strategy_id,
                    "qty": int(qty),
                    "flatten": flatten,
                    "actor": ALARM_EXECUTOR_ID,
                },
            )
            return
        job.last_reason = str(result.message or "submit_rejected")

    def _log(self, event: str, payload: dict[str, object]) -> None:
        body = {"event": event, "actor": ALARM_EXECUTOR_ID, **payload}
        append_shadow_record(self.jsonl_path, body)
        logger.info(event, extra={"event_data": body})
