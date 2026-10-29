"""Conservative research execution: trade-through entries, stop/target exits.

Gross on an exit bar is booked at the stop or target price (or the open on a
gap-through). Stops fill on touch (assume stopped). Targets require trade-through
(do not book a win on a mere touch). Session-end flatten and a time-stop close
at the bar close.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.fills import trade_through_fill
from lumina_research.cycles.geometry import Geometry
from lumina_research.validation.contracts import spec_for
from lumina_research.validation.cost_model import MarketSnapshot

EQUITY = 100_000.0
ADV_WINDOW = 21


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    side: float
    entry_price: float
    exit_price: float
    pnl_ticks: float
    reason: str


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    gross: tuple[float, ...]
    positions: tuple[float, ...]
    markets: tuple[MarketSnapshot, ...]
    trades: tuple[ClosedTrade, ...]


class ExecutionRefused(ValueError):
    """Execution book refused a non-aligned tape."""


def causal_adv(bars: Sequence[ResearchBar], index: int) -> float:
    window = bars[max(0, index - (ADV_WINDOW - 1)) : index + 1]
    total = sum(max(item.volume, 1.0) for item in window)
    return total / float(len(window))


def bar_volatility_price(bar: ResearchBar) -> float:
    """True range of this bar. Never a fixed 2.0 index-point constant."""
    return max(float(bar.high) - float(bar.low), 0.0)


def run_execution(
    *,
    bars: Sequence[ResearchBar],
    signals: Sequence[float],
    geometry: Geometry,
    breaks: Sequence[bool],
    rth: Sequence[bool],
    session_dates: Sequence[date],
    session_filter: str = "rth",
    time_stop_bars: int = 16,
    session_end_flatten: bool = True,
    equity: float = EQUITY,
) -> ExecutionResult:
    n = len(bars)
    if n < 1 or n != len(signals) or n != len(breaks) or n != len(rth) or n != len(session_dates):
        raise ExecutionRefused("execution series must align")
    if time_stop_bars < 1:
        raise ExecutionRefused("time_stop_bars must be >= 1")
    allow = _allow_entry(rth, session_filter)
    session_end = _session_end_flags(session_dates, allow, session_end_flatten)
    spec = spec_for(geometry.root)
    book = _Book(geometry=geometry, time_stop_bars=time_stop_bars)
    gross: list[float] = []
    positions: list[float] = []
    markets: list[MarketSnapshot] = []
    trades: list[ClosedTrade] = []
    prev_close = bars[0].close
    for index, bar in enumerate(bars):
        adv = causal_adv(bars, index)
        markets.append(
            MarketSnapshot(
                volume=max(bar.volume, 1.0),
                average_volume=adv,
                volatility_price=bar_volatility_price(bar),
            )
        )
        if breaks[index]:
            book.clear_position()
            gross.append(0.0)
            positions.append(0.0)
            prev_close = bar.close
            continue
        pnl, pos, closed = book.step(
            bar=bar,
            prev_close=prev_close,
            adv=adv,
            signal=float(signals[index]),
            allow_entry=allow[index],
            session_end=session_end[index],
            multiplier=spec.multiplier,
            equity=equity,
        )
        gross.append(pnl)
        positions.append(pos)
        trades.extend(closed)
        prev_close = bar.close
    return ExecutionResult(
        gross=tuple(gross),
        positions=tuple(positions),
        markets=tuple(markets),
        trades=tuple(trades),
    )


def _allow_entry(rth: Sequence[bool], session_filter: str) -> tuple[bool, ...]:
    key = session_filter.strip().lower()
    if key == "globex":
        return tuple(True for _ in rth)
    return tuple(bool(flag) for flag in rth)


def _session_end_flags(
    session_dates: Sequence[date],
    allow: Sequence[bool],
    session_end_flatten: bool,
) -> tuple[bool, ...]:
    n = len(session_dates)
    flags = [False] * n
    if not session_end_flatten or n == 0:
        return tuple(flags)
    last_allowed: dict[date, int] = {}
    for index, session in enumerate(session_dates):
        if allow[index]:
            last_allowed[session] = index
    for index in last_allowed.values():
        flags[index] = True
    return tuple(flags)


@dataclass
class _Book:
    geometry: Geometry
    time_stop_bars: int
    pos: float = 0.0
    entry: float = 0.0
    pending: float = 0.0
    limit: float = 0.0
    held: int = 0

    def clear_position(self) -> None:
        self.pos, self.entry, self.pending, self.held = 0.0, 0.0, 0.0, 0

    def step(
        self,
        *,
        bar: ResearchBar,
        prev_close: float,
        adv: float,
        signal: float,
        allow_entry: bool,
        session_end: bool,
        multiplier: float,
        equity: float,
    ) -> tuple[float, float, tuple[ClosedTrade, ...]]:
        closed: list[ClosedTrade] = []
        start_pos = self.pos
        mark_from = prev_close
        if self.pending != 0.0 and self.pos == 0.0:
            if trade_through_fill(side=self.pending, limit=self.limit, bar=bar, average_volume=adv):
                self.pos, self.entry = self.pending, self.limit
                self.held = 0
                start_pos = self.pos
                mark_from = self.entry
            self.pending = 0.0
        exit_price: float | None = None
        reason = ""
        if self.pos != 0.0:
            self.held += 1
            exit_price, reason = _bracket_exit(self.pos, self.entry, bar, self.geometry)
            if exit_price is None and self.held >= self.time_stop_bars:
                exit_price, reason = bar.close, "time_stop"
            if exit_price is None and session_end:
                exit_price, reason = bar.close, "session_end"
        if exit_price is not None and start_pos != 0.0:
            pnl = start_pos * (exit_price - mark_from) * multiplier / equity
            closed.append(
                ClosedTrade(
                    side=start_pos,
                    entry_price=self.entry,
                    exit_price=exit_price,
                    pnl_ticks=(exit_price - self.entry) / self.geometry.tick_size * start_pos,
                    reason=reason,
                )
            )
            self.clear_position()
            return pnl, 0.0, tuple(closed)
        pnl = start_pos * (bar.close - mark_from) * multiplier / equity if start_pos != 0.0 else 0.0
        if self.pos == 0.0 and allow_entry and signal != 0.0:
            self.pending = signal
            self.limit = bar.close
        return pnl, self.pos, tuple(closed)


def _bracket_exit(
    pos: float,
    entry: float,
    bar: ResearchBar,
    geometry: Geometry,
) -> tuple[float | None, str]:
    target = geometry.target_ticks * geometry.tick_size
    stop = geometry.stop_ticks * geometry.tick_size
    if pos > 0.0:
        stop_px = entry - stop
        target_px = entry + target
        if bar.open < stop_px:
            return bar.open, "stop"
        if bar.low <= stop_px:
            return stop_px, "stop"
        if bar.open > target_px:
            return bar.open, "target"
        if bar.high > target_px:
            return target_px, "target"
        return None, ""
    stop_px = entry + stop
    target_px = entry - target
    if bar.open > stop_px:
        return bar.open, "stop"
    if bar.high >= stop_px:
        return stop_px, "stop"
    if bar.open < target_px:
        return bar.open, "target"
    if bar.low < target_px:
        return target_px, "target"
    return None, ""
