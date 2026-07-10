"""FillMatchingMixin methods for TradeReconciler."""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone

from lumina_core.engine.trade_reconciler.schemas import FillEvent, PendingTradeClose

logger = logging.getLogger(__name__)


class FillMatchingMixin:
    def _timeout_seconds(self) -> float:
        raw = self.engine.config.reconciliation_timeout_seconds
        return float(15.0 if raw is None else raw)

    def _flush_timeouts(self) -> None:
        timeout_seconds = self._timeout_seconds()
        items = self._get_pending_closes()
        kept: list[PendingTradeClose] = []
        now = datetime.now(timezone.utc)
        for pending in items:
            if pending.status != "closing":
                continue
            age = (now - pending.detected_ts).total_seconds()
            if age >= timeout_seconds:
                self._finalize_pending_close(pending, fill=None, status="timeout_no_broker_fill")
            else:
                kept.append(pending)
        self._set_pending_closes(kept)

    def _try_match_recent_fills(self) -> None:
        items = self._get_pending_closes()
        unresolved: list[PendingTradeClose] = []
        matched_ids: set[str] = set()
        consumed_fill_ids: set[str] = set()
        for pending in items:
            fill_bundle = self._find_matching_fill_bundle(pending=pending, consumed_fill_ids=consumed_fill_ids)
            if fill_bundle is None:
                unresolved.append(pending)
                continue
            fill = self._build_aggregate_fill(fill_bundle)
            self._finalize_pending_close(pending, fill=fill, status="reconciled_fill")
            for item in fill_bundle:
                consumed_fill_ids.add(item.fill_id)
                matched_ids.add(item.fill_id)
        if matched_ids:
            self._recent_fills = deque(
                [fill for fill in self._recent_fills if fill.fill_id not in matched_ids], maxlen=100
            )
        self._set_pending_closes(unresolved)

    def _find_matching_fill_bundle(
        self, *, pending: PendingTradeClose, consumed_fill_ids: set[str]
    ) -> list[FillEvent] | None:
        timeout_seconds = self._timeout_seconds()
        fills = sorted(self._recent_fills, key=lambda row: row.event_ts)
        matched: list[FillEvent] = []
        matched_qty = 0
        for fill in fills:
            if fill.fill_id in consumed_fill_ids:
                continue
            age = abs((fill.event_ts - pending.detected_ts).total_seconds())
            if age > timeout_seconds:
                continue
            if fill.symbol != pending.symbol:
                continue
            if fill.side and fill.side != pending.expected_close_side:
                continue
            matched.append(fill)
            matched_qty += int(fill.quantity or 0)
            if pending.quantity <= 0:
                break
            if matched_qty >= pending.quantity:
                break
        if not matched:
            return None
        if pending.quantity > 0 and matched_qty < pending.quantity:
            return None
        return matched

    @staticmethod
    def _build_aggregate_fill(fill_bundle: list[FillEvent]) -> FillEvent:
        if len(fill_bundle) == 1:
            return fill_bundle[0]
        quantity = sum(max(int(item.quantity or 0), 0) for item in fill_bundle)
        notional = sum(float(item.price) * max(int(item.quantity or 0), 0) for item in fill_bundle)
        avg_price = float(notional / quantity) if quantity > 0 else float(fill_bundle[-1].price)
        commission = sum(float(item.commission or 0.0) for item in fill_bundle)
        event_ts = max(item.event_ts for item in fill_bundle)
        fill_ids = [item.fill_id for item in fill_bundle]
        aggregate_id = f"{fill_ids[0]}+{len(fill_ids)}"

        # Phase 2 Slice 25: Propagate lineage from the fill bundle for multi-leg netting.
        # Use the first fill's lineage as the root for the aggregate (consistent with single-leg from Slice 24).
        # All fills in the bundle should share the same decision_context_id in practice.
        dcid = getattr(fill_bundle[0], "decision_context_id", None)
        ph = getattr(fill_bundle[0], "prev_hash", None)
        if not dcid and isinstance(getattr(fill_bundle[0], "raw_payload", None), dict):
            dcid = fill_bundle[0].raw_payload.get("decision_context_id")
        if not ph and isinstance(getattr(fill_bundle[0], "raw_payload", None), dict):
            ph = fill_bundle[0].raw_payload.get("prev_hash")

        return FillEvent(
            fill_id=aggregate_id,
            symbol=fill_bundle[-1].symbol,
            side=fill_bundle[-1].side,
            quantity=quantity,
            price=avg_price,
            commission=commission,
            event_ts=event_ts,
            raw_payload={
                "fill_parts": [item.raw_payload for item in fill_bundle],
                "fill_ids": fill_ids,
                "decision_context_id": dcid,
                "prev_hash": ph,
            },
            # Carry first-class lineage on the aggregate for downstream hash chain (Slice 25 multi-leg)
            decision_context_id=dcid,
            prev_hash=ph,
        )
