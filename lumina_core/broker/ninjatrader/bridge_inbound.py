"""Inbound NT8 / Fabric frame handling for NinjaTraderBridgeService.

Extracted from ``bridge_service`` (Wave B2 PR-C3). Behavior-preserving split.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Position
from lumina_core.broker.ninjatrader.schemas import (
    AccountSnapshotFrame,
    ConnectionStatusFrame,
    ExecutionFrame,
    PositionUpdateFrame,
    parse_inbound_frame,
)

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class BridgeInboundMixin:
    """Inbound WS frames + Fabric stream event application."""

    def handle_inbound(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Process an inbound frame from NT8. Returns optional outbound response."""
        try:
            frame = parse_inbound_frame(payload)
        except Exception as exc:
            logger.warning("NT8 inbound frame rejected: %s", exc)
            return {
                "schema_version": "1.0",
                "type": "error",
                "correlation_id": str(payload.get("correlation_id", uuid.uuid4())),
                "ts": _utc_now_iso(),
                "code": "SCHEMA_VIOLATION",
                "message": str(exc),
            }

        frame_type = str(getattr(frame, "type", ""))

        if frame_type == "connection_status" and isinstance(frame, ConnectionStatusFrame):
            self._apply_connection_status(frame)
            return None

        if frame_type == "execution" and isinstance(frame, ExecutionFrame):
            self._record_execution(frame)
            return None

        if frame_type == "account_snapshot" and isinstance(frame, AccountSnapshotFrame):
            self._apply_account_snapshot(frame)
            return None

        if frame_type == "position_update" and isinstance(frame, PositionUpdateFrame):
            self._apply_position_update(frame)
            return None

        if frame_type in {"ack", "error"}:
            ref_id = str(getattr(frame, "ref_correlation_id", "") or getattr(frame, "correlation_id", ""))
            self._complete_command(ref_id, payload)
            return None

        if frame_type == "ping":
            return {
                "schema_version": "1.0",
                "type": "pong",
                "correlation_id": str(getattr(frame, "correlation_id", uuid.uuid4())),
                "ts": _utc_now_iso(),
            }

        return None

    def _apply_connection_status(self, frame: ConnectionStatusFrame) -> None:
        with self._lock:
            self._connection.state = frame.state if frame.state != "error" else "error"
            if frame.account_name:
                self._connection.account_name = frame.account_name
            if frame.connection_name:
                self._connection.connection_name = frame.connection_name
            if frame.ninjatrader_version:
                self._connection.ninjatrader_version = frame.ninjatrader_version

    def _record_execution(self, frame: ExecutionFrame) -> None:
        with self._lock:
            if frame.execution_id in self._fill_ids:
                return
            self._fill_ids.add(frame.execution_id)
            self._fills.append(
                Fill(
                    fill_id=frame.execution_id,
                    order_id=frame.order_id,
                    symbol=frame.symbol,
                    side=frame.side,
                    quantity=int(frame.quantity),
                    price=float(frame.price),
                    timestamp=frame.ts,
                    commission=float(frame.commission),
                    raw=frame.model_dump(),
                )
            )

    def _apply_account_snapshot(self, frame: AccountSnapshotFrame) -> None:
        with self._lock:
            self._account = AccountInfo(
                balance=float(frame.balance),
                equity=float(frame.equity),
                available_margin=frame.available_margin,
                realized_pnl_today=float(frame.realized_pnl_today),
                currency=str(frame.currency),
                raw=frame.model_dump(),
            )

    def _apply_position_update(self, frame: PositionUpdateFrame) -> None:
        with self._lock:
            symbol = str(frame.symbol).strip()
            self._positions = [p for p in self._positions if p.symbol != symbol]
            if int(frame.quantity) != 0:
                self._positions.append(
                    Position(
                        symbol=symbol,
                        quantity=abs(int(frame.quantity)),
                        avg_price=float(frame.avg_price),
                        side=str(frame.side).upper(),
                        raw=frame.model_dump(),
                    )
                )

    def _complete_command(self, correlation_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            waiter = self._pending_commands.pop(correlation_id, None)
            if waiter is None:
                return
            waiter.result = payload
            waiter.event.set()

    def _on_fabric_message(self, msg: Any) -> None:
        """Apply Fabric stream events to session fill/account state."""
        try:
            from lumina_core.broker.ninjatrader.fabric_client import apply_fabric_message_to_bridge_state
            from lumina_core.broker.ninjatrader.generated import fabric_pb2
        except ImportError:
            return

        def _record_fill(fill: Fill) -> None:
            with self._lock:
                if fill.fill_id in self._fill_ids:
                    return
                self._fill_ids.add(fill.fill_id)
                self._fills.append(fill)

        def _set_account(account: AccountInfo) -> None:
            with self._lock:
                self._account = account

        def _set_positions(positions: list[Position]) -> None:
            with self._lock:
                self._positions = list(positions)

        def _set_meta(**kwargs: Any) -> None:
            with self._lock:
                if "account_name" in kwargs and kwargs["account_name"]:
                    self._connection.account_name = str(kwargs["account_name"])
                if "session_id" in kwargs and kwargs["session_id"]:
                    self._session_id = str(kwargs["session_id"])

        apply_fabric_message_to_bridge_state(
            msg,
            record_fill=_record_fill,
            set_account=_set_account,
            set_positions=_set_positions,
            set_connection_meta=_set_meta,
        )

        which = msg.WhichOneof("payload") if hasattr(msg, "WhichOneof") else None
        if which == "auth_result" and getattr(msg.auth_result, "ok", False):
            with self._lock:
                self._connection.state = "connected"
        if which == "state_sync":
            with self._lock:
                self._last_state_hash = str(getattr(msg.state_sync, "state_hash", "") or "")
                if self._connection.state == "degraded":
                    # Reconciled after reconnect — allow orders only if Fabric left SAFE.
                    pass
        if which == "safety_alert":
            alert = msg.safety_alert
            alert_dict = {
                "alert_type": int(alert.alert_type),
                "severity": int(alert.severity),
                "message": str(alert.message),
                "recommended_action": str(alert.recommended_action),
                "correlation_id": str(alert.correlation_id),
            }
            with self._lock:
                self._safety_alerts.append(alert_dict)
                if len(self._safety_alerts) > 200:
                    self._safety_alerts = self._safety_alerts[-100:]
                if alert.alert_type in (
                    fabric_pb2.SAFETY_ALERT_TYPE_SAFE_MODE_ENTERED,
                    fabric_pb2.SAFETY_ALERT_TYPE_HEARTBEAT_TIMEOUT,
                ):
                    self._fabric_safe_mode = "SAFE"
            self.metrics.record_safety_alert()
            logger.warning(
                "Fabric SafetyAlert type=%s msg=%s",
                alert.alert_type,
                alert.message,
            )
            if alert.alert_type in (
                fabric_pb2.SAFETY_ALERT_TYPE_SAFE_MODE_ENTERED,
                fabric_pb2.SAFETY_ALERT_TYPE_HEARTBEAT_TIMEOUT,
                fabric_pb2.SAFETY_ALERT_TYPE_NT_CONNECTION_LOST,
                fabric_pb2.SAFETY_ALERT_TYPE_FLATTEN_ISSUED,
            ):
                with self._lock:
                    # Degraded: block new orders via connection state policy.
                    if self._connection.state == "connected":
                        self._connection.state = "degraded"
        if which == "heartbeat":
            sm = int(getattr(msg.heartbeat, "fabric_safe_mode", 0) or 0)
            mode_map = {0: "UNKNOWN", 1: "NORMAL", 2: "SAFE", 3: "FULL_SAFE"}
            with self._lock:
                self._fabric_safe_mode = mode_map.get(sm, "UNKNOWN")


__all__ = ["BridgeInboundMixin", "_utc_now_iso"]
