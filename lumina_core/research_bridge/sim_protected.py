"""ATM then companion STOP place helpers for SimRuntime (ADR-0064).

Research team decision (relayed by Steve 2026-10-29): option A default,
option C fallback, fail-closed flatten when neither confirms.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lumina_core.broker.broker_bridge.schemas import Order, OrderResult
from lumina_core.order_gatekeeper.ungated_place_block import gate_order
from lumina_core.research_bridge.protective_attach import (
    ATM_UNCONFIRMED,
    ATM_UNAVAILABLE,
    ATTACH_ATM,
    COMPANION_UNCONFIRMED,
    PATH_ATM,
    PATH_COMPANION,
    atm_confirmed,
    companion_confirmed,
    emergency_flatten_order,
    from_engine as attach_config_from_engine,
)
from lumina_core.research_bridge.protective_stop import companion_stop_order
from lumina_core.research_bridge.sim_gate import RESEARCH_BRIDGE_SOURCE


class SimProtectedMixin:
    _submitter: Any
    _orders: list[Order]
    _broker_submits: int
    _results: list[OrderResult]
    _protective: Any
    _engine: Any
    _clock: Callable[[], Any]
    _alarm_executor: Any
    _alerts: Any

    def _refuse(self, reason: str, extra: dict[str, object]) -> None:
        raise RuntimeError("SimRuntime.host_refuse")

    def _place_protected(
        self,
        order: Order,
        client_order_id: str,
        plan: object,
        strategy_id: str,
    ) -> OrderResult | None:
        path = str(getattr(plan, "path", PATH_COMPANION))
        timeout_ms = int(getattr(plan, "companion_confirm_timeout_ms", 5000))
        if path == PATH_ATM:
            result = self._submit_entry(order)
            if result is not None and atm_confirmed(result):
                raw = result.raw if isinstance(result.raw, dict) else {}
                raw["protective_attach"] = ATTACH_ATM
                result.raw = raw
                return result
            live = bool(result is not None and result.accepted is True)
            fallback_cfg = self._protective if self._protective is not None else attach_config_from_engine(self._engine)
            allow_c = fallback_cfg.fallback_companion is True
            if live is True:
                if allow_c is True and self._submit_companion_stop(order, client_order_id, timeout_ms) is True:
                    return result
                self._flatten_unconfirmed(
                    order,
                    strategy_id,
                    COMPANION_UNCONFIRMED if allow_c is True else ATM_UNCONFIRMED,
                )
                return None
            # ATM rejected: do not submit a second MARKET. A silent NT fill
            # plus a retry would double the position. Fail-closed.
            self._refuse(ATM_UNAVAILABLE, {"reason": str(result.message if result else ATM_UNAVAILABLE)})
            return result
        result = self._submit_entry(order)
        if result is None or result.accepted is not True:
            return result
        if self._submit_companion_stop(order, client_order_id, timeout_ms) is not True:
            self._flatten_unconfirmed(order, strategy_id, COMPANION_UNCONFIRMED)
            return None
        return result

    def _submit_entry(self, order: Order) -> OrderResult | None:
        if self._submitter is None:
            self._refuse("companion_stop_rejected", {"reason": "submitter_missing"})
            return None
        allowed, gate_reason = gate_order(
            "ninjatrader.broker.submit_order",
            order,
            engine=self._engine,
            source_agent=RESEARCH_BRIDGE_SOURCE,
        )
        if allowed is not True:
            self._refuse("ungated_place:" + str(gate_reason), {"reason": gate_reason})
            return None
        result = self._submitter.submit_order(order)
        self._orders.append(order)
        self._broker_submits += 1
        self._results.append(result)
        return result

    def _submit_companion_stop(self, order: Order, client_order_id: str, timeout_ms: int = 5000) -> bool:
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
        started = self._clock()
        meta = dict(companion.metadata) if isinstance(companion.metadata, dict) else {}
        meta.pop("atm_strategy_template", None)
        companion.metadata = meta
        companion_result = self._submitter.submit_order(companion) if self._submitter is not None else None
        if companion_result is None:
            self._refuse("companion_stop_rejected", {"reason": "submitter_missing"})
            return False
        self._orders.append(companion)
        self._broker_submits += 1
        self._results.append(companion_result)
        if companion_confirmed(companion_result, started=started, now=self._clock(), timeout_ms=timeout_ms) is not True:
            self._refuse(
                COMPANION_UNCONFIRMED,
                {"reason": str(companion_result.message or "submit_rejected"), "residual": True},
            )
            return False
        return True

    def _flatten_unconfirmed(self, order: Order, strategy_id: str, reason: str) -> None:
        self._refuse(reason, {"residual": True, "strategy_id": strategy_id})
        if self._alarm_executor is not None:
            self._alarm_executor.flatten_unconfirmed_protective_stop(
                instrument=str(order.symbol),
                strategy_id=str(strategy_id),
                qty=int(order.quantity),
            )
            return
        flatten = emergency_flatten_order(
            instrument=str(order.symbol),
            entry_side=str(order.side),
            quantity=int(order.quantity),
            strategy_id=str(strategy_id),
        )
        if self._submitter is None:
            return
        allowed, gate_reason = gate_order(
            "alarm_executor.execute",
            flatten,
            live_position_qty=int(order.quantity),
        )
        if allowed is not True:
            self._alerts.alert(
                code="unconfirmed_protective_stop_gated",
                message=str(gate_reason),
                details={"strategy_id": strategy_id},
            )
            return
        flat_result = self._submitter.submit_order(flatten)
        self._orders.append(flatten)
        self._broker_submits += 1
        self._results.append(flat_result)
