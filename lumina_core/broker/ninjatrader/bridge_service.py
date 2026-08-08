"""Session state and transport for the NinjaTrader bridge (Fabric gRPC + legacy WS).

Thin façade (Wave B2 PR-C3): inbound frames live in ``bridge_inbound``;
sync command routing lives in ``bridge_command_sync``.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, Callable

from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Position
from lumina_core.broker.ninjatrader.bridge_command_sync import BridgeCommandSyncMixin, _CommandWaiter
from lumina_core.broker.ninjatrader.bridge_inbound import BridgeInboundMixin
from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.fabric_metrics import FabricClientMetrics
from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability
from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction, normalize_trade_mode

if TYPE_CHECKING:
    from lumina_core.broker.ninjatrader.fabric_client import FabricGrpcClient

logger = logging.getLogger(__name__)

SendFn = Callable[[dict[str, Any]], None]

_SERVICE: "NinjaTraderBridgeService | None" = None
_SERVICE_LOCK = threading.Lock()


class NinjaTraderBridgeService(BridgeInboundMixin, BridgeCommandSyncMixin):
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
            # Track E residual: Brain treats disconnect as SAFE until re-auth (no new places).
            self._fabric_safe_mode = "SAFE"
            self._send_fn = None
            self._session_id = None
            for waiter in self._pending_commands.values():
                waiter.result = {"type": "error", "code": "DISCONNECTED", "message": "NT8 / Fabric disconnected"}
                waiter.event.set()
            self._pending_commands.clear()
        logger.warning(
            "nt.bridge.disconnect → SAFE_MODE (brain-side); places blocked until reconnect+auth"
        )

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


__all__ = [
    "NinjaTraderBridgeService",
    "SendFn",
    "get_ninjatrader_bridge_service",
    "reset_ninjatrader_bridge_service",
]
