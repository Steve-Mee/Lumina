"""TransportMixin methods for TradeReconciler."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any

import requests
import websockets

from lumina_core.engine.errors import format_error_code

logger = logging.getLogger(__name__)


class TransportMixin:
    def _run_websocket_loop(self) -> None:
        app = self._app()
        while not self.stop_requested:
            try:
                self._update_status(connection_state="connecting", status="connecting")
                asyncio.run(self._websocket_listener())
                self._backoff_seconds = 1.0
                if self.stop_requested:
                    break
            except Exception as exc:
                if self.stop_requested:
                    break
                code = format_error_code("RECONCILE_WEBSOCKET", exc, fallback="LOOP_FAILED")
                app.logger.error(f"TradeReconciler websocket error [{code}]: {exc}")
                self._update_status(connection_state="error", status="reconnecting", last_error=str(exc))
                sleep_for = min(self._backoff_seconds + random.uniform(0.0, 0.5), self._max_backoff_seconds)
                app.logger.warning(f"TradeReconciler reconnect in {sleep_for:.1f}s")
                time.sleep(sleep_for)
                self._backoff_seconds = min(self._backoff_seconds * 2.0, self._max_backoff_seconds)
            self._flush_timeouts()
        self._update_status(connection_state="stopped", status="stopped")

    async def _websocket_listener(self) -> None:
        app = self._app()
        uri = self.engine.config.crosstrade_fill_ws_url
        headers = {"Authorization": f"Bearer {self.engine.config.crosstrade_token or ''}"}
        heartbeat_seconds = self._heartbeat_seconds
        account = self.engine.config.crosstrade_account
        async with websockets.connect(uri, additional_headers=headers, ping_interval=None, ping_timeout=None) as ws:
            await ws.send(
                json.dumps(
                    {
                        "action": "subscribe",
                        "accounts": [account],
                        "channels": ["fills", "executions"],
                    }
                )
            )
            app.logger.info("TradeReconciler websocket connected")
            self._update_status(connection_state="connected", status="streaming", last_error=None)
            while not self.stop_requested:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=heartbeat_seconds)
                except asyncio.TimeoutError:
                    pong = await ws.ping()
                    await asyncio.wait_for(pong, timeout=heartbeat_seconds)
                    self._flush_timeouts()
                    continue
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    app.logger.debug("TradeReconciler received non-JSON websocket frame")
                    continue
                event_hint = str(data.get("type") or data.get("event") or data.get("channel") or "").lower()
                if event_hint in {"heartbeat", "ping", "pong", "keepalive", "subscribed", "ack"}:
                    if event_hint == "ping":
                        try:
                            await ws.send(json.dumps({"action": "pong", "ts": datetime.now(timezone.utc).isoformat()}))
                        except Exception:
                            logger.exception("TradeReconciler failed to send websocket pong")
                    self._update_status(last_message_ts=datetime.now(timezone.utc).isoformat(), status="streaming")
                    self._flush_timeouts()
                    continue
                self.ingest_fill_event(data)
                self._flush_timeouts()
            try:
                await ws.close()
            except Exception:
                logger.exception("TradeReconciler failed to close websocket cleanly")

    def _run_polling_loop(self) -> None:
        app = self._app()
        url = str(self.engine.config.crosstrade_fill_poll_url or "").strip()
        if not url:
            app.logger.warning(
                "TradeReconciler polling enabled without CROSSTRADE_FILL_POLL_URL; timeout fallback only"
            )
        self._update_status(connection_state="polling", status="polling")
        while not self.stop_requested:
            if url:
                try:
                    response = requests.get(
                        url,
                        headers={"Authorization": f"Bearer {self.engine.config.crosstrade_token or ''}"},
                        timeout=8,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        rows = data if isinstance(data, list) else data.get("fills", [])
                        for row in rows:
                            if isinstance(row, dict):
                                self.ingest_fill_event(row)
                except Exception as exc:
                    code = format_error_code("RECONCILE_POLLING", exc, fallback="LOOP_FAILED")
                    app.logger.error(f"TradeReconciler polling error [{code}]: {exc}")
                    self._update_status(connection_state="error", status="polling_error", last_error=str(exc))
            self._flush_timeouts()
            time.sleep(2.0)

    def run_self_test(self) -> dict[str, Any]:
        sample = {
            "type": "fill",
            "instrument": self.engine.config.instrument,
            "side": "SELL",
            "quantity": 2,
            "fillPrice": 5012.25,
            "commission": 1.25,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fillId": "selftest-fill-001",
        }
        normalized = self._normalize_fill_event(sample)
        ok = normalized is not None
        result = {
            "status": "ok" if ok else "failed",
            "raw_sample": sample,
            "normalized": {
                "fill_id": normalized.fill_id,
                "symbol": normalized.symbol,
                "side": normalized.side,
                "quantity": normalized.quantity,
                "price": normalized.price,
                "commission": normalized.commission,
                "event_ts": normalized.event_ts.isoformat(),
            }
            if normalized is not None
            else None,
        }
        self._update_status(status="self_test", last_self_test=result)
        return result
