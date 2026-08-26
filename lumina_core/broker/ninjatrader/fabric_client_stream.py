"""Fabric TradingStream / heartbeat / pending-command helpers.

Extracted from ``fabric_client`` (Wave B2 PR-C3). Behavior-preserving split.
Sync order API remains on ``FabricGrpcClient`` in ``fabric_client``.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any

from lumina_core.broker.ninjatrader import fabric_mapper as mapper

try:
    import grpc
    from lumina_core.broker.ninjatrader.generated import fabric_pb2
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "grpc / fabric stubs required. pip install grpcio && python scripts/generate_fabric_proto.py"
    ) from exc

logger = logging.getLogger(__name__)


@dataclass
class _PendingCommand:
    event: threading.Event
    result: dict[str, Any] | None = None


class FabricClientStreamMixin:
    """Stream loop, heartbeat, and pending-command wait/complete."""

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
            return

        if which == "market_data":
            md = msg.market_data
            inst = str(getattr(md, "instrument", "") or "").strip().upper()
            if not inst:
                return
            quote = {
                "instrument": inst,
                "last": float(getattr(md, "last", 0.0) or 0.0),
                "bid": float(getattr(md, "bid", 0.0) or 0.0),
                "ask": float(getattr(md, "ask", 0.0) or 0.0),
                "volume": int(getattr(md, "volume", 0) or 0),
                "timestamp_unix_ms": int(getattr(md, "timestamp_unix_ms", 0) or 0),
            }
            with self._lock:
                cache = getattr(self, "_last_quotes", None)
                if cache is None:
                    self._last_quotes = {}  # type: ignore[attr-defined]
                    cache = self._last_quotes  # type: ignore[attr-defined]
                cache[inst] = quote
            return

        if which == "position_update":
            pu = msg.position_update
            logger.info(
                "Fabric PositionUpdate instrument=%s qty=%s side=%s",
                getattr(pu, "instrument", ""),
                getattr(pu, "quantity", 0),
                getattr(pu, "side", ""),
            )
            return

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


__all__ = ["FabricClientStreamMixin", "_PendingCommand"]
