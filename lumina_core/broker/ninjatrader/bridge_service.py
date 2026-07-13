"""Session state and transport for the NinjaTrader WebSocket bridge."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Position
from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability
from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction, normalize_trade_mode
from lumina_core.broker.ninjatrader.schemas import (
    AccountSnapshotFrame,
    ConnectionStatusFrame,
    ExecutionFrame,
    PositionUpdateFrame,
    parse_inbound_frame,
)

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
    """Transport-only bridge between Core and the NT8 add-on WebSocket."""

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
        self._connection = NinjaTraderConnectionState()
        self._session_id: str | None = None
        self._fills: list[Fill] = []
        self._fill_ids: set[str] = set()
        self._account: AccountInfo = AccountInfo(balance=0.0, equity=0.0)
        self._positions: list[Position] = []
        self._pending_commands: dict[str, _CommandWaiter] = {}

    def set_trade_mode(self, mode: str) -> None:
        with self._lock:
            self.trade_mode = normalize_trade_mode(mode)

    def set_configured_account(self, account: str) -> None:
        with self._lock:
            self.configured_account = str(account or "").strip()

    def register_send(self, send_fn: SendFn | None) -> None:
        with self._lock:
            self._send_fn = send_fn

    def on_disconnect(self) -> None:
        with self._lock:
            self._connection.state = "disconnected"
            self._send_fn = None
            self._session_id = None
            for waiter in self._pending_commands.values():
                waiter.result = {"type": "error", "code": "DISCONNECTED", "message": "NT8 WebSocket disconnected"}
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
        """Enqueue an outbound command and wait for ack/error (broker-only entry)."""
        correlation_id = str(frame.get("correlation_id", "") or uuid.uuid4())
        frame["correlation_id"] = correlation_id

        with self._lock:
            connection = self.get_connection_state()
            allowed, reason = assert_nt_bridge_capability(
                action=NtBridgeAction.SUBMIT_ORDER
                if frame.get("type") == "submit_order"
                else NtBridgeAction.CANCEL,
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
            send_fn = self._send_fn
            if send_fn is None:
                return {
                    "type": "error",
                    "code": "DISCONNECTED",
                    "message": "No active NT8 WebSocket session",
                    "correlation_id": correlation_id,
                }
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
