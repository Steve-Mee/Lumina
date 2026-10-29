"""S2 fill SSOT: FillEvent fans out to monitor observe and live calibrator JSONL.

Unmapped fills update desk-level calibration only. Hypothetical fills never
write the live calibrator. KEEP calls observe; this module does not import
the NT broker and cannot place an order.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research_execution import (
    FILL_TRANSLATOR_AGENT_ID,
    RESEARCH_EXECUTION_FILL_TOPIC,
    ResearchExecutionFill,
    guard_research_execution_fill,
)
from lumina_core.agent_orchestration.schemas_trading import ExecutionFill
from lumina_core.engine.trade_reconciler.schemas import FillEvent
from lumina_core.logging_utils import get_logger
from lumina_core.research_bridge.calibrator_rows import (
    BROKER_SOURCE,
    HYPOTHETICAL_SOURCE,
    CalibratorRowRefused,
    live_calibrator_row,
    normalize_fill_source,
)
from lumina_core.research_bridge.fill_index import FillIndex, FillIndexEntry
from lumina_core.research_bridge.fill_stamp import FillStampRefused, execution_commission, stamp_slippage
from lumina_core.research_bridge.jsonl import append_shadow_record

logger = get_logger("lumina.research_bridge.fill_translator")


class ObserveSink(Protocol):
    def observe(self, signal_id: str, metric: object) -> object: ...


class TranslateRefused(ValueError):
    """Fill cannot enter the SSOT without inventing commission, horizon, or a signal id."""


@dataclass(frozen=True, slots=True)
class TranslateResult:
    fill: FillEvent
    observed: bool
    calibrated: bool
    published: bool
    refuse_reason: str


class FillTranslator:
    """Single fan-out API. Writing JSONL by hand is not sufficient for observe()."""

    def __init__(
        self,
        *,
        index: FillIndex | None = None,
        observe_sink: ObserveSink | None = None,
        calibrator_jsonl: Path | None = None,
        refuse_jsonl: Path | None = None,
        bus: EventBus | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._index = index if index is not None else FillIndex()
        self._observe = observe_sink
        self._calibrator_jsonl = calibrator_jsonl
        self._refuse_jsonl = refuse_jsonl
        self._bus = bus
        self._clock = clock if clock is not None else (lambda: datetime.now(timezone.utc))
        self._observed: list[tuple[str, float]] = []
        self._calibrator_rows: list[dict[str, Any]] = []
        self._broker_submits = 0
        if bus is not None:
            bus.register_topic_guard(RESEARCH_EXECUTION_FILL_TOPIC, guard_research_execution_fill)

    def index(self) -> FillIndex:
        return self._index

    def observed_metrics(self) -> tuple[tuple[str, float], ...]:
        return tuple(self._observed)

    def calibrator_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._calibrator_rows)

    def assert_no_broker_submit(self) -> None:
        if self._broker_submits != 0:
            raise AssertionError("fill_translator recorded a broker submit")

    def ingest(
        self,
        payload: FillEvent | ExecutionFill | dict[str, Any],
        *,
        client_order_id: str = "",
        reference_price: float | None = None,
    ) -> TranslateResult:
        fill = self._coerce(payload, reference_price=reference_price)
        mapped = self._mapped_entry(fill, client_order_id=client_order_id)
        if mapped is not None:
            fill.strategy_id = mapped.strategy_id
            fill.expected_horizon = mapped.expected_horizon
        observed = self._maybe_observe(fill, mapped)
        calibrated = self._maybe_calibrate(fill)
        published = self._maybe_publish(fill, mapped)
        self.assert_no_broker_submit()
        return TranslateResult(
            fill=fill,
            observed=observed,
            calibrated=calibrated,
            published=published,
            refuse_reason="",
        )

    def _coerce(
        self,
        payload: FillEvent | ExecutionFill | dict[str, Any],
        *,
        reference_price: float | None,
    ) -> FillEvent:
        if isinstance(payload, FillEvent):
            fill = payload
        elif isinstance(payload, ExecutionFill):
            fill = _from_execution_fill(payload)
        elif isinstance(payload, dict):
            fill = _from_row(payload, clock=self._clock)
        else:
            raise TranslateRefused("unsupported_fill_payload")
        return self._stamp_execution_side(fill, reference_price=reference_price)

    def _stamp_execution_side(self, fill: FillEvent, *, reference_price: float | None) -> FillEvent:
        try:
            source = normalize_fill_source(fill.source)
        except CalibratorRowRefused as exc:
            self._refuse("unknown_fill_source", {"error": str(exc), "fill_id": fill.fill_id})
            raise TranslateRefused(str(exc)) from exc
        fill.source = source
        qty = int(fill.quantity)
        try:
            card_usd, card_ticks, discrepancy = execution_commission(fill.symbol, qty, fill.commission)
        except FillStampRefused as exc:
            self._refuse("fill_stamp_refused", {"error": str(exc), "fill_id": fill.fill_id})
            raise TranslateRefused(str(exc)) from exc
        if discrepancy:
            logger.warning(
                "cost_discrepancy",
                extra={
                    "event_data": {
                        "event": "cost_discrepancy",
                        "fill_id": fill.fill_id,
                        "claimed_commission": float(fill.commission),
                        "execution_commission_usd": card_usd,
                        "winner": "execution_side",
                    }
                },
            )
        fill.commission = card_usd
        fill.commission_ticks = card_ticks
        if reference_price is not None:
            try:
                slip = stamp_slippage(
                    symbol=fill.symbol,
                    side=fill.side,
                    fill_price=float(fill.price),
                    reference_price=reference_price,
                    qty=qty,
                )
            except FillStampRefused as exc:
                self._refuse("slippage_refused", {"error": str(exc), "fill_id": fill.fill_id})
                raise TranslateRefused(str(exc)) from exc
            if slip is not None:
                fill.slippage_ticks = float(slip[0])
                fill.slippage_usd = float(slip[1])
        return fill

    def _mapped_entry(self, fill: FillEvent, *, client_order_id: str) -> FillIndexEntry | None:
        if str(fill.strategy_id or "").strip() and int(fill.expected_horizon) >= 1:
            return FillIndexEntry(
                strategy_id=str(fill.strategy_id),
                expected_horizon=int(fill.expected_horizon),
            )
        cid = str(client_order_id or "").strip() or _client_order_id(fill)
        return self._index.lookup(cid)

    def _maybe_observe(self, fill: FillEvent, mapped: FillIndexEntry | None) -> bool:
        if mapped is None:
            return False
        if self._observe is None:
            return False
        metric = observe_metric(fill)
        try:
            self._observe.observe(mapped.strategy_id, metric)
        except Exception as exc:
            self._refuse(
                "observe_failed",
                {"strategy_id": mapped.strategy_id, "error": str(exc), "fill_id": fill.fill_id},
            )
            return False
        self._observed.append((mapped.strategy_id, metric))
        return True

    def _maybe_calibrate(self, fill: FillEvent) -> bool:
        if normalize_fill_source(fill.source) == HYPOTHETICAL_SOURCE:
            return False
        try:
            row = live_calibrator_row(fill)
        except Exception as exc:
            self._refuse("calibrator_row_refused", {"error": str(exc), "fill_id": fill.fill_id})
            return False
        if row is None:
            return False
        self._calibrator_rows.append(row)
        if self._calibrator_jsonl is not None:
            append_shadow_record(self._calibrator_jsonl, row)
        return True

    def _maybe_publish(self, fill: FillEvent, mapped: FillIndexEntry | None) -> bool:
        if self._bus is None or mapped is None:
            return False
        if mapped.expected_horizon < 1:
            self._refuse("expected_horizon_missing", {"strategy_id": mapped.strategy_id})
            return False
        side = str(fill.side).strip().upper()
        if side not in {"BUY", "SELL"}:
            self._refuse("side_invalid", {"side": side, "fill_id": fill.fill_id})
            return False
        direction: Literal["BUY", "SELL"] = "BUY" if side == "BUY" else "SELL"
        payload = ResearchExecutionFill(
            fill_id=str(fill.fill_id),
            symbol=str(fill.symbol),
            side=direction,
            quantity=int(fill.quantity),
            price=float(fill.price),
            commission=float(fill.commission),
            event_ts=fill.event_ts if fill.event_ts.tzinfo else fill.event_ts.replace(tzinfo=timezone.utc),
            slippage_ticks=float(fill.slippage_ticks),
            slippage_usd=float(fill.slippage_usd),
            commission_ticks=float(fill.commission_ticks),
            source=BROKER_SOURCE if fill.source == BROKER_SOURCE else HYPOTHETICAL_SOURCE,
            strategy_id=mapped.strategy_id,
            expected_horizon=mapped.expected_horizon,
        )
        self._bus.publish(
            topic=RESEARCH_EXECUTION_FILL_TOPIC,
            producer=FILL_TRANSLATOR_AGENT_ID,
            payload=payload.model_dump(mode="json"),
        )
        return True

    def _refuse(self, code: str, details: dict[str, object]) -> None:
        logger.error(
            "fill_translator.refused",
            extra={"event_data": {"event": "fill_translator.refused", "code": code, **details}},
        )
        if self._refuse_jsonl is not None:
            append_shadow_record(
                self._refuse_jsonl,
                {"event": "refused", "code": code, **details},
            )


def observe_metric(fill: FillEvent) -> float:
    value = -(float(fill.commission) + float(fill.slippage_usd))
    if not math.isfinite(value):
        raise TranslateRefused("observe_metric_non_finite")
    return float(value)


def _client_order_id(fill: FillEvent) -> str:
    raw = fill.raw_payload if isinstance(fill.raw_payload, dict) else {}
    for key in ("client_order_id", "clientOrderId"):
        text = str(raw.get(key) or "").strip()
        if text:
            return text
    return str(fill.fill_id or "").strip()


def _from_execution_fill(payload: ExecutionFill) -> FillEvent:
    ts = _parse_ts(str(payload.timestamp))
    raw = dict(payload.raw) if isinstance(payload.raw, dict) else {}
    return FillEvent(
        fill_id=str(payload.fill_id),
        symbol=str(payload.symbol),
        side=str(payload.side),
        quantity=int(payload.quantity),
        price=float(payload.price),
        commission=float(payload.commission),
        event_ts=ts,
        raw_payload=raw,
        decision_context_id=payload.decision_context_id,
        prev_hash=payload.prev_hash,
        prev_event_topic=payload.prev_event_topic,
        slippage_ticks=float(getattr(payload, "slippage", 0.0) or 0.0),
        commission_ticks=float(getattr(payload, "commission_ticks", 0.0) or 0.0),
        source=str(raw.get("source") or BROKER_SOURCE),
        strategy_id=str(raw.get("strategy_id") or ""),
    )


def _from_row(payload: dict[str, Any], *, clock: Callable[[], datetime]) -> FillEvent:
    qty_raw = payload.get("qty", payload.get("quantity", 0))
    price_raw = payload.get("fill_price", payload.get("price", None))
    if price_raw is None:
        raise TranslateRefused("fill_price_missing")
    ts_raw = payload.get("ts") or payload.get("event_ts") or payload.get("timestamp")
    ts = _parse_ts(str(ts_raw)) if ts_raw is not None else clock()
    try:
        quantity = int(qty_raw)
        price = float(price_raw)
        commission = float(payload.get("commission", 0.0) or 0.0)
    except (TypeError, ValueError) as exc:
        raise TranslateRefused("row_numeric_invalid") from exc
    if quantity < 1:
        raise TranslateRefused("qty_invalid")
    return FillEvent(
        fill_id=str(payload.get("fill_id") or payload.get("broker_fill_id") or "row-fill"),
        symbol=str(payload.get("symbol") or payload.get("instrument") or ""),
        side=str(payload.get("side") or ""),
        quantity=quantity,
        price=price,
        commission=commission,
        event_ts=ts,
        raw_payload=dict(payload),
        slippage_ticks=float(payload.get("slippage_ticks") or 0.0),
        slippage_usd=float(payload.get("slippage_usd") or 0.0),
        commission_ticks=float(payload.get("commission_ticks") or 0.0),
        source=str(payload.get("source") or BROKER_SOURCE),
        strategy_id=str(payload.get("strategy_id") or ""),
        expected_horizon=int(payload.get("expected_horizon") or 0),
    )


def _parse_ts(raw: str) -> datetime:
    text = str(raw).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TranslateRefused("timestamp_invalid") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
