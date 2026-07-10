"""FillIngestMixin methods for TradeReconciler."""

from __future__ import annotations

from typing import Any

import logging


logger = logging.getLogger(__name__)


class FillIngestMixin:
    def ingest_fill_event(self, payload: dict[str, Any]) -> bool:
        fill = self._normalize_fill_event(payload)
        if fill is None:
            return False
        self._overlay_pending_broker_lineage(fill, payload)
        if fill.fill_id in self._seen_fill_ids:
            return False
        if any(existing.fill_id == fill.fill_id for existing in self._recent_fills):
            return False
        self._seen_fill_ids.append(fill.fill_id)
        self._recent_fills.append(fill)

        # Phase 2 Slice 18: Best-effort publishing of typed execution.fill.received
        # with lineage if present in the normalized fill or original payload.
        try:
            engine = self._app()
            bus = getattr(engine, "event_bus", None)
            if bus and hasattr(bus, "publish_validated"):
                from lumina_core.agent_orchestration.schemas import (
                    EXECUTION_FILL_RECEIVED_TOPIC,
                    ExecutionFill,
                )
                payload = {
                    "fill_id": fill.fill_id,
                    "order_id": getattr(fill, "order_id", None),
                    "symbol": fill.symbol,
                    "side": fill.side,
                    "quantity": fill.quantity,
                    "price": fill.price,
                    "timestamp": fill.event_ts.isoformat() if hasattr(fill, "event_ts") else fill.timestamp,
                    "commission": fill.commission,
                    "raw": dict(getattr(fill, "raw", {})) if hasattr(fill, "raw") else {},
                }
                # Pull lineage if it was attached to the fill (from broker or payload).
                # Phase 2 Slice 19 note + live wiring: prefer first-class attrs on the fill object
                # (now set by CrossTradeBroker overlay + reconciler promote), fall back to raw (Paper + legacy).
                # This makes typed execution.fill.received + downstream (decision_lineage, Guardian, provenance)
                # have real ctx for live production paths (not just paper/sim).
                dcid = getattr(fill, "decision_context_id", None)
                ph = getattr(fill, "prev_hash", None)
                pet = getattr(fill, "prev_event_topic", None)
                if not dcid:
                    raw = getattr(fill, "raw", {}) or {}
                    if isinstance(raw, dict):
                        dcid = raw.get("decision_context_id")
                        ph = ph or raw.get("prev_hash")
                        pet = pet or raw.get("prev_event_topic")
                if dcid:
                    payload["decision_context_id"] = dcid
                if ph:
                    payload["prev_hash"] = ph
                if pet:
                    payload["prev_event_topic"] = pet

                ExecutionFill.model_validate(payload)
                bus.publish_validated(
                    topic=EXECUTION_FILL_RECEIVED_TOPIC,
                    producer="trade_reconciler",
                    payload=payload,
                )
        except Exception:
            # Best-effort only
            pass

        self._append_audit_event(
            {
                "event": "fill_received",
                "fill_id": fill.fill_id,
                "symbol": fill.symbol,
                "side": fill.side,
                "quantity": fill.quantity,
                "price": fill.price,
                "commission": fill.commission,
                "event_ts": fill.event_ts.isoformat(),
            }
        )
        self._update_status(
            connection_state="connected",
            status="fill_received",
            last_message_ts=fill.event_ts.isoformat(),
            last_fill_sample={
                "fill_id": fill.fill_id,
                "symbol": fill.symbol,
                "side": fill.side,
                "quantity": fill.quantity,
                "price": fill.price,
                "commission": fill.commission,
            },
        )
        self._try_match_recent_fills()
        return True
