"""NinjaTrader broker implementation — BrokerBridge subclass."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from lumina_core.broker.broker_bridge.admission import run_final_arbitration
from lumina_core.broker.broker_bridge.base import BrokerBridge
from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Order, OrderResult, Position
from lumina_core.broker.ninjatrader.bridge_service import NinjaTraderBridgeService, get_ninjatrader_bridge_service
from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability
from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction, normalize_trade_mode


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(slots=True)
class NinjaTraderBroker(BrokerBridge):
    configured_account: str = "Sim101"
    ninjatrader_enabled: bool = True
    command_timeout_seconds: float = 10.0
    connect_timeout_seconds: float = 5.0
    logger: logging.Logger | None = None
    engine: Any | None = None
    bridge_service: NinjaTraderBridgeService | None = None
    _pending_lineage: dict[str, dict[str, str | None]] = field(default_factory=dict, init=False, repr=False)

    def _resolve_bridge(self) -> NinjaTraderBridgeService:
        if self.bridge_service is not None:
            return self.bridge_service
        trade_mode = normalize_trade_mode(
            str(getattr(getattr(self.engine, "config", None), "trade_mode", "sim") or "sim")
        )
        self.bridge_service = get_ninjatrader_bridge_service(
            configured_account=self.configured_account,
            trade_mode=trade_mode,
            ninjatrader_enabled=self.ninjatrader_enabled,
            command_timeout_seconds=self.command_timeout_seconds,
        )
        return self.bridge_service

    def _resolve_trade_mode(self) -> str:
        return normalize_trade_mode(
            str(getattr(getattr(self.engine, "config", None), "trade_mode", "sim") or "sim")
        )

    def connect(self) -> bool:
        bridge = self._resolve_bridge()
        bridge.set_trade_mode(self._resolve_trade_mode())
        bridge.set_configured_account(self.configured_account)
        state = bridge.get_connection_state()
        if state.is_connected:
            return True
        if self.logger is not None:
            self.logger.warning(
                "NinjaTrader bridge not connected (state=%s); connect returns False for live provider",
                state.state,
            )
        return False

    def disconnect(self) -> None:
        if self.bridge_service is not None:
            self.bridge_service.on_disconnect()

    def submit_order(self, order: Order) -> OrderResult:
        meta = getattr(order, "metadata", {}) or {}
        lineage: dict[str, str | None] = {}
        if isinstance(meta, dict):
            for key in ("decision_context_id", "prev_hash", "prev_event_topic"):
                if meta.get(key):
                    lineage[key] = str(meta[key])  # type: ignore[assignment]

        client_order_id = (
            str(meta.get("clientOrderId") or f"lumina-{uuid.uuid4()}") if isinstance(meta, dict) else f"lumina-{uuid.uuid4()}"
        )
        if lineage:
            self._pending_lineage[client_order_id] = lineage

        allowed, reason = run_final_arbitration(self.engine, order)
        if not allowed:
            res = OrderResult(
                accepted=False,
                order_id="",
                status="rejected",
                message=f"FinalArbitration blocked order: {reason}",
            )
            if lineage:
                for key, value in lineage.items():
                    setattr(res, key, value)
            return res

        bridge = self._resolve_bridge()
        bridge.set_trade_mode(self._resolve_trade_mode())
        connection = bridge.get_connection_state()
        guard_ok, guard_reason = assert_nt_bridge_capability(
            action=NtBridgeAction.SUBMIT_ORDER,
            trade_mode=self._resolve_trade_mode(),
            connection=connection,
            configured_account=self.configured_account,
            ninjatrader_enabled=self.ninjatrader_enabled,
        )
        if not guard_ok:
            res = OrderResult(
                accepted=False,
                order_id="",
                status="rejected",
                message=f"NT bridge guard blocked order: {guard_reason}",
            )
            if lineage:
                for key, value in lineage.items():
                    setattr(res, key, value)
            return res

        correlation_id = str(uuid.uuid4())
        frame = {
            "schema_version": "1.0",
            "type": "submit_order",
            "correlation_id": correlation_id,
            "ts": _utc_now_iso(),
            "client_order_id": client_order_id,
            "symbol": str(order.symbol),
            "side": str(order.side).upper(),
            "quantity": int(order.quantity),
            "order_type": str(order.order_type).upper(),
            "stop_loss": float(order.stop_loss or 0.0),
            "take_profit": float(order.take_profit or 0.0),
            "mode_context": self._resolve_trade_mode(),
        }

        response = bridge.send_command_sync(frame, timeout_seconds=self.command_timeout_seconds)
        response_type = str(response.get("type", ""))
        if response_type == "error":
            res = OrderResult(
                accepted=False,
                order_id="",
                status="rejected",
                message=str(response.get("message", "NT8 rejected order")),
                raw=response if isinstance(response, dict) else {"raw": response},
            )
        else:
            order_id = str(response.get("order_id", response.get("ref_correlation_id", "")))
            res = OrderResult(
                accepted=True,
                order_id=order_id,
                status="accepted",
                message=str(response.get("message", "")),
                raw=response if isinstance(response, dict) else {"raw": response},
            )
            if lineage and order_id:
                self._pending_lineage[order_id] = lineage

        if lineage:
            for key, value in lineage.items():
                setattr(res, key, value)
        return res

    def get_account_info(self) -> AccountInfo:
        return self._resolve_bridge().get_account_info()

    def get_positions(self) -> list[Position]:
        return self._resolve_bridge().get_positions()

    def get_fills(self) -> list[Fill]:
        return self._resolve_bridge().get_fills()

    def cancel_all_orders(self) -> dict[str, object]:
        bridge = self._resolve_bridge()
        connection = bridge.get_connection_state()
        guard_ok, guard_reason = assert_nt_bridge_capability(
            action=NtBridgeAction.CANCEL,
            trade_mode=self._resolve_trade_mode(),
            connection=connection,
            configured_account=self.configured_account,
            ninjatrader_enabled=self.ninjatrader_enabled,
        )
        if not guard_ok:
            return {"ok": False, "reason": guard_reason}

        correlation_id = str(uuid.uuid4())
        frame = {
            "schema_version": "1.0",
            "type": "flatten",
            "correlation_id": correlation_id,
            "ts": _utc_now_iso(),
        }
        response = bridge.send_command_sync(frame, timeout_seconds=self.command_timeout_seconds)
        ok = str(response.get("type", "")) != "error"
        return {"ok": ok, "response": response}

    def subscribe_to_websocket(self) -> None:
        return None
