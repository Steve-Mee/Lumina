from __future__ import annotations

import json
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.risk.cost_model import TradeExecutionCostModel

logger = logging.getLogger(__name__)

# One WARNING per account per process when REST returns no parsable balance/equity (avoid log spam).
_CROSS_TRADE_BALANCE_WARN_ACCOUNTS: set[str] = set()

_ACCOUNT_BALANCE_KEYS = (
    "balance",
    "cashBalance",
    "cash_balance",
    "availableBalance",
    "available_balance",
    "availableFunds",
    "netCash",
    "net_cash",
    "cashValue",
    "totalCashValue",
)
_ACCOUNT_EQUITY_KEYS = (
    "equity",
    "totalEquity",
    "total_equity",
    "netLiquidation",
    "net_liquidation",
    "accountEquity",
    "account_equity",
    "netLiquidationValue",
    "total_account_value",
)
_ACCOUNT_PNL_KEYS = (
    "realizedPnlToday",
    "realized_pnl_today",
    "realizedPnl",
    "dayPnl",
    "realizedDayPnl",
)
_ACCOUNT_AVAILABLE_MARGIN_KEYS = (
    "availableMargin",
    "available_margin",
    "availableFunds",
    "available_funds",
    "availableBalance",
    "available_balance",
    "buyingPower",
    "buying_power",
    "excessLiquidity",
    "excess_liquidity",
    "maintenanceExcess",
)


def _resolve_trade_mode(engine: object | None) -> str:
    mode = str(getattr(getattr(engine, "config", None), "trade_mode", "paper") or "paper").strip().lower()
    return mode or "paper"


def audit_final_arbitration_reject(
    engine: object | None,
    *,
    mode: str,
    reason: str,
    order: Order | None = None,
) -> None:
    context = {
        "mode": str(mode),
        "reason": str(reason),
        "symbol": str(getattr(order, "symbol", "") or ""),
        "side": str(getattr(order, "side", "") or ""),
        "quantity": int(getattr(order, "quantity", 0) or 0),
    }
    log_structured(
        LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="FINAL_ARBITRATION_GATE_REJECT",
            message=f"FinalArbitration rejected execution order: {reason}",
            context=context,
        )
    )
    service = getattr(engine, "audit_log_service", None) if engine is not None else None
    if service is None or not hasattr(service, "log_decision"):
        return
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision_id": f"final-arbitration-{uuid.uuid4().hex[:8]}",
        "stage": "final_arbitration",
        "mode": str(mode),
        "symbol": str(getattr(order, "symbol", "") or ""),
        "proposed_risk": float(
            getattr(getattr(order, "metadata", {}), "get", lambda *_: 0.0)("proposed_risk", 0.0) or 0.0
        ),
        "final_decision": "rejected",
        "reason": str(reason),
        "probability": 0.0,
        "expected_value": 0.0,
        "agents_involved": [{"agent_id": "final_arbitration_gate", "confidence": 1.0}],
        "var_impact": {},
        "monte_carlo": {},
    }
    try:
        service.log_decision(payload, is_real_mode=str(mode).lower() == "real")
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/broker_bridge.py:121")
        return


def _run_final_arbitration(engine: object | None, order: "Order") -> tuple[bool, str]:
    mode = _resolve_trade_mode(engine)
    if engine is None:
        reason = "admission_engine_required"
        audit_final_arbitration_reject(engine, mode=mode, reason=reason, order=order)
        return False, reason
    try:
        metadata = order.metadata if isinstance(order.metadata, dict) else {}
        if bool(metadata.get("skip_admission_chain_recheck", False)):
            # Defensive deprecation trap (post 1.3.4 zero-trace hygiene).
            # The skip_admission_chain_recheck key is a pre-1.3.3 legacy bypass remnant (B-004).
            # It has had no functional effect since 1.3.3. The authoritative gate always runs.
            # Any code still emitting this key must be located and cleaned.
            logger.error(
                "LEGACY_BYPASS_FLAG_DETECTED: skip_admission_chain_recheck=True was set. "
                "This flag has had no effect since Phase 1.3.3. Remove the source that still emits this metadata key."
            )
            # Always fall through — no short-circuit remains in any mode.
        reference_price = float(metadata.get("reference_price", 0.0) or 0.0)
        stop_loss = float(order.stop_loss or 0.0)
        fallback_risk = abs(reference_price - stop_loss) if reference_price > 0 and stop_loss > 0 else 0.0
        proposed_risk = float(metadata.get("proposed_risk", fallback_risk) or fallback_risk)
        allowed, reason = enforce_pre_trade_gate(
            engine,
            symbol=str(order.symbol),
            regime=str(metadata.get("regime", "NEUTRAL") or "NEUTRAL"),
            proposed_risk=float(proposed_risk),
            order_side=str(order.side).upper(),
        )
        if not allowed:
            audit_final_arbitration_reject(engine, mode=mode, reason=str(reason), order=order)
        return bool(allowed), str(reason)
    except Exception as exc:
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/broker_bridge.py:153")
        reason = f"admission_chain_error:{exc}"
        audit_final_arbitration_reject(engine, mode=mode, reason=reason, order=order)
        return False, reason


