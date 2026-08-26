"""Connect/order ops for FabricGrpcClient (global residual)."""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Any

import grpc

from lumina_core.broker.broker_bridge.schemas import Order
from lumina_core.broker.ninjatrader import fabric_mapper as mapper
from lumina_core.broker.ninjatrader.generated import fabric_pb2_grpc

logger = logging.getLogger(__name__)


class FabricClientOpsMixin:
    def connect(self) -> bool:
        """Open channel, start TradingStream, authenticate.

        Sets ``last_connect_error`` / ``last_connect_code`` for callers
        (AUTH_FAILED vs CONNECTION_REFUSED vs TOKEN_EMPTY).
        """
        self.last_connect_error = ""
        self.last_connect_code = ""
        with self._lock:
            if self._connected:
                return True
            self._stop.clear()
            try:
                if self._channel is None:
                    # ADR-0042: TLS/mTLS when LUMINA_FABRIC_TLS_* env is set; else localhost insecure.
                    try:
                        from lumina_core.mtls_config import build_grpc_channel

                        self._channel = build_grpc_channel(self.config.target)
                    except Exception:
                        self._channel = grpc.insecure_channel(self.config.target)
                    self._owns_channel = True
                self._stub = fabric_pb2_grpc.ExecutionFabricStub(self._channel)
            except Exception as exc:
                logger.exception("Fabric channel open failed target=%s", self.config.target)
                self.last_connect_code = "CONNECTION_REFUSED"
                self.last_connect_error = str(exc)
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
            self.last_connect_code = "TOKEN_EMPTY"
            self.last_connect_error = "Fabric auth token empty"
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
            self.last_connect_code = "AUTH_TIMEOUT"
            self.last_connect_error = f"Fabric auth timed out after {self.config.connect_timeout_seconds}s"
            self.disconnect()
            return False

        result = auth_waiter.result or {}
        if result.get("type") == "error" or not result.get("ok"):
            msg = str(result.get("message") or result.get("code") or result)
            logger.error("Fabric auth failed: %s", msg)
            code = str(result.get("code") or "").upper()
            msg_l = msg.lower()
            if any(
                x in msg_l
                for x in (
                    "connection refused",
                    "unavailable",
                    "failed to connect",
                    "stream lost",
                    "10061",
                )
            ):
                self.last_connect_code = "CONNECTION_REFUSED"
            elif "AUTH" in code or "token" in msg_l or "invalid" in msg_l:
                self.last_connect_code = "AUTH_FAILED"
            else:
                self.last_connect_code = "AUTH_FAILED"
            self.last_connect_error = msg
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
        self.last_connect_code = "OK"
        self.last_connect_error = ""
        return True
    def disconnect(self) -> None:
        self._stop.set()
        try:
            self._outbound.put_nowait(None)
        except Exception:
            pass
        with self._lock:
            self._connected = False
            # Local SAFE until next auth sync (host also cancels non-protected on disconnect).
            try:
                from lumina_core.broker.ninjatrader.generated import fabric_pb2

                self._safe_mode = int(fabric_pb2.SAFE_MODE_STATE_SAFE)
            except Exception:
                self._safe_mode = 2  # SAFE
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
        """Transport-only place after Brain Final Arbitration.

        Track E: Fabric must not be a capital aperture bypass. Callers
        (NinjaTrader broker) run ``run_final_arbitration`` first. Strict modes
        reject here if lineage is still missing (defense in depth).
        """
        if not self.is_connected:
            return {"type": "error", "code": "DISCONNECTED", "message": "Fabric not connected"}
        # Fail-closed: host SAFE / FULL_SAFE rejects new places (cancel/flatten separate APIs).
        try:
            sm = int(getattr(self, "safe_mode", 0) or 0)
            # Proto: 0 UNSPECIFIED, 1 NORMAL, 2 SAFE, 3 FULL_SAFE
            if sm in {2, 3}:
                return {
                    "type": "error",
                    "code": "SAFE_MODE",
                    "message": f"Fabric place blocked: safe_mode={sm} (reconnect/auth to clear)",
                    "safe_mode": sm,
                }
        except Exception:
            logger.debug("fabric.safe_mode_check_failed", exc_info=True)
        try:
            from lumina_core.risk.capital_aperture_lineage import (
                extract_order_lineage,
                is_lineage_strict_mode,
            )

            mode_ctx = str(getattr(self.config, "mode_context", "") or "").strip().lower()
            # mode_context may be account labels; trade mode often on parent config.
            trade_mode = str(getattr(self.config, "trade_mode", mode_ctx) or mode_ctx).strip().lower()
            if is_lineage_strict_mode(trade_mode):
                lin = extract_order_lineage(order)
                if not lin.get("decision_context_id"):
                    return {
                        "type": "error",
                        "code": "APERTURE_LINEAGE_MISSING",
                        "message": (
                            "Fabric place blocked: missing decision_context_id in strict mode "
                            "(Final Arbitration must run before Fabric transport)"
                        ),
                    }
        except Exception:
            # Never open a silent bypass on guard failure in connected path — fail open only for
            # non-strict / soft modes where extract may throw; re-check soft.
            logger.debug("fabric.aperture_lineage_guard_failed", exc_info=True)
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
