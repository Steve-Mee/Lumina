"""Paper (simulation) broker implementation."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import lumina_core.broker.broker_bridge as _bb
from lumina_core.broker.broker_bridge.admission import run_final_arbitration
from lumina_core.broker.broker_bridge.base import BrokerBridge
from lumina_core.broker.broker_bridge.schemas import (
    AccountInfo,
    Fill,
    Order,
    OrderResult,
    Position,
    paper_position_from_fills,
)
from lumina_core.risk.cost_model import TradeExecutionCostModel

@dataclass(slots=True)
class PaperBroker(BrokerBridge):
    """
    Paper (simulation) broker implementation.

    Phase 2 Slice 15/16 lineage note:
    When an Order carrying decision_context_id + prev_hash (populated by the
    authoritative post-Final-Arbitration path in policy_engine) reaches submit_order,
    the resulting Fill and OrderResult now have the same lineage fields copied into
    their .raw dicts (best-effort). This is the second downstream cryptographic link.

    Live broker implementations (e.g. CrossTradeBroker) should apply the exact same
    pattern when they receive fill confirmations from the wire: read lineage from the
    original Order (if present) or from the submission context, and attach it to the
    Fill/OrderResult objects they create or return.
    """
    engine: Any | None = None
    logger: logging.Logger | None = None
    starting_balance: float = 50000.0
    _connected: bool = field(default=False, init=False)
    _positions: dict[str, Position] = field(default_factory=dict, init=False)
    _fills: list[Fill] = field(default_factory=list, init=False)
    _cost_model: TradeExecutionCostModel | None = field(default=None, init=False)

    def _resolve_cost_model(self, symbol: str) -> TradeExecutionCostModel:
        if self._cost_model is not None:
            return self._cost_model
        cfg = getattr(self.engine, "config", None)
        instrument = str(symbol or getattr(cfg, "instrument", "MES"))
        self._cost_model = TradeExecutionCostModel.from_config(cfg, instrument=instrument)
        return self._cost_model

    def _estimate_atr(self, fallback_price: float) -> float:
        if self.engine is None:
            return max(0.25, abs(float(fallback_price)) * 0.001)
        try:
            with self.engine.live_data_lock:
                frame = getattr(self.engine, "ohlc_1min", None)
                if frame is not None and len(frame) > 0:
                    last = frame.iloc[-1]
                    high = float(last.get("high", 0.0) or 0.0)
                    low = float(last.get("low", 0.0) or 0.0)
                    if high > 0 and low > 0 and high >= low:
                        return max(0.25, high - low)
        except Exception:
            logging.exception("BrokerBridge failed to estimate ATR from live OHLC; using fallback")
        return max(0.25, abs(float(fallback_price)) * 0.001)

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def submit_order(self, order: Order) -> OrderResult:
        if not self._connected:
            self.connect()
        allowed, reason = run_final_arbitration(self.engine, order)
        if not allowed:
            return OrderResult(
                accepted=False,
                order_id="",
                status="rejected",
                message=f"FinalArbitration blocked order: {reason}",
            )

        side = str(order.side).upper()
        if side not in {"BUY", "SELL"}:
            return OrderResult(
                accepted=False,
                order_id="",
                status="rejected",
                message=f"Unsupported side: {order.side}",
            )

        fill_price = 0.0
        if self.engine is not None:
            try:
                with self.engine.live_data_lock:
                    if self.engine.live_quotes:
                        fill_price = float(self.engine.live_quotes[-1]["last"])
                    elif len(self.engine.ohlc_1min) > 0:
                        fill_price = float(self.engine.ohlc_1min["close"].iloc[-1])
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/engine/broker_bridge.py:313")
                fill_price = 0.0

        fill_price = float(fill_price or 0.0)
        model = self._resolve_cost_model(order.symbol)
        atr = self._estimate_atr(fill_price if fill_price > 0 else 1.0)
        cost = model.cost_for_trade(
            price=max(fill_price, 1e-9),
            quantity=max(1, int(order.quantity)),
            atr=atr,
            avg_volume=1000.0,
            time_period="midday",
        )
        per_side_slip_ticks = max(0.0, float(cost.total_slippage_ticks))
        if model.slippage_sigma > 0:
            per_side_slip_ticks = max(
                0.0,
                per_side_slip_ticks + _bb.random.gauss(0.0, float(model.slippage_sigma)),
            )
        per_side_price_slip = per_side_slip_ticks * float(model.tick_size)
        if side == "BUY":
            fill_price = fill_price + per_side_price_slip
        else:
            fill_price = fill_price - per_side_price_slip

        order_id = f"paper-{uuid.uuid4()}"

        # Phase 2 Slice 16: Propagate downstream lineage (decision_context_id + prev_hash)
        # from the Order (populated by Slice 15 at the post-Final-Arbitration boundary)
        # into the Fill and OrderResult. This is purely additive metadata population.
        fill_raw = {"broker": "paper"}
        result_raw = {"broker": "paper", "fill_id": None}

        try:
            meta = getattr(order, "metadata", {}) or {}
            if isinstance(meta, dict):
                if meta.get("decision_context_id"):
                    fill_raw["decision_context_id"] = meta["decision_context_id"]
                    result_raw["decision_context_id"] = meta["decision_context_id"]
                if meta.get("prev_hash"):
                    fill_raw["prev_hash"] = meta["prev_hash"]
                    result_raw["prev_hash"] = meta["prev_hash"]
                if meta.get("prev_event_topic"):
                    fill_raw["prev_event_topic"] = meta["prev_event_topic"]
                    result_raw["prev_event_topic"] = meta["prev_event_topic"]
        except Exception:
            pass  # best-effort only; never break fill creation

        fill = Fill(
            fill_id=f"fill-{uuid.uuid4()}",
            order_id=order_id,
            symbol=order.symbol,
            side=side,
            quantity=int(order.quantity),
            price=fill_price,
            timestamp=datetime.now(timezone.utc).isoformat(),
            commission=float(cost.total_fees_usd_per_side),
            # Phase 2 Slice 19: Populate first-class lineage fields (in addition to raw for transition)
            decision_context_id=meta.get("decision_context_id") if isinstance(meta, dict) else None,
            prev_hash=meta.get("prev_hash") if isinstance(meta, dict) else None,
            prev_event_topic=meta.get("prev_event_topic") if isinstance(meta, dict) else None,
            raw=fill_raw,
        )
        self._fills.append(fill)
        self._sync_positions_from_fills()

        # Phase 2 Slice 18 + 19: Best-effort publishing of typed execution.fill.received event
        # with full lineage. Now prefers the first-class fields on the Fill dataclass
        # (promoted Slice 19) so the typed event contract and domain model stay aligned.
        # Falls back to raw only during transition / for legacy fills.
        try:
            bus = getattr(self.engine, "event_bus", None)
            if bus and hasattr(bus, "publish_validated"):
                from lumina_core.agent_orchestration.schemas import (
                    EXECUTION_FILL_RECEIVED_TOPIC,
                    ExecutionFill,
                )
                payload = {
                    "fill_id": fill.fill_id,
                    "order_id": order_id,
                    "symbol": fill.symbol,
                    "side": fill.side,
                    "quantity": fill.quantity,
                    "price": fill.price,
                    "timestamp": fill.timestamp,
                    "commission": fill.commission,
                    "raw": dict(fill.raw) if isinstance(fill.raw, dict) else {},
                }
                # Phase 2 Slice 19: Prefer first-class lineage fields on the Fill instance
                # (set at construction from Order metadata). raw is fallback only.
                dcid = getattr(fill, "decision_context_id", None)
                ph = getattr(fill, "prev_hash", None)
                pet = getattr(fill, "prev_event_topic", None)
                if not dcid and isinstance(fill.raw, dict):
                    dcid = fill.raw.get("decision_context_id")
                if not ph and isinstance(fill.raw, dict):
                    ph = fill.raw.get("prev_hash")
                if not pet and isinstance(fill.raw, dict):
                    pet = fill.raw.get("prev_event_topic")
                if dcid:
                    payload["decision_context_id"] = dcid
                if ph:
                    payload["prev_hash"] = ph
                if pet:
                    payload["prev_event_topic"] = pet

                # Validate before publishing (follows event-bus-contract)
                ExecutionFill.model_validate(payload)
                bus.publish_validated(
                    topic=EXECUTION_FILL_RECEIVED_TOPIC,
                    producer="paper_broker",
                    payload=payload,
                )
        except Exception:
            # Best-effort only — never break fill creation or submission
            pass

        result_raw["fill_id"] = fill.fill_id
        return OrderResult(
            accepted=True,
            order_id=order_id,
            status="filled",
            filled_qty=int(order.quantity),
            fill_price=fill_price,
            message="paper fill",
            raw=result_raw,
        )

    def get_account_info(self) -> AccountInfo:
        if self.engine is None:
            return AccountInfo(
                balance=self.starting_balance,
                equity=self.starting_balance,
                available_margin=self.starting_balance,
            )

        return AccountInfo(
            balance=float(getattr(self.engine, "account_balance", self.starting_balance)),
            equity=float(getattr(self.engine, "account_equity", self.starting_balance)),
            available_margin=float(
                getattr(self.engine, "available_margin", getattr(self.engine, "account_equity", self.starting_balance))
            ),
            realized_pnl_today=float(getattr(self.engine, "realized_pnl_today", 0.0)),
        )

    def _sync_positions_from_fills(self) -> None:
        self._positions.clear()
        symbols = {str(f.symbol).strip() for f in self._fills}
        for sym in symbols:
            pos = paper_position_from_fills(self._fills, sym)
            if pos is not None:
                self._positions[sym] = pos

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    def get_fills(self) -> list[Fill]:
        return list(self._fills)

    def cancel_all_orders(self) -> dict[str, Any]:
        # Paper broker fills market orders immediately; no pending order book exists.
        return {"status": "ok", "cancelled_count": 0, "cancelled": [], "message": "No pending paper orders."}

    def last_fill_for_symbol(self, symbol: str) -> Fill | None:
        sym = str(symbol).strip()
        matches = [f for f in self._fills if str(f.symbol).strip() == sym]
        if not matches:
            return None
        return max(matches, key=lambda f: f.timestamp)

    def subscribe_to_websocket(self) -> None:
        # Paper mode has no external websocket stream.
        return