@dataclass(slots=True)
class Order:
    symbol: str
    side: str
    quantity: int
    order_type: str = "MARKET"
    stop_loss: float = 0.0
    take_profit: float = 0.0
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class OrderResult:
    accepted: bool
    order_id: str
    status: str
    filled_qty: int = 0
    fill_price: float = 0.0
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    # Phase 2 live broker lineage (mirror Fill post-Slice 19; first-class for get_lineage_from_order_result + typed events)
    decision_context_id: str | None = None
    prev_hash: str | None = None
    prev_event_topic: str | None = None


@dataclass(slots=True)
class AccountInfo:
    balance: float
    equity: float
    available_margin: float | None = None
    realized_pnl_today: float = 0.0
    currency: str = "USD"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: int
    avg_price: float
    side: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Fill:
    fill_id: str
    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: str
    commission: float = 0.0

    # Phase 2 Slice 19: First-class lineage fields (promoted from raw)
    decision_context_id: str | None = None
    prev_hash: str | None = None
    prev_event_topic: str | None = None

    raw: dict[str, Any] = field(default_factory=dict)


def paper_position_from_fills(fills: list[Fill], symbol: str) -> Position | None:
    """Net position for ``symbol`` from chronological broker-confirmed fills (paper ledger)."""
    sym = str(symbol).strip()
    rows = [f for f in fills if str(f.symbol).strip() == sym]
    if not rows:
        return None
    rows_sorted = sorted(rows, key=lambda f: f.timestamp)
    net = 0
    avg = 0.0
    for f in rows_sorted:
        q = max(0, int(f.quantity))
        p = float(f.price)
        d = q if str(f.side).upper() == "BUY" else -q
        if net == 0:
            net = d
            avg = p if d != 0 else 0.0
            continue
        new_net = net + d
        if net * d > 0:
            abs_new = abs(new_net)
            avg = (abs(net) * avg + abs(d) * p) / max(abs_new, 1e-9)
            net = new_net
            continue
        if net * new_net > 0:
            net = new_net
            continue
        if new_net == 0:
            net = 0
            avg = 0.0
            continue
        net = new_net
        avg = p
    if net == 0:
        return None
    side = "BUY" if net > 0 else "SELL"
    return Position(symbol=sym, quantity=int(net), avg_price=float(avg), side=side, raw={})


