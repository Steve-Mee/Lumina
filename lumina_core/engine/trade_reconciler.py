from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import websockets

from .lumina_engine import LuminaEngine


@dataclass(slots=True)
class FillEvent:
    fill_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    commission: float
    event_ts: datetime
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PendingTradeClose:
    reconciliation_id: str
    symbol: str
    mode: str
    signal: str
    quantity: int
    entry_price: float
    detected_exit_price: float
    expected_pnl: float
    detected_ts: datetime
    status: str = "closing"
    reflection: dict[str, Any] = field(default_factory=dict)
    chart_base64: str | None = None
    expected_close_side: str = "SELL"
    fill_parts: list[dict[str, Any]] = field(default_factory=list)
    matched_qty: int = 0
    weighted_exit_notional: float = 0.0
    commission_total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["detected_ts"] = self.detected_ts.isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PendingTradeClose":
        data = dict(payload)
        detected_ts_raw = data.get("detected_ts")
        if isinstance(detected_ts_raw, str):
            data["detected_ts"] = datetime.fromisoformat(detected_ts_raw)
        return cls(**data)


@dataclass(slots=True)
class TradeReconciler:
    """Reconciles broker fill events against locally detected close snapshots."""

    engine: LuminaEngine
    stop_requested: bool = False
    _recent_fills: deque[FillEvent] = field(default_factory=lambda: deque(maxlen=100))
    _backoff_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("TradeReconciler requires a LuminaEngine")
        pending = []
        for item in getattr(self.engine, "pending_trade_reconciliations", []):
            if isinstance(item, dict):
                try:
                    pending.append(PendingTradeClose.from_dict(item))
                except Exception:
                    continue
        self._set_pending_closes(pending)
        self._update_status(connection_state="idle", status="ready")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def _get_pending_closes(self) -> list[PendingTradeClose]:
        return [PendingTradeClose.from_dict(item) for item in getattr(self.engine, "pending_trade_reconciliations", []) if isinstance(item, dict)]

    def _set_pending_closes(self, items: list[PendingTradeClose]) -> None:
        self.engine.pending_trade_reconciliations = [item.to_dict() for item in items]

    def stop(self) -> None:
        self.stop_requested = True
        self._update_status(connection_state="stopped", status="stopped")

    def start(self) -> None:
        if self.engine.config.trade_mode != "real":
            self._update_status(connection_state="disabled", status="skipped_non_real")
            return
        if not bool(self.engine.config.reconcile_fills):
            self._update_status(connection_state="disabled", status="disabled")
            return

        method = str(self.engine.config.reconciliation_method or "websocket").lower()
        if method == "polling":
            self._run_polling_loop()
            return
        self._run_websocket_loop()

    def mark_closing(
        self,
        *,
        symbol: str,
        signal: str,
        entry_price: float,
        detected_exit_price: float,
        quantity: int,
        expected_pnl: float,
        reflection: dict[str, Any] | None = None,
        chart_base64: str | None = None,
        detected_ts: datetime | None = None,
    ) -> str:
        detected_at = detected_ts or datetime.now(timezone.utc)
        expected_close_side = "SELL" if str(signal).upper() == "BUY" else "BUY"
        reconciliation_id = f"{symbol}-{int(detected_at.timestamp() * 1000)}-{abs(int(quantity))}"
        pending = PendingTradeClose(
            reconciliation_id=reconciliation_id,
            symbol=str(symbol).strip().upper(),
            mode=self.engine.config.trade_mode,
            signal=str(signal).upper(),
            quantity=int(abs(quantity)),
            entry_price=float(entry_price),
            detected_exit_price=float(detected_exit_price),
            expected_pnl=float(expected_pnl),
            detected_ts=detected_at,
            reflection=dict(reflection or {}),
            chart_base64=chart_base64,
            expected_close_side=expected_close_side,
        )
        items = [item for item in self._get_pending_closes() if item.symbol != pending.symbol or item.status != "closing"]
        items.append(pending)
        self._set_pending_closes(items)
        app = self._app()
        app.logger.info(
            "FILL_RECONCILE_PENDING,"
            f"id={reconciliation_id},symbol={pending.symbol},qty={pending.quantity},"
            f"snapshot_exit={pending.detected_exit_price:.2f},expected_pnl={pending.expected_pnl:.2f}"
        )
        self._append_audit_event(
            {
                "event": "pending_close",
                "reconciliation_id": reconciliation_id,
                "symbol": pending.symbol,
                "signal": pending.signal,
                "qty": pending.quantity,
                "entry_price": pending.entry_price,
                "detected_exit_price": pending.detected_exit_price,
                "expected_pnl": pending.expected_pnl,
                "detected_ts": pending.detected_ts.isoformat(),
            }
        )
        self._update_status(status="pending_close")
        self._try_match_recent_fills()
        return reconciliation_id

    def ingest_fill_event(self, payload: dict[str, Any]) -> bool:
        fill = self._normalize_fill_event(payload)
        if fill is None:
            return False
        self._recent_fills.append(fill)
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

    def _run_websocket_loop(self) -> None:
        app = self._app()
        while not self.stop_requested:
            try:
                self._update_status(connection_state="connecting", status="connecting")
                asyncio.run(self._websocket_listener())
                self._backoff_seconds = 1.0
            except Exception as exc:
                app.logger.error(f"TradeReconciler websocket error: {exc}")
                self._update_status(connection_state="error", status="reconnecting", last_error=str(exc))
                sleep_for = min(self._backoff_seconds, 30.0)
                app.logger.warning(f"TradeReconciler reconnect in {sleep_for:.1f}s")
                time.sleep(sleep_for)
                self._backoff_seconds = min(self._backoff_seconds * 2.0, 30.0)
            self._flush_timeouts()

    async def _websocket_listener(self) -> None:
        app = self._app()
        uri = self.engine.config.crosstrade_fill_ws_url
        headers = {"Authorization": f"Bearer {self.engine.config.crosstrade_token or ''}"}
        heartbeat_seconds = 20.0
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
                data = json.loads(message)
                self.ingest_fill_event(data)
                self._flush_timeouts()

    def _run_polling_loop(self) -> None:
        app = self._app()
        url = str(self.engine.config.crosstrade_fill_poll_url or "").strip()
        if not url:
            app.logger.warning("TradeReconciler polling enabled without CROSSTRADE_FILL_POLL_URL; timeout fallback only")
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
                    app.logger.error(f"TradeReconciler polling error: {exc}")
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
            } if normalized is not None else None,
        }
        self._update_status(status="self_test", last_self_test=result)
        return result

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
                self._finalize_pending_close(pending, fill=None, status="timeout_snapshot")
            else:
                kept.append(pending)
        self._set_pending_closes(kept)

    def _try_match_recent_fills(self) -> None:
        items = self._get_pending_closes()
        unresolved: list[PendingTradeClose] = []
        matched_ids: set[str] = set()
        for pending in items:
            fill = self._find_matching_fill(pending)
            if fill is None:
                unresolved.append(pending)
                continue
            self._finalize_pending_close(pending, fill=fill, status="reconciled_fill")
            matched_ids.add(fill.fill_id)
        if matched_ids:
            self._recent_fills = deque([fill for fill in self._recent_fills if fill.fill_id not in matched_ids], maxlen=100)
        self._set_pending_closes(unresolved)

    def _find_matching_fill(self, pending: PendingTradeClose) -> FillEvent | None:
        timeout_seconds = self._timeout_seconds()
        for fill in reversed(self._recent_fills):
            age = abs((fill.event_ts - pending.detected_ts).total_seconds())
            if age > timeout_seconds:
                continue
            if fill.symbol != pending.symbol:
                continue
            if fill.side and fill.side != pending.expected_close_side:
                continue
            if fill.quantity and pending.quantity and fill.quantity != pending.quantity:
                continue
            return fill
        return None

    def _finalize_pending_close(self, pending: PendingTradeClose, fill: FillEvent | None, status: str) -> None:
        app = self._app()
        use_real_fill = bool(self.engine.config.use_real_fill_for_pnl)
        final_exit = float(fill.price) if fill is not None and use_real_fill else float(pending.detected_exit_price)
        quantity = int(fill.quantity) if fill is not None and fill.quantity else int(pending.quantity)
        commission = float(fill.commission) if fill is not None else 0.0
        if use_real_fill:
            signed_qty = quantity if pending.signal == "BUY" else -quantity
            final_pnl = (final_exit - float(pending.entry_price)) * signed_qty * 5.0 - commission
        else:
            final_pnl = float(pending.expected_pnl)
        slippage_points = float(final_exit - pending.detected_exit_price)
        fill_latency_ms = max(0.0, (datetime.now(timezone.utc) - pending.detected_ts).total_seconds() * 1000.0)

        reconciliation_meta = {
            "status": status,
            "broker_fill_id": fill.fill_id if fill is not None else pending.reconciliation_id,
            "commission": round(commission, 4),
            "slippage_points": round(slippage_points, 4),
            "fill_latency_ms": round(fill_latency_ms, 2),
            "use_real_fill_for_pnl": use_real_fill,
            "detected_exit_price": round(float(pending.detected_exit_price), 4),
            "final_exit_price": round(float(final_exit), 4),
        }
        reflection_payload = dict(pending.reflection)
        reflection_payload["reconciliation"] = reconciliation_meta

        push_fn = getattr(app, "push_traderleague_trade", None)
        if callable(push_fn):
            push_fn(
                mode=pending.mode,
                symbol=pending.symbol,
                signal=pending.signal,
                entry_price=float(pending.entry_price),
                exit_price=float(final_exit),
                qty=int(quantity),
                pnl_dollars=float(final_pnl),
                reflection=reflection_payload,
                chart_base64=pending.chart_base64,
                broker_fill_id=reconciliation_meta["broker_fill_id"],
                commission=float(commission),
                slippage_points=float(slippage_points),
                fill_latency_ms=float(fill_latency_ms),
                reconciliation_status=status,
            )

        publish_fn = getattr(app, "publish_traderleague_trade_close", None)
        if callable(publish_fn):
            try:
                summary = (
                    f"reconciliation={status}; slippage_points={slippage_points:.4f}; "
                    f"fill_latency_ms={fill_latency_ms:.0f}; commission={commission:.2f}"
                )
                publish_fn(
                    symbol=pending.symbol,
                    entry_price=float(pending.entry_price),
                    exit_price=float(final_exit),
                    quantity=int(quantity),
                    pnl=float(final_pnl),
                    reflection=summary,
                    chart_snapshot_url=str(pending.reflection.get("chart_snapshot_url", "") or ""),
                )
            except Exception as exc:
                app.logger.error(f"TradeReconciler final publish error: {exc}")

        app.logger.info(
            "FILL_RECONCILED,"
            f"id={pending.reconciliation_id},symbol={pending.symbol},status={status},"
            f"exit={final_exit:.2f},snapshot_exit={pending.detected_exit_price:.2f},"
            f"slippage={slippage_points:.4f},commission={commission:.2f},latency_ms={fill_latency_ms:.0f},"
            f"pnl={final_pnl:.2f}"
        )
        log_thought = getattr(app, "log_thought", None)
        if callable(log_thought):
            log_thought(
                {
                    "type": "trade_fill_reconciled",
                    "symbol": pending.symbol,
                    "status": status,
                    "entry_price": float(pending.entry_price),
                    "detected_exit_price": float(pending.detected_exit_price),
                    "final_exit_price": float(final_exit),
                    "pnl": float(final_pnl),
                    "commission": float(commission),
                    "slippage_points": float(slippage_points),
                    "fill_latency_ms": float(fill_latency_ms),
                }
            )
        self._update_status(
            status="reconciled",
            last_reconciled_trade={
                "symbol": pending.symbol,
                "status": status,
                "broker_fill_id": reconciliation_meta["broker_fill_id"],
                "final_exit_price": float(final_exit),
                "pnl": float(final_pnl),
            },
        )
        self._append_audit_event(
            {
                "event": "reconciled",
                "reconciliation_id": pending.reconciliation_id,
                "symbol": pending.symbol,
                "status": status,
                "broker_fill_id": reconciliation_meta["broker_fill_id"],
                "entry_price": float(pending.entry_price),
                "detected_exit_price": float(pending.detected_exit_price),
                "final_exit_price": float(final_exit),
                "quantity": int(quantity),
                "pnl": float(final_pnl),
                "commission": float(commission),
                "slippage_points": float(slippage_points),
                "fill_latency_ms": float(fill_latency_ms),
            }
        )

    def _append_audit_event(self, payload: dict[str, Any]) -> None:
        audit_path = Path(self.engine.config.trade_reconciler_audit_log)
        event = dict(payload)
        event["ts"] = datetime.now(timezone.utc).isoformat()
        try:
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            with audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _update_status(self, **updates: Any) -> None:
        status = dict(getattr(self.engine, "trade_reconciler_status", {}) or {})
        status.setdefault("method", self.engine.config.reconciliation_method)
        status.setdefault("connection_state", "idle")
        status.setdefault("status", "ready")
        status.setdefault("last_error", None)
        status.setdefault("last_message_ts", None)
        status.setdefault("pending_count", 0)
        status.setdefault("pending_symbols", [])
        status.update({key: value for key, value in updates.items() if value is not None or key == "last_error"})
        pending = self._get_pending_closes()
        status["pending_count"] = len(pending)
        status["pending_symbols"] = sorted({item.symbol for item in pending})
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.engine.trade_reconciler_status = status

        status_path = Path(self.engine.config.trade_reconciler_status_file)
        try:
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
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

        return FillEvent(
            fill_id=fill_id,
            symbol=symbol,
            side=side_raw,
            quantity=quantity,
            price=price,
            commission=commission,
            event_ts=event_ts,
            raw_payload=raw,
        )
