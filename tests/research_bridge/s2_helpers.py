"""Shared S2 FillEvent fixtures. No broker I/O."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.trade_reconciler.schemas import FillEvent
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.fill_translator import FillTranslator
from tests.research_bridge.helpers import RecordingObserveSink


def utc() -> datetime:
    return datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def broker_fill(
    *,
    symbol: str = "MES",
    side: str = "BUY",
    quantity: int = 1,
    price: float = 5000.25,
    commission: float = 0.0,
    fill_id: str = "fill-mes-1",
    source: str = "broker",
    strategy_id: str = "",
    expected_horizon: int = 0,
    client_order_id: str = "cid-1",
    slippage_ticks: float = 0.0,
    slippage_usd: float = 0.0,
) -> FillEvent:
    return FillEvent(
        fill_id=fill_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        commission=commission,
        event_ts=utc(),
        raw_payload={"client_order_id": client_order_id, "source": source},
        slippage_ticks=slippage_ticks,
        slippage_usd=slippage_usd,
        source=source,
        strategy_id=strategy_id,
        expected_horizon=expected_horizon,
    )


def make_translator(
    tmp_path: Path,
    *,
    with_bus: bool = True,
    remember: tuple[str, str, int] | None = ("cid-1", "hyp-s2", 8),
) -> tuple[FillTranslator, RecordingObserveSink, FillIndex, EventBus | None]:
    observe = RecordingObserveSink()
    index = FillIndex()
    if remember is not None:
        index.remember(remember[0], remember[1], remember[2])
    bus = EventBus() if with_bus else None
    translator = FillTranslator(
        index=index,
        observe_sink=observe,
        calibrator_jsonl=tmp_path / "live_calibrator.jsonl",
        refuse_jsonl=tmp_path / "s2_refuse.jsonl",
        bus=bus,
        clock=utc,
    )
    return translator, observe, index, bus
