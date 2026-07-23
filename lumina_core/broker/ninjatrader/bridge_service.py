"""Session state and transport for the NinjaTrader bridge (Fabric gRPC + legacy WS)."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Order, Position
from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.fabric_metrics import FabricClientMetrics
from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability
from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction, normalize_trade_mode
from lumina_core.broker.ninjatrader.schemas import (
    AccountSnapshotFrame,
    ConnectionStatusFrame,
    ExecutionFrame,
    PositionUpdateFrame,
    parse_inbound_frame,
)

if TYPE_CHECKING:
    from lumina_core.broker.ninjatrader.fabric_client import FabricGrpcClient

logger = logging.getLogger(__name__)

SendFn = Callable[[dict[str, Any]], None]

_SERVICE: "NinjaTraderBridgeService | None" = None
_SERVICE_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class _CommandWaiter:
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None


class NinjaTraderBridgeService:
    """Session + command façade for NT8 via Execution Fabric gRPC (preferred) or legacy WS send_fn."""

    def __init__(
        self,
        *,
        configured_account: str = "",
        trade_mode: str = "sim",
        ninjatrader_enabled: bool = True,
        command_timeout_seconds: float = 10.0,
    ) -> None:
        self.configured_account = str(configured_account or "").strip()
        self.trade_mode = normalize_trade_mode(trade_mode)
        self.ninjatrader_enabled = bool(ninjatrader_enabled)
        self.command_timeout_seconds = float(command_timeout_seconds)
        self._lock = threading.RLock()
        self._send_fn: SendFn | None = None
        self._fabric: FabricGrpcClient | None = None
        self._connection = NinjaTraderConnectionState()
        self._session_id: str | None = None
        self._fills: list[Fill] = []
        self._fill_ids: set[str] = set()
        self._account: AccountInfo = AccountInfo(balance=0.0, equity=0.0)
        self._positions: list[Position] = []
        self._pending_commands: dict[str, _CommandWaiter] = {}
        self._safety_alerts: list[dict[str, Any]] = []
        self._last_state_hash: str = ""
        self._fabric_safe_mode: str = "UNKNOWN"
        self.metrics = FabricClientMetrics()

    def set_trade_mode(self, mode: str) -> None:
        with self._lock:
            self.trade_mode = normalize_trade_mode(mode)
            if self._fabric is not None:
                self._fabric.set_mode_context(self.trade_mode)

    def set_configured_account(self, account: str) -> None:
        with self._lock:
            self.configured_account = str(account or "").strip()

    def register_send(self, send_fn: SendFn | None) -> None:
        with self._lock:
            self._send_fn = send_fn

    def attach_fabric_client(self, client: FabricGrpcClient | None) -> None:
        """Attach Execution Fabric gRPC client (ADR-0035). Preferred over WS send_fn."""
        with self._lock:
            self._fabric = client
            if client is not None:
                client.set_mode_context(self.trade_mode)
                client.set_on_message(self._on_fabric_message)

    def get_fabric_client(self) -> FabricGrpcClient | None:
        with self._lock:
            return self._fabric

    def connect_fabric(self) -> bool:
        """Connect Fabric client and mark bridge session connected on success."""
        fabric = self.get_fabric_client()
        if fabric is None:
            return False
        fabric.set_mode_context(self.trade_mode)
        self.begin_authentication()
        ok = fabric.connect()
        self.metrics.record_connect(ok=ok)
        if not ok:
            with self._lock:
                self._connection.state = "error"
            return False
        with self._lock:
            self._session_id = fabric.session_id
            self._connection.state = "connected"
            self._connection.account_name = fabric.account_name or self.configured_account
            self._connection.client_name = fabric.config.client_name
            self._connection.client_version = fabric.config.client_version
            self._fabric_safe_mode = "NORMAL"
        # Refresh account snapshot when possible.
        account, positions, code = fabric.get_account_state()
        if code == "ok" and account is not None:
            with self._lock:
                self._account = account
                self._positions = positions
                if account.raw.get("account_name"):
                    self._connection.account_name = str(account.raw["account_name"])
                sm = account.raw.get("safe_mode")
                if sm is not None:
                    mode_map = {0: "UNKNOWN", 1: "NORMAL", 2: "SAFE", 3: "FULL_SAFE"}
                    self._fabric_safe_mode = mode_map.get(int(sm), "UNKNOWN")
        return True

    def on_disconnect(self) -> None:
        fabric = self.get_fabric_client()
        if fabric is not None:
            try:
                fabric.disconnect()
            except Exception:
                logger.debug("Fabric disconnect failed", exc_info=True)
            self.metrics.record_disconnect()
        with self._lock:
            self._connection.state = "disconnected"
            self._send_fn = None
            self._session_id = None
            for waiter in self._pending_commands.values():
                waiter.result = {"type": "error", "code": "DISCONNECTED", "message": "NT8 / Fabric disconnected"}
                waiter.event.set()
            self._pending_commands.clear()

    def begin_authentication(self) -> None:
        with self._lock:
            self._connection.state = "authenticating"

    def set_client_info(self, *, name: str, version: str) -> None:
        with self._lock:
            self._connection.client_name = str(name)
            self._connection.client_version = str(version)

    def authenticate_session(self, *, session_id: str, account_name: str = "") -> None:
        with self._lock:
            self._session_id = session_id
            self._connection.state = "connected"
            if account_name:
                self._connection.account_name = account_name

    def get_connection_state(self) -> NinjaTraderConnectionState:
        fabric = self.get_fabric_client()
        fabric_target = ""
        gateway = ""
        if fabric is not None:
            fabric_target = fabric.config.target
            gateway = "fabric"
            sm = int(getattr(fabric, "safe_mode", 0) or 0)
            # Proto SafeModeState: 0 UNSPECIFIED, 1 NORMAL, 2 SAFE, 3 FULL_SAFE
            mode_map = {0: "UNKNOWN", 1: "NORMAL", 2: "SAFE", 3: "FULL_SAFE"}
            with self._lock:
                if self._fabric_safe_mode == "UNKNOWN" and sm in mode_map:
                    self._fabric_safe_mode = mode_map[sm]
        with self._lock:
            return NinjaTraderConnectionState(
                state=self._connection.state,
                account_name=self._connection.account_name,
                connection_name=self._connection.connection_name,
                ninjatrader_version=self._connection.ninjatrader_version,
                last_bar_ts=self._connection.last_bar_ts,
                session_id=self._session_id,
                client_name=self._connection.client_name,
                client_version=self._connection.client_version,
                safe_mode=self._fabric_safe_mode,
                fabric_target=fabric_target,
                gateway=gateway,
                last_state_hash=self._last_state_hash,
                recent_alerts=len(self._safety_alerts),
                metrics=self.metrics.snapshot(),
            )

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

    def get_safety_alerts(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._safety_alerts)

    def get_last_state_hash(self) -> str:
        with self._lock:
            return self._last_state_hash

    def get_fills(self) -> list[Fill]:
        with self._lock:
            return list(self._fills)

    def get_account_info(self) -> AccountInfo:
        with self._lock:
            return AccountInfo(
                balance=self._account.balance,
                equity=self._account.equity,
                available_margin=self._account.available_margin,
                realized_pnl_today=self._account.realized_pnl_today,
                currency=self._account.currency,
                raw=dict(self._account.raw),
            )

    def get_positions(self) -> list[Position]:
        with self._lock:
            return list(self._positions)

    def ingest_market_data(self, payload: dict[str, Any]) -> tuple[bool, str]:
        """Guarded market-data ingest path."""
        with self._lock:
            connection = self.get_connection_state()
            allowed, reason = assert_nt_bridge_capability(
                action=NtBridgeAction.MARKET_DATA,
                trade_mode=self.trade_mode,
                connection=connection,
                configured_account=self.configured_account,
                ninjatrader_enabled=self.ninjatrader_enabled,
            )
            if not allowed:
                return False, reason
            if payload.get("type") == "bar":
                ts = str(payload.get("ts", "") or "")
                if ts:
                    self._connection.last_bar_ts = ts
        return True, "ok"


def get_ninjatrader_bridge_service(
    *,
    configured_account: str = "",
    trade_mode: str = "sim",
    ninjatrader_enabled: bool = True,
    command_timeout_seconds: float = 10.0,
    reset: bool = False,
) -> NinjaTraderBridgeService:
    global _SERVICE
    with _SERVICE_LOCK:
        if reset or _SERVICE is None:
            _SERVICE = NinjaTraderBridgeService(
                configured_account=configured_account,
                trade_mode=trade_mode,
                ninjatrader_enabled=ninjatrader_enabled,
                command_timeout_seconds=command_timeout_seconds,
            )
        else:
            if configured_account:
                _SERVICE.set_configured_account(configured_account)
            if trade_mode:
                _SERVICE.set_trade_mode(trade_mode)
            _SERVICE.ninjatrader_enabled = bool(ninjatrader_enabled)
        return _SERVICE


def reset_ninjatrader_bridge_service() -> None:
    global _SERVICE
    with _SERVICE_LOCK:
        _SERVICE = None
