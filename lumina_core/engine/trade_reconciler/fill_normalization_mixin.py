"""FillNormalizationMixin methods for TradeReconciler."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from lumina_core.engine.trade_reconciler.schemas import FillEvent

logger = logging.getLogger(__name__)


class FillNormalizationMixin:
    @staticmethod
    def _wire_order_ids_from_payload(payload: dict[str, Any]) -> tuple[str, str]:
        """Extract orderId / clientOrderId from WS or poll wire frames (nested-aware)."""
        if not isinstance(payload, dict):
            return "", ""
        nested = None
        for key in ("fill", "execution", "data", "payload"):
            value = payload.get(key)
            if isinstance(value, dict):
                nested = value
                break
        source = nested or payload

        def _first(*keys: str, default: str = "") -> str:
            for key in keys:
                if key in source and source.get(key) is not None:
                    return str(source.get(key) or "").strip()
                if key in payload and payload.get(key) is not None:
                    return str(payload.get(key) or "").strip()
            return default

        return _first("orderId", "order_id", default=""), _first(
            "clientOrderId", "client_order_id", default=""
        )

    def _resolve_broker_for_lineage(self) -> Any | None:
        """Best-effort broker handle (engine, container, or get_broker callable)."""
        broker = getattr(self.engine, "broker", None)
        if broker is not None:
            return broker
        container = getattr(self.engine, "container", None)
        if container is not None:
            broker = getattr(container, "broker", None)
            if broker is not None:
                return broker
        get_broker = getattr(self.engine, "get_broker", None)
        if callable(get_broker):
            return get_broker()
        return None

    def _overlay_pending_broker_lineage(self, fill: FillEvent, wire_payload: dict[str, Any]) -> None:
        """Best-effort overlay from CrossTrade pending map (WS/poll paths; fail-open)."""
        if fill.decision_context_id:
            return
        try:
            broker = self._resolve_broker_for_lineage()
            if broker is None or not hasattr(broker, "lookup_pending_lineage"):
                return
            order_id, client_order_id = self._wire_order_ids_from_payload(wire_payload)
            if not order_id and not client_order_id:
                return
            lineage = broker.lookup_pending_lineage(
                order_id=order_id,
                client_order_id=client_order_id,
                consume=True,
            )
            if not lineage:
                return
            dcid = lineage.get("decision_context_id")
            ph = lineage.get("prev_hash")
            pet = lineage.get("prev_event_topic")
            if dcid:
                fill.decision_context_id = str(dcid)
            if ph:
                fill.prev_hash = str(ph)
            if pet:
                fill.prev_event_topic = str(pet)
            if isinstance(fill.raw_payload, dict):
                for key, value in lineage.items():
                    if value and key not in fill.raw_payload:
                        fill.raw_payload[key] = value
        except Exception:
            pass

    @staticmethod
    def _normalize_fill_event(payload: dict[str, Any]) -> FillEvent | None:
        raw = payload
        if not isinstance(raw, dict):
            return None

        nested = None
        for key in ("fill", "execution", "data", "payload"):
            value = raw.get(key)
            if isinstance(value, dict):
                nested = value
                break
        source = nested or raw

        event_hint = str(raw.get("type") or raw.get("event") or raw.get("channel") or "").lower()
        candidate_hint = str(source.get("type") or source.get("event") or "").lower()
        if event_hint and not any(token in event_hint for token in ("fill", "execution")):
            if candidate_hint and not any(token in candidate_hint for token in ("fill", "execution")):
                numeric_keys = {"fillPrice", "avgPrice", "price", "executionPrice"}
                if not any(key in source for key in numeric_keys):
                    return None

        def _first(*keys: str, default=None):
            for key in keys:
                if key in source and source.get(key) is not None:
                    return source.get(key)
                if key in raw and raw.get(key) is not None:
                    return raw.get(key)
            return default

        symbol = str(_first("instrument", "symbol", "ticker", default="")).strip().upper()
        if not symbol:
            return None

        quantity_raw = _first("quantity", "qty", "filledQty", "fillQty", default=0)
        price_raw = _first("fillPrice", "avgPrice", "executionPrice", "price", default=None)
        if price_raw is None:
            return None

        side_raw = str(_first("side", "action", "orderSide", default="")).strip().upper()
        if side_raw in {"LONG", "BOT"}:
            side_raw = "BUY"
        elif side_raw in {"SHORT", "SLD"}:
            side_raw = "SELL"

        ts_raw = _first("timestamp", "time", "filledAt", "executedAt", default=None)
        event_ts = datetime.now(timezone.utc)
        if isinstance(ts_raw, str):
            try:
                event_ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/engine/trade_reconciler.py:718")
                event_ts = datetime.now(timezone.utc)

        fill_id = str(_first("fillId", "executionId", "id", "orderId", default="")).strip()
        if not fill_id:
            fill_id = f"{symbol}-{int(event_ts.timestamp() * 1000)}-{price_raw}"

        try:
            quantity = int(abs(float(quantity_raw or 0)))
            price = float(price_raw)
            commission = float(_first("commission", "fees", default=0.0) or 0.0)
        except (TypeError, ValueError):
            return None

        # Phase 2 live broker lineage polish: promote from raw/wire (now reliably overlaid by CrossTradeBroker pending map)
        # so FillEvent first-class + typed publish + decision_lineage consumers see it (was raw-only best-effort).
        dcid = _first("decision_context_id", "dcid", default=None)
        ph = _first("prev_hash", "prevHash", default=None)
        pet = _first("prev_event_topic", "prevEventTopic", default=None)

        fe = FillEvent(
            fill_id=fill_id,
            symbol=symbol,
            side=side_raw,
            quantity=quantity,
            price=price,
            commission=commission,
            event_ts=event_ts,
            raw_payload=raw,
        )
        # Promote lineage (now reliably present from broker overlay for live) to first-class attrs on FillEvent
        if dcid is not None:
            fe.decision_context_id = dcid
        if ph is not None:
            fe.prev_hash = ph
        if pet is not None:
            fe.prev_event_topic = pet
        return fe
