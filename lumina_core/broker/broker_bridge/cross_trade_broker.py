"""CrossTrade live broker implementation."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

from lumina_core.broker.broker_bridge.admission import run_final_arbitration
from lumina_core.broker.broker_bridge.base import BrokerBridge
from lumina_core.broker.broker_bridge.cross_trade_payload import parse_account_info_payload
from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Order, OrderResult, Position

@dataclass(slots=True)
class CrossTradeBroker(BrokerBridge):
    api_key: str
    account: str
    websocket_url: str = "wss://app.crosstrade.io/ws/stream"
    base_url: str = "https://app.crosstrade.io"
    fill_poll_url: str = ""
    logger: logging.Logger | None = None
    timeout_seconds: float = 10.0
    engine: Any | None = None
    _session: requests.Session | None = field(default=None, init=False)
    _last_client_order_id: str = field(default="", init=False)

    # Phase 2 live broker lineage (pending map by client/server order id for async fill correlation on poll/WS)
    # Populated on submit from Order.metadata (Slice 15 attach), overlaid on get_fills / returned OrderResult.
    # Mirrors PaperBroker exact pattern per class docstring. Additive; best-effort + raw fallback preserved.
    _pending_lineage: dict[str, dict[str, str | None]] = field(default_factory=dict, init=False, repr=False)

    def connect(self) -> bool:
        if self._session is None:
            self._session = requests.Session()
        return True

    def disconnect(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key or ''}"}

    def _client(self) -> requests.Session:
        if self._session is None:
            self.connect()
        assert self._session is not None
        return self._session

    def lookup_pending_lineage(
        self,
        *,
        order_id: str = "",
        client_order_id: str = "",
        consume: bool = True,
    ) -> dict[str, str | None]:
        """Resolve submit-time lineage from the pending map (WS/poll/get_fills overlay)."""
        oid = str(order_id or "").strip()
        coid = str(client_order_id or "").strip()
        lookup = self._pending_lineage.get(oid) or (self._pending_lineage.get(coid) if coid else None) or {}
        if not lookup:
            return {}
        result = dict(lookup)
        if consume:
            if oid:
                self._pending_lineage.pop(oid, None)
            if coid:
                self._pending_lineage.pop(coid, None)
        return result

    def submit_order(self, order: Order) -> OrderResult:
        # Phase 2 live broker lineage wiring (Slice 16/19 pattern from Paper + docstring)
        # Extract early (before arb) from Order (populated upstream by policy_engine Slice 15 from final_arb + gate_entry prev_hash).
        # Store in pending map for async fill correlation on success path.
        meta = getattr(order, "metadata", {}) or {}
        lineage = {}
        if isinstance(meta, dict):
            for k in ("decision_context_id", "prev_hash", "prev_event_topic"):
                if meta.get(k):
                    lineage[k] = meta[k]
        client_order_id = str(order.metadata.get("clientOrderId") or f"lumina-{uuid.uuid4()}") if hasattr(order, 'metadata') else f"lumina-{uuid.uuid4()}"
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
                for k, v in lineage.items():
                    setattr(res, k, v)
            return res

        payload = {
            "instrument": order.symbol,
            "action": str(order.side).upper(),
            "orderType": str(order.order_type).upper(),
            "quantity": int(order.quantity),
            "stopLoss": float(order.stop_loss),
            "takeProfit": float(order.take_profit),
            "clientOrderId": client_order_id,
        }

        self._last_client_order_id = client_order_id
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                response = self._client().post(
                    f"{self.base_url}/v1/api/accounts/{self.account}/orders/place",
                    headers=self._headers(),
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                body = response.json() if response.content else {}
                accepted = response.status_code in (200, 201)
                if accepted or response.status_code < 500 or attempt == attempts:
                    server_oid = str(body.get("orderId", ""))
                    # Inject lineage into this return (first-class + raw) + store pending under server oid for fill correlation
                    res = OrderResult(
                        accepted=accepted,
                        order_id=server_oid,
                        status="accepted" if accepted else "rejected",
                        filled_qty=int(body.get("filledQuantity", 0) or 0),
                        fill_price=float(body.get("fillPrice", 0.0) or 0.0),
                        message=str(body.get("message", "")),
                        raw=body if isinstance(body, dict) else {"raw": body},
                    )
                    if lineage:
                        for k, v in lineage.items():
                            setattr(res, k, v)
                            if isinstance(res.raw, dict):
                                res.raw.setdefault(k, v)
                        if server_oid:
                            self._pending_lineage[server_oid] = lineage
                    return res
            except Exception as exc:
                if attempt == attempts:
                    if self.logger is not None:
                        self.logger.error(f"CrossTrade submit_order failed after retries: {exc}")
                    res = OrderResult(
                        accepted=False,
                        order_id="",
                        status="error",
                        message=str(exc),
                    )
                    if lineage:
                        for k, v in lineage.items():
                            setattr(res, k, v)
                    return res
            time.sleep(min(0.25 * (2 ** (attempt - 1)), 1.0))
        # Error path: lineage not attached (error before server response); caller can retry or log
        return OrderResult(
            accepted=False,
            order_id="",
            status="error",
            message="submit_order retry loop exhausted",
        )

    def get_account_info(self) -> AccountInfo:
        """REST snapshot from Crosstrade (not NinjaTrader UI directly).

        Field names vary by API version; we map common aliases so SIM/demo balances surface when present.
        """
        try:
            response = self._client().get(
                f"{self.base_url}/v1/api/accounts/{self.account}",
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            data = response.json() if response.content else {}
            if not isinstance(data, dict):
                data = {"raw": data}

            if response.status_code >= 400:
                if self.logger is not None:
                    self.logger.warning(
                        "CrossTrade get_account_info HTTP %s account=%s body=%s",
                        response.status_code,
                        self.account,
                        (response.text or "")[:400],
                    )
                return AccountInfo(balance=0.0, equity=0.0, raw=data)

            return parse_account_info_payload(data, account=self.account, logger=self.logger)
        except Exception as exc:
            if self.logger is not None:
                self.logger.error(f"CrossTrade get_account_info failed: {exc}")
            return AccountInfo(balance=0.0, equity=0.0)

    def get_positions(self) -> list[Position]:
        try:
            response = self._client().get(
                f"{self.base_url}/v1/api/accounts/{self.account}/positions",
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            payload = response.json() if response.content else []
            rows = payload if isinstance(payload, list) else payload.get("positions", [])
            result: list[Position] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                qty = int(row.get("quantity", 0) or 0)
                side = "BUY" if qty >= 0 else "SELL"
                result.append(
                    Position(
                        symbol=str(row.get("instrument", "")),
                        quantity=qty,
                        avg_price=float(row.get("avgPrice", 0.0) or 0.0),
                        side=side,
                        raw=row,
                    )
                )
            return result
        except Exception as exc:
            if self.logger is not None:
                self.logger.error(f"CrossTrade get_positions failed: {exc}")
            return []

    def get_fills(self) -> list[Fill]:
        if not self.fill_poll_url:
            return []
        try:
            response = self._client().get(
                self.fill_poll_url,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            payload = response.json() if response.content else []
            rows = payload if isinstance(payload, list) else payload.get("fills", [])
            fills: list[Fill] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                oid = str(row.get("orderId", ""))
                coid = str(row.get("clientOrderId") or row.get("client_order_id") or "")
                peek = self.lookup_pending_lineage(order_id=oid, client_order_id=coid, consume=False)
                dcid = row.get("decision_context_id") or peek.get("decision_context_id")
                ph = row.get("prev_hash") or peek.get("prev_hash")
                pet = row.get("prev_event_topic") or peek.get("prev_event_topic")
                if oid and (dcid or ph or pet):
                    self.lookup_pending_lineage(order_id=oid, client_order_id=coid, consume=True)
                fills.append(
                    Fill(
                        fill_id=str(row.get("fillId", "")),
                        order_id=oid,
                        symbol=str(row.get("instrument", "")),
                        side=str(row.get("action", "")).upper(),
                        quantity=int(row.get("quantity", 0) or 0),
                        price=float(row.get("fillPrice", 0.0) or 0.0),
                        timestamp=str(row.get("timestamp", datetime.now(timezone.utc).isoformat())),
                        commission=float(row.get("commission", 0.0) or 0.0),
                        # Phase 2 live broker wiring: prefer pending overlay (from submit-time Order.metadata) then wire
                        decision_context_id=dcid,
                        prev_hash=ph,
                        prev_event_topic=pet,
                        raw=row,
                    )
                )
            return fills
        except Exception as exc:
            if self.logger is not None:
                self.logger.error(f"CrossTrade get_fills failed: {exc}")
            return []

    def cancel_all_orders(self) -> dict[str, Any]:
        response = self._client().post(
            f"{self.base_url}/v1/api/accounts/{self.account}/orders/cancel",
            headers=self._headers(),
            json={},
            timeout=self.timeout_seconds,
        )
        try:
            body = response.json() if response.content else {}
        except Exception:
            body = {"raw_text": (response.text or "")[:600]}
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"CrossTrade cancel orders rejected HTTP {response.status_code}: "
                f"{(response.text or '')[:400]}"
            )
        if not isinstance(body, dict):
            body = {"raw": body}
        order_ids = body.get("orderIds") if isinstance(body.get("orderIds"), list) else []
        cancelled_rows = [{"order_id": str(order_id)} for order_id in order_ids]
        cancelled_count = len(cancelled_rows)
        return {
            "status": "ok",
            "cancelled_count": cancelled_count,
            "cancelled": cancelled_rows,
            "raw": body,
        }

    def subscribe_to_websocket(self) -> None:
        for attempt in range(1, 4):
            try:
                import websocket  # type: ignore

                ws = websocket.create_connection(
                    self.websocket_url,
                    header=[f"Authorization: Bearer {self.api_key}"],
                    timeout=self.timeout_seconds,
                )
                subscribe_payload = {
                    "action": "subscribe",
                    "accounts": [self.account],
                    "channels": ["fills", "executions"],
                }
                ws.send(json.dumps(subscribe_payload))
                try:
                    ws.ping("lumina-keepalive")
                except Exception:
                    logging.exception("CrossTrade websocket ping failed during subscribe warmup")
                ws.settimeout(0.5)
                try:
                    ws.recv()
                except Exception:
                    logging.exception("CrossTrade websocket recv probe failed during subscribe warmup")
                ws.close()
                return
            except Exception as exc:
                if self.logger is not None:
                    self.logger.warning(
                        "CrossTrade websocket subscribe attempt %s failed: %s",
                        attempt,
                        exc,
                    )
                time.sleep(min(0.5 * attempt, 2.0))
