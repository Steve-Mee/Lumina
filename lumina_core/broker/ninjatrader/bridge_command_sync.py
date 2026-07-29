"""Synchronous outbound command path for NinjaTraderBridgeService.

Extracted from ``bridge_service`` (Wave B2 PR-C3). Behavior-preserving split.
Order payload construction and Fabric routing semantics are unchanged.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lumina_core.broker.broker_bridge.schemas import Order
from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability
from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction

if TYPE_CHECKING:
    from lumina_core.broker.ninjatrader.fabric_client import FabricGrpcClient


@dataclass
class _CommandWaiter:
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None


class BridgeCommandSyncMixin:
    """Enqueue outbound commands and wait for ack/error (broker-only entry)."""

    def send_command_sync(self, frame: dict[str, Any], *, timeout_seconds: float | None = None) -> dict[str, Any]:
        """Enqueue an outbound command and wait for ack/error (broker-only entry).

        Prefer Execution Fabric gRPC when attached; fall back to legacy WS send_fn.
        """
        correlation_id = str(frame.get("correlation_id", "") or uuid.uuid4())
        frame["correlation_id"] = correlation_id
        frame_type = str(frame.get("type", ""))

        with self._lock:
            connection = self.get_connection_state()
            action = (
                NtBridgeAction.SUBMIT_ORDER
                if frame_type == "submit_order"
                else NtBridgeAction.CANCEL
            )
            allowed, reason = assert_nt_bridge_capability(
                action=action,
                trade_mode=self.trade_mode,
                connection=connection,
                configured_account=self.configured_account,
                ninjatrader_enabled=self.ninjatrader_enabled,
            )
            if not allowed:
                return {
                    "type": "error",
                    "code": "CONSTITUTION_BLOCKED" if "account" in reason or "mismatch" in reason else "BRIDGE_GUARD",
                    "message": reason,
                    "correlation_id": correlation_id,
                }
            fabric = self._fabric
            send_fn = self._send_fn

        if fabric is not None:
            return self._send_via_fabric(frame, fabric=fabric, timeout_seconds=timeout_seconds)

        if send_fn is None:
            return {
                "type": "error",
                "code": "DISCONNECTED",
                "message": "No active Fabric client or NT8 WebSocket session",
                "correlation_id": correlation_id,
            }

        with self._lock:
            waiter = _CommandWaiter()
            self._pending_commands[correlation_id] = waiter

        try:
            send_fn(frame)
        except Exception as exc:
            with self._lock:
                self._pending_commands.pop(correlation_id, None)
            return {
                "type": "error",
                "code": "SEND_FAILED",
                "message": str(exc),
                "correlation_id": correlation_id,
            }

        timeout = float(timeout_seconds if timeout_seconds is not None else self.command_timeout_seconds)
        if not waiter.event.wait(timeout=timeout):
            with self._lock:
                self._pending_commands.pop(correlation_id, None)
            return {
                "type": "error",
                "code": "TIMEOUT",
                "message": f"Command timed out after {timeout}s",
                "correlation_id": correlation_id,
            }
        return waiter.result or {
            "type": "error",
            "code": "EMPTY_RESPONSE",
            "message": "No response from NT8",
            "correlation_id": correlation_id,
        }

    def _send_via_fabric(
        self,
        frame: dict[str, Any],
        *,
        fabric: FabricGrpcClient,
        timeout_seconds: float | None,
    ) -> dict[str, Any]:
        frame_type = str(frame.get("type", ""))
        corr = str(frame.get("correlation_id", "") or uuid.uuid4())
        timeout = float(timeout_seconds if timeout_seconds is not None else self.command_timeout_seconds)

        if frame_type == "submit_order":
            order = Order(
                symbol=str(frame.get("symbol", "")),
                side=str(frame.get("side", "BUY")),
                quantity=int(frame.get("quantity", 1) or 1),
                order_type=str(frame.get("order_type", "MARKET") or "MARKET"),
                stop_loss=float(frame.get("stop_loss") or 0.0),
                take_profit=float(frame.get("take_profit") or 0.0),
                metadata={
                    "price": frame.get("price"),
                    "stop_price": frame.get("stop_price"),
                    "reduce_only": frame.get("reduce_only"),
                    "protected": frame.get("protected"),
                },
            )
            client_order_id = str(frame.get("client_order_id") or f"lumina-{uuid.uuid4()}")
            t0 = time.perf_counter()
            result = fabric.place_order_sync(
                order,
                client_order_id=client_order_id,
                correlation_id=corr,
                timeout_seconds=timeout,
            )
            rtt_ms = (time.perf_counter() - t0) * 1000.0
            self.metrics.record_place(ok=str(result.get("type")) != "error", rtt_ms=rtt_ms)
            return result

        if frame_type in {"flatten", "cancel_all", "cancel_order"}:
            if frame_type == "cancel_order":
                self.metrics.record_cancel()
                return fabric.cancel_order_sync(
                    client_order_id=str(frame.get("client_order_id", "")),
                    nt_order_id=str(frame.get("order_id", frame.get("nt_order_id", ""))),
                    correlation_id=corr,
                    timeout_seconds=timeout,
                )
            self.metrics.record_flatten()
            return fabric.flatten_sync(
                instrument=str(frame.get("symbol", frame.get("instrument", ""))),
                correlation_id=corr,
                emergency=bool(frame.get("emergency", False)),
                timeout_seconds=timeout,
            )

        if frame_type == "modify_order":
            return fabric.modify_order_sync(
                client_order_id=str(frame.get("client_order_id", "")),
                nt_order_id=str(frame.get("order_id", frame.get("nt_order_id", ""))),
                quantity=int(frame.get("quantity") or 0),
                price=float(frame.get("price") or 0.0),
                stop_price=float(frame.get("stop_price") or 0.0),
                correlation_id=corr,
                timeout_seconds=timeout,
            )

        return {
            "type": "error",
            "code": "UNSUPPORTED",
            "message": f"Unsupported Fabric command type: {frame_type}",
            "correlation_id": corr,
        }


__all__ = ["BridgeCommandSyncMixin", "_CommandWaiter"]