class BrokerBridge(ABC):
    @abstractmethod
    def connect(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def submit_order(self, order: Order) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[Position]:
        raise NotImplementedError

    @abstractmethod
    def get_fills(self) -> list[Fill]:
        raise NotImplementedError

    @abstractmethod
    def cancel_all_orders(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def subscribe_to_websocket(self) -> None:
        raise NotImplementedError


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
        allowed, reason = _run_final_arbitration(self.engine, order)
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
                per_side_slip_ticks + random.gauss(0.0, float(model.slippage_sigma)),
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

    @staticmethod
    def _pick_float(payload: dict[str, Any], keys: tuple[str, ...]) -> float:
        for key in keys:
            if key not in payload:
                continue
            val = payload.get(key)
            if val is None:
                continue
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
        return 0.0

    @staticmethod
    def _account_payload_layers(root: dict[str, Any]) -> list[dict[str, Any]]:
        """Crosstrade often wraps balances inside ``item`` / ``data`` / list entries."""
        layers: list[dict[str, Any]] = []
        seen: set[int] = set()

        def add(d: dict[str, Any]) -> None:
            i = id(d)
            if i in seen:
                return
            seen.add(i)
            layers.append(d)

        add(root)
        for key in ("item", "data", "account", "result", "payload", "summary", "details"):
            node = root.get(key)
            if isinstance(node, dict):
                add(node)
            elif isinstance(node, list):
                for el in node[:8]:
                    if isinstance(el, dict):
                        add(el)
        return layers

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

        allowed, reason = _run_final_arbitration(self.engine, order)
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

            layers = self._account_payload_layers(data)
            balance = 0.0
            equity = 0.0
            pnl = 0.0
            available_margin: float | None = None
            for layer in layers:
                if balance == 0.0:
                    balance = self._pick_float(layer, _ACCOUNT_BALANCE_KEYS)
                if equity == 0.0:
                    equity = self._pick_float(layer, _ACCOUNT_EQUITY_KEYS)
                if pnl == 0.0:
                    pnl = self._pick_float(layer, _ACCOUNT_PNL_KEYS)
                if available_margin is None:
                    parsed_margin = self._pick_float(layer, _ACCOUNT_AVAILABLE_MARGIN_KEYS)
                    if parsed_margin > 0.0:
                        available_margin = parsed_margin
            if equity == 0.0 and balance > 0.0:
                equity = balance

            if balance == 0.0 and equity == 0.0 and self.logger is not None:
                aid = str(self.account)
                if aid not in _CROSS_TRADE_BALANCE_WARN_ACCOUNTS:
                    _CROSS_TRADE_BALANCE_WARN_ACCOUNTS.add(aid)
                    item_preview = ""
                    raw_item = data.get("item")
                    if isinstance(raw_item, dict):
                        item_preview = str(sorted(raw_item.keys()))[:200]
                    elif raw_item is not None:
                        item_preview = str(raw_item)[:220]
                    self.logger.warning(
                        "CrossTrade account REST has no parsable balance/equity for account=%s "
                        "(parsed nested layers: item/data/account/…). top_keys=%s item_keys_or_preview=%s "
                        "Set CROSSTRADE_ACCOUNT to the ID Crosstrade shows for your NinjaTrader demo. "
                        "If this endpoint only returns metadata, balances may live on another route in your tenant.",
                        aid,
                        sorted(data.keys())[:28],
                        item_preview or "<none>",
                    )

            return AccountInfo(
                balance=balance,
                equity=equity,
                available_margin=available_margin,
                realized_pnl_today=pnl,
                raw=data,
            )
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


def broker_factory(
    config: Any | None = None, engine: Any | None = None, logger: logging.Logger | None = None
) -> BrokerBridge:
    backend = "paper"
    if config is not None:
        backend = str(getattr(config, "broker_backend", "paper") or "paper").strip().lower()
        if backend not in {"paper", "live"}:
            backend = "paper"

    if backend == "live":
        trade_mode = str(getattr(config, "trade_mode", "paper") or "paper").strip().lower()
        if trade_mode == "paper":
            raise ValueError(
                "broker_backend=live is incompatible with trade_mode=paper (set broker_backend=paper for paper mode)"
            )
        if trade_mode not in {"sim", "sim_real_guard", "real"}:
            raise ValueError(f"broker_backend=live requires trade_mode in sim/sim_real_guard/real, got {trade_mode!r}")
        api_key = str(
            getattr(config, "broker_crosstrade_api_key", None) or getattr(config, "crosstrade_token", "") or ""
        ).strip()
        account = str(getattr(config, "crosstrade_account", "DEMO5042070")).strip()
        websocket_url = str(
            getattr(config, "broker_crosstrade_websocket_url", None)
            or getattr(config, "crosstrade_fill_ws_url", "wss://app.crosstrade.io/ws/stream")
        ).strip()
        base_url = str(getattr(config, "broker_crosstrade_base_url", "https://app.crosstrade.io")).strip()
        fill_poll_url = str(getattr(config, "crosstrade_fill_poll_url", "")).strip()
        return CrossTradeBroker(
            api_key=api_key,
            account=account,
            websocket_url=websocket_url,
            base_url=base_url,
            fill_poll_url=fill_poll_url,
            logger=logger,
            engine=engine,
        )

    return PaperBroker(engine=engine, logger=logger)
