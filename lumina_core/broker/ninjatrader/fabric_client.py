"""gRPC client for the LUMINA Execution Fabric (Brain → Fabric).

Fabric hosts the server (ADR-0035). This client is mockable via an injected
``grpc.Channel`` (used in tests with an in-process server).
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Order, Position
from lumina_core.broker.ninjatrader import fabric_mapper as mapper

try:
    import grpc
    from lumina_core.broker.ninjatrader.generated import fabric_pb2, fabric_pb2_grpc
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "grpc / fabric stubs required. pip install grpcio && python scripts/generate_fabric_proto.py"
    ) from exc

logger = logging.getLogger(__name__)

EventCallback = Callable[[fabric_pb2.FabricMessage], None]


@dataclass(slots=True)
class FabricConfig:
    host: str = "127.0.0.1"
    port: int = 50051
    auth_token: str = ""
    auth_token_env: str = "LUMINA_FABRIC_TOKEN"
    client_name: str = "lumina-brain"
    client_version: str = "1.0"
    mode_context: str = "sim"
    command_timeout_seconds: float = 10.0
    connect_timeout_seconds: float = 5.0
    heartbeat_interval_ms: int = 1000
    heartbeat_timeout_ms: int = 5000

    @property
    def target(self) -> str:
        return f"{self.host}:{int(self.port)}"

    def resolve_token(self) -> str:
        if self.auth_token:
            return self.auth_token
        env_name = str(self.auth_token_env or "LUMINA_FABRIC_TOKEN").strip() or "LUMINA_FABRIC_TOKEN"
        token = str(os.getenv(env_name, "") or "").strip()
        if not token:
            # Backward-compatible fallback used by ADR-0029 WS sketches.
            token = str(os.getenv("LUMINA_NT8_API_KEY", "") or "").strip()
        return token

    @classmethod
    def from_engine_config(cls, config: Any | None, *, mode_context: str = "sim") -> FabricConfig:
        if config is None:
            return cls(mode_context=mode_context)
        host = str(getattr(config, "fabric_host", None) or getattr(config, "ninjatrader_fabric_host", "127.0.0.1") or "127.0.0.1")
        port = int(getattr(config, "fabric_port", None) or getattr(config, "ninjatrader_fabric_port", 50051) or 50051)
        token_env = str(
            getattr(config, "fabric_auth_token_env", None)
            or getattr(config, "ninjatrader_fabric_auth_token_env", "LUMINA_FABRIC_TOKEN")
            or "LUMINA_FABRIC_TOKEN"
        )
        explicit_token = str(getattr(config, "ninjatrader_nt8_api_key", None) or getattr(config, "fabric_auth_token", "") or "").strip()
        return cls(
            host=host,
            port=port,
            auth_token=explicit_token,
            auth_token_env=token_env,
            mode_context=mode_context,
            command_timeout_seconds=float(getattr(config, "fabric_command_timeout_seconds", 10.0) or 10.0),
            connect_timeout_seconds=float(getattr(config, "fabric_connect_timeout_seconds", 5.0) or 5.0),
            heartbeat_interval_ms=int(getattr(config, "fabric_heartbeat_interval_ms", 1000) or 1000),
            heartbeat_timeout_ms=int(getattr(config, "fabric_heartbeat_timeout_ms", 5000) or 5000),
        )


@dataclass
class _PendingCommand:
    event: threading.Event
    result: dict[str, Any] | None = None


class FabricGrpcClient:
    """Synchronous façade over Fabric TradingStream + unary GetAccountState."""

    def __init__(
        self,
        config: FabricConfig | None = None,
        *,
        channel: grpc.Channel | None = None,
        on_message: EventCallback | None = None,
    ) -> None:
        self.config = config or FabricConfig()
        self._external_channel = channel
        self._channel: grpc.Channel | None = channel
        self._stub: fabric_pb2_grpc.ExecutionFabricStub | None = None
        self._on_message = on_message
        self._lock = threading.RLock()
        self._outbound: queue.Queue[fabric_pb2.BrainMessage | None] = queue.Queue()
        self._pending: dict[str, _PendingCommand] = {}
        self._stream_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._connected = False
        self._session_id: str | None = None
        self._account_name: str = ""
        self._safe_mode: int = fabric_pb2.SAFE_MODE_STATE_UNSPECIFIED
        self._hb_seq = 0
        self._owns_channel = channel is None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    @property
    def session_id(self) -> str | None:
        with self._lock:
            return self._session_id

    @property
    def account_name(self) -> str:
        with self._lock:
            return self._account_name

    @property
    def safe_mode(self) -> int:
        with self._lock:
            return self._safe_mode

    def set_mode_context(self, mode: str) -> None:
        self.config.mode_context = str(mode or "sim")

    def set_on_message(self, callback: EventCallback | None) -> None:
        self._on_message = callback

    def connect(self) -> bool:
        """Open channel, start TradingStream, authenticate."""
        with self._lock:
            if self._connected:
                return True
            self._stop.clear()
            try:
                if self._channel is None:
                    self._channel = grpc.insecure_channel(self.config.target)
                    self._owns_channel = True
                self._stub = fabric_pb2_grpc.ExecutionFabricStub(self._channel)
            except Exception:
                logger.exception("Fabric channel open failed target=%s", self.config.target)
                return False

        self._stream_thread = threading.Thread(
            target=self._stream_loop,
            name="fabric-trading-stream",
            daemon=True,
        )
        self._stream_thread.start()

        token = self.config.resolve_token()
        if not token:
            logger.error("Fabric auth token empty (set %s or LUMINA_NT8_API_KEY)", self.config.auth_token_env)
            self.disconnect()
            return False

        corr = str(uuid.uuid4())
        auth_waiter = self._register_pending(f"auth:{corr}")
        self._outbound.put(
            mapper.auth_hello_message(
                token=token,
                client_name=self.config.client_name,
                client_version=self.config.client_version,
                mode_context=self.config.mode_context,
            )
        )
        # Auth correlation is special-cased in handler under key "auth".
        # Register both keys so either path can complete.
        with self._lock:
            self._pending["auth"] = auth_waiter

        if not auth_waiter.event.wait(timeout=self.config.connect_timeout_seconds):
            logger.error("Fabric auth timed out after %ss", self.config.connect_timeout_seconds)
            self.disconnect()
            return False

        result = auth_waiter.result or {}
        if result.get("type") == "error" or not result.get("ok"):
            logger.error("Fabric auth failed: %s", result.get("message", result))
            self.disconnect()
            return False

        with self._lock:
            self._connected = True
            self._session_id = str(result.get("session_id") or "")
            self._account_name = str(result.get("account_name") or "")

        if self.config.heartbeat_interval_ms > 0:
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name="fabric-heartbeat",
                daemon=True,
            )
            self._heartbeat_thread.start()

        logger.info(
            "Fabric connected target=%s session=%s account=%s",
            self.config.target,
            self._session_id,
            self._account_name,
        )
        return True

    def disconnect(self) -> None:
        self._stop.set()
        try:
            self._outbound.put_nowait(None)
        except Exception:
            pass
        with self._lock:
            self._connected = False
            for waiter in self._pending.values():
                if not waiter.event.is_set():
                    waiter.result = {
                        "type": "error",
                        "code": "DISCONNECTED",
                        "message": "Fabric client disconnected",
                    }
                    waiter.event.set()
            self._pending.clear()
            channel = self._channel if self._owns_channel else None
            self._stub = None
            if self._owns_channel:
                self._channel = None
        if self._stream_thread and self._stream_thread.is_alive() and threading.current_thread() is not self._stream_thread:
            self._stream_thread.join(timeout=2.0)
        if self._heartbeat_thread and self._heartbeat_thread.is_alive() and threading.current_thread() is not self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1.0)
        if channel is not None:
            try:
                channel.close()
            except Exception:
                logger.debug("Fabric channel close failed", exc_info=True)
        self._stream_thread = None
        self._heartbeat_thread = None

    def place_order_sync(
        self,
        order: Order,
        *,
        client_order_id: str,
        correlation_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not self.is_connected:
            return {"type": "error", "code": "DISCONNECTED", "message": "Fabric not connected"}
        corr = correlation_id or str(uuid.uuid4())
        cmd = mapper.order_to_place_command(
            order,
            client_order_id=client_order_id,
            correlation_id=corr,
            mode_context=self.config.mode_context,
        )
        return self._send_and_wait(
            mapper.place_command_to_brain_message(cmd),
            wait_key=corr,
            alt_keys=(client_order_id,),
            timeout_seconds=timeout_seconds,
        )

    def cancel_order_sync(
        self,
        *,
        client_order_id: str = "",
        nt_order_id: str = "",
        correlation_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not self.is_connected:
            return {"type": "error", "code": "DISCONNECTED", "message": "Fabric not connected"}
        corr = correlation_id or str(uuid.uuid4())
        msg = mapper.cancel_to_brain_message(
            client_order_id=client_order_id,
            nt_order_id=nt_order_id,
            correlation_id=corr,
        )
        return self._send_and_wait(msg, wait_key=corr, alt_keys=(client_order_id,), timeout_seconds=timeout_seconds)

    def flatten_sync(
        self,
        *,
        instrument: str = "",
        correlation_id: str | None = None,
        emergency: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not self.is_connected:
            return {"type": "error", "code": "DISCONNECTED", "message": "Fabric not connected"}
        corr = correlation_id or str(uuid.uuid4())
        msg = mapper.flatten_to_brain_message(instrument=instrument, correlation_id=corr, emergency=emergency)
        return self._send_and_wait(msg, wait_key=corr, timeout_seconds=timeout_seconds)

    def modify_order_sync(
        self,
        *,
        client_order_id: str = "",
        nt_order_id: str = "",
        quantity: int = 0,
        price: float = 0.0,
        stop_price: float = 0.0,
        correlation_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not self.is_connected:
            return {"type": "error", "code": "DISCONNECTED", "message": "Fabric not connected"}
        corr = correlation_id or str(uuid.uuid4())
        msg = mapper.modify_to_brain_message(
            client_order_id=client_order_id,
            nt_order_id=nt_order_id,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            correlation_id=corr,
        )
        return self._send_and_wait(
            msg,
            wait_key=corr,
            alt_keys=(client_order_id,) if client_order_id else (),
            timeout_seconds=timeout_seconds,
        )

    def get_account_state(self) -> tuple[AccountInfo | None, list[Position], str]:
        """Unary GetAccountState. Returns (account, positions, error_code)."""
        stub = self._stub
        if stub is None:
            return None, [], "DISCONNECTED"
        try:
            state = stub.GetAccountState(
                fabric_pb2.GetAccountStateRequest(correlation_id=str(uuid.uuid4())),
                timeout=self.config.command_timeout_seconds,
            )
        except grpc.RpcError as exc:
            return None, [], f"RPC_{exc.code().name}"  # type: ignore[union-attr]
        account = mapper.account_state_to_info(state)
        positions: list[Position] = []
        for p in state.positions:
            mapped = mapper.position_update_to_position(p)
            if mapped is not None:
                positions.append(mapped)
        with self._lock:
            if state.account.account_name:
                self._account_name = state.account.account_name
            self._safe_mode = int(state.safe_mode)
        return account, positions, "ok"

    def _register_pending(self, key: str) -> _PendingCommand:
        waiter = _PendingCommand(event=threading.Event())
        with self._lock:
            self._pending[key] = waiter
        return waiter

    def _send_and_wait(
        self,
        message: fabric_pb2.BrainMessage,
        *,
        wait_key: str,
        alt_keys: tuple[str, ...] = (),
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        waiter = self._register_pending(wait_key)
        for alt in alt_keys:
            if alt and alt != wait_key:
                with self._lock:
                    self._pending[alt] = waiter
        self._outbound.put(message)
        timeout = float(timeout_seconds if timeout_seconds is not None else self.config.command_timeout_seconds)
        if not waiter.event.wait(timeout=timeout):
            with self._lock:
                self._pending.pop(wait_key, None)
                for alt in alt_keys:
                    self._pending.pop(alt, None)
            return {
                "type": "error",
                "code": "TIMEOUT",
                "message": f"Fabric command timed out after {timeout}s",
                "correlation_id": wait_key,
            }
        with self._lock:
            self._pending.pop(wait_key, None)
            for alt in alt_keys:
                self._pending.pop(alt, None)
        return waiter.result or {
            "type": "error",
            "code": "EMPTY_RESPONSE",
            "message": "No response from Fabric",
            "correlation_id": wait_key,
        }

    def _complete(self, key: str, result: dict[str, Any]) -> None:
        with self._lock:
            waiter = self._pending.get(key)
            if waiter is None:
                return
            if waiter.result is None:
                waiter.result = result
            waiter.event.set()

    def _request_iterator(self):  # type: ignore[no-untyped-def]
        while not self._stop.is_set():
            try:
                item = self._outbound.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is None:
                return
            yield item

    def _stream_loop(self) -> None:
        stub = self._stub
        if stub is None:
            return
        try:
            for msg in stub.TradingStream(self._request_iterator()):
                if self._stop.is_set():
                    break
                self._handle_fabric_message(msg)
        except grpc.RpcError as exc:
            if not self._stop.is_set():
                logger.warning("Fabric TradingStream ended: %s", exc)
                with self._lock:
                    self._connected = False
                self._fail_all_pending(f"STREAM_ERROR:{exc.code().name}")  # type: ignore[union-attr]
        except Exception:
            if not self._stop.is_set():
                logger.exception("Fabric TradingStream crashed")
                with self._lock:
                    self._connected = False
                self._fail_all_pending("STREAM_CRASH")

    def _fail_all_pending(self, code: str) -> None:
        with self._lock:
            pending = list(self._pending.items())
            self._pending.clear()
        for _key, waiter in pending:
            if not waiter.event.is_set():
                waiter.result = {"type": "error", "code": code, "message": "Fabric stream lost"}
                waiter.event.set()

    def _handle_fabric_message(self, msg: fabric_pb2.FabricMessage) -> None:
        if self._on_message is not None:
            try:
                self._on_message(msg)
            except Exception:
                logger.exception("Fabric on_message callback failed")

        which = msg.WhichOneof("payload")
        if which == "auth_result":
            ar = msg.auth_result
            result = {
                "type": "auth_result",
                "ok": bool(ar.ok),
                "session_id": ar.session_id,
                "account_name": ar.account_name,
                "code": ar.code,
                "message": ar.message or ("ok" if ar.ok else "auth failed"),
            }
            if not ar.ok:
                result["type"] = "error"
            self._complete("auth", result)
            return

        if which == "order_event":
            event = msg.order_event
            response = mapper.order_event_to_response_dict(event)
            # First terminal-ish ack for waiters: submitted/working/filled/rejected complete place.
            if event.correlation_id:
                self._complete(event.correlation_id, response)
            if event.client_order_id:
                self._complete(event.client_order_id, response)
            return

        if which == "command_reject":
            reject = msg.command_reject
            response = mapper.command_reject_to_response_dict(reject)
            if reject.correlation_id:
                self._complete(reject.correlation_id, response)
            if reject.client_order_id:
                self._complete(reject.client_order_id, response)
            return

        if which == "heartbeat":
            with self._lock:
                self._safe_mode = int(msg.heartbeat.fabric_safe_mode)
            return

        if which == "state_sync":
            with self._lock:
                if msg.state_sync.account.account_name:
                    self._account_name = msg.state_sync.account.account_name
                self._safe_mode = int(msg.state_sync.safe_mode)
            logger.info(
                "Fabric StateSync hash=%s safe_mode=%s orders=%s positions=%s",
                msg.state_sync.state_hash,
                msg.state_sync.safe_mode,
                len(msg.state_sync.open_orders),
                len(msg.state_sync.positions),
            )
            return

        if which == "safety_alert":
            logger.warning(
                "Fabric SafetyAlert type=%s severity=%s msg=%s action=%s",
                msg.safety_alert.alert_type,
                msg.safety_alert.severity,
                msg.safety_alert.message,
                msg.safety_alert.recommended_action,
            )

    def _heartbeat_loop(self) -> None:
        interval = max(0.2, self.config.heartbeat_interval_ms / 1000.0)
        while not self._stop.wait(timeout=interval):
            if not self.is_connected:
                continue
            with self._lock:
                self._hb_seq += 1
                seq = self._hb_seq
            try:
                self._outbound.put(mapper.heartbeat_message(sequence_number=seq))
            except Exception:
                logger.debug("Fabric heartbeat enqueue failed", exc_info=True)


def apply_fabric_message_to_bridge_state(
    msg: fabric_pb2.FabricMessage,
    *,
    record_fill: Callable[[Fill], None],
    set_account: Callable[[AccountInfo], None],
    set_positions: Callable[[list[Position]], None],
    set_connection_meta: Callable[..., None] | None = None,
) -> None:
    """Helper for bridge_service to apply inbound Fabric stream events."""
    which = msg.WhichOneof("payload")
    if which == "order_event":
        fill = mapper.order_event_to_fill(msg.order_event)
        if fill is not None:
            record_fill(fill)
        return
    if which == "state_sync":
        account, positions, _orders = mapper.state_sync_to_domain(msg.state_sync)
        set_account(account)
        set_positions(positions)
        if set_connection_meta is not None and msg.state_sync.account.account_name:
            set_connection_meta(account_name=msg.state_sync.account.account_name)
        return
    if which == "position_update":
        # Incremental updates are left to full sync callers; optional hook.
        return
    if which == "auth_result" and msg.auth_result.ok and set_connection_meta is not None:
        set_connection_meta(
            account_name=msg.auth_result.account_name,
            session_id=msg.auth_result.session_id,
        )
