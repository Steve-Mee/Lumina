"""Simple economically motivated position rules on OHLC bars. No live orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.fills import trade_through_fill
from lumina_research.cycles.geometry import Geometry
from lumina_research.cycles.sessions import annotate
from lumina_research.validation.cost_model import MarketSnapshot
from lumina_research.validation.contracts import spec_for

Tape = tuple[tuple[float, ...], tuple[float, ...], tuple[MarketSnapshot, ...]]


class StrategyRefused(ValueError):
    """A research strategy could not be evaluated on the supplied tape."""


def simulate(
    *,
    family: str,
    bars: Sequence[ResearchBar],
    geometry: Geometry,
    lookback: int,
    threshold: float,
    mode: str,
    breaks: Sequence[bool] | None = None,
    session_dates: Sequence[date] | None = None,
    rth: Sequence[bool] | None = None,
    quiet: Sequence[bool] | None = None,
) -> Tape:
    if len(bars) < 241:
        raise StrategyRefused("need >= 241 bars for the Validation Gate")
    computed = annotate(bars)
    sessions = tuple(session_dates) if session_dates is not None else computed.session_dates
    rth_flags = tuple(rth) if rth is not None else computed.rth
    hole = tuple(breaks) if breaks is not None else tuple(False for _ in bars)
    if family == "mean_reversion":
        positions = _mean_reversion(
            bars, lookback=lookback, z_entry=threshold, geometry=geometry, breaks=hole
        )
    elif family == "volume_imbalance":
        positions = _volume_imbalance(
            bars, lookback=lookback, cutoff=threshold, geometry=geometry, breaks=hole
        )
    elif family == "regime_momentum":
        positions = _regime_momentum(
            bars, lookback=lookback, vol_pct=threshold, geometry=geometry, breaks=hole, quiet=quiet
        )
    elif family == "opening_range":
        positions = _opening_range(
            bars,
            or_bars=lookback,
            mode=mode,
            geometry=geometry,
            breaks=hole,
            session_dates=sessions,
            rth=rth_flags,
        )
    elif family == "overnight_gap":
        positions = _overnight_gap(
            bars, gap_ticks=threshold, geometry=geometry, breaks=hole, session_dates=sessions
        )
    elif family == "vwap_distance":
        positions = _vwap_distance(
            bars,
            lookback=lookback,
            z_entry=threshold,
            geometry=geometry,
            breaks=hole,
            session_dates=sessions,
        )
    elif family == "range_compression":
        positions = _range_compression(
            bars, lookback=lookback, pct=threshold, geometry=geometry, breaks=hole
        )
    elif family == "close_reversal":
        positions = _close_reversal(bars, streak=lookback, geometry=geometry, breaks=hole)
    elif family == "time_of_day":
        positions = _time_of_day(
            bars,
            first_bars=lookback,
            geometry=geometry,
            breaks=hole,
            session_dates=sessions,
            rth=rth_flags,
        )
    elif family == "trend_pullback":
        positions = _trend_pullback(
            bars, lookback=lookback, geometry=geometry, breaks=hole, quiet=quiet
        )
    elif family == "volatility_expansion":
        positions = _volatility_expansion(
            bars, lookback=lookback, pct=threshold, geometry=geometry, breaks=hole
        )
    else:
        raise StrategyRefused(f"unknown family {family!r}")
    return _tape(bars, positions, geometry.root, breaks=hole)


@dataclass
class _Book:
    pos: float = 0.0
    entry: float = 0.0
    pending: float = 0.0
    limit: float = 0.0

    def step(
        self,
        bar: ResearchBar,
        geometry: Geometry,
        adv: float,
        signal: float,
        flatten: bool = False,
    ) -> float:
        if flatten:
            self.pos, self.entry, self.pending = 0.0, 0.0, 0.0
            return 0.0
        if self.pending != 0.0 and self.pos == 0.0:
            if trade_through_fill(side=self.pending, limit=self.limit, bar=bar, average_volume=adv):
                self.pos, self.entry = self.pending, self.limit
            self.pending = 0.0
        if self.pos == 0.0 and self.pending == 0.0 and signal != 0.0:
            self.pending = signal
            self.limit = bar.close
        self.pos, self.entry = _manage(self.pos, self.entry, bar, geometry)
        return self.pos


def _flat(breaks: Sequence[bool], index: int) -> bool:
    return bool(breaks[index])


def _adv(bars: Sequence[ResearchBar], index: int) -> float:
    window = bars[max(0, index - 20) : index + 1]
    total = sum(max(item.volume, 1.0) for item in window)
    return total / float(len(window))


def _mean_reversion(
    bars: Sequence[ResearchBar],
    *,
    lookback: int,
    z_entry: float,
    geometry: Geometry,
    breaks: Sequence[bool],
) -> tuple[float, ...]:
    closes = [item.close for item in bars]
    book = _Book()
    out: list[float] = []
    for index, bar in enumerate(bars):
        signal = 0.0
        if index >= lookback:
            window = closes[index - lookback : index]
            mean = sum(window) / float(lookback)
            var = sum((item - mean) ** 2 for item in window) / float(lookback)
            stdev = var**0.5
            zed = 0.0 if stdev <= 1e-12 else (bar.close - mean) / stdev
            if zed > z_entry:
                signal = -1.0
            elif zed < -z_entry:
                signal = 1.0
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _volume_imbalance(
    bars: Sequence[ResearchBar],
    *,
    lookback: int,
    cutoff: float,
    geometry: Geometry,
    breaks: Sequence[bool],
) -> tuple[float, ...]:
    signed: list[float] = []
    book = _Book()
    out: list[float] = []
    for index, bar in enumerate(bars):
        direction = 1.0 if bar.close >= bar.open else -1.0
        signed.append(direction * bar.volume)
        signal = 0.0
        if index >= lookback:
            window = signed[index - lookback : index]
            total = sum(abs(item) for item in window)
            imb = 0.0 if total <= 1e-12 else sum(window) / total
            if imb > cutoff:
                signal = -1.0
            elif imb < -cutoff:
                signal = 1.0
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _regime_momentum(
    bars: Sequence[ResearchBar],
    *,
    lookback: int,
    vol_pct: float,
    geometry: Geometry,
    breaks: Sequence[bool],
    quiet: Sequence[bool] | None,
) -> tuple[float, ...]:
    closes = [item.close for item in bars]
    rets = [0.0]
    for index in range(1, len(closes)):
        prev = closes[index - 1]
        rets.append(0.0 if prev == 0.0 else (closes[index] - prev) / prev)
    book = _Book()
    out: list[float] = []
    sq_hist: list[float] = []
    for index, bar in enumerate(bars):
        signal = 0.0
        if index >= lookback:
            window = rets[index - lookback : index]
            vol = (sum(item * item for item in window) / float(lookback)) ** 0.5
            sq_hist.append(sum(item * item for item in window))
            history = sq_hist[-252:-1]
            median_vol = (sorted(history)[len(history) // 2] ** 0.5) if history else vol
            local_quiet = vol <= max(median_vol * (0.5 + vol_pct), 1e-12)
            if quiet is not None:
                local_quiet = local_quiet and bool(quiet[index])
            mom = sum(window)
            if local_quiet and mom > 0.0:
                signal = 1.0
            elif local_quiet and mom < 0.0:
                signal = -1.0
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _opening_range(
    bars: Sequence[ResearchBar],
    *,
    or_bars: int,
    mode: str,
    geometry: Geometry,
    breaks: Sequence[bool],
    session_dates: Sequence[date],
    rth: Sequence[bool],
) -> tuple[float, ...]:
    first_rth: dict[date, list[int]] = {}
    for index, session in enumerate(session_dates):
        if rth[index]:
            first_rth.setdefault(session, []).append(index)
    book = _Book()
    out: list[float] = []
    for index, bar in enumerate(bars):
        signal = 0.0
        opening_idx = first_rth.get(session_dates[index], [])[:or_bars]
        if len(opening_idx) >= or_bars and index > opening_idx[-1]:
            opening = [bars[item] for item in opening_idx]
            hi = max(item.high for item in opening)
            lo = min(item.low for item in opening)
            if mode == "breakout":
                if bar.close > hi:
                    signal = 1.0
                elif bar.close < lo:
                    signal = -1.0
            else:
                if bar.close > hi:
                    signal = -1.0
                elif bar.close < lo:
                    signal = 1.0
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _overnight_gap(
    bars: Sequence[ResearchBar],
    *,
    gap_ticks: float,
    geometry: Geometry,
    breaks: Sequence[bool],
    session_dates: Sequence[date],
) -> tuple[float, ...]:
    spec = spec_for(geometry.root)
    last_close: dict[date, float] = {}
    book = _Book()
    out: list[float] = []
    for index, bar in enumerate(bars):
        session = session_dates[index]
        signal = 0.0
        if index >= 1 and session != session_dates[index - 1] and not breaks[index]:
            prev_session = session_dates[index - 1]
            prev_close = last_close.get(prev_session, bars[index - 1].close)
            gap = (bar.open - prev_close) / spec.tick_size
            if gap >= gap_ticks:
                signal = -1.0
            elif gap <= -gap_ticks:
                signal = 1.0
        last_close[session] = bar.close
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _vwap_distance(
    bars: Sequence[ResearchBar],
    *,
    lookback: int,
    z_entry: float,
    geometry: Geometry,
    breaks: Sequence[bool],
    session_dates: Sequence[date],
) -> tuple[float, ...]:
    book = _Book()
    out: list[float] = []
    pv = 0.0
    vol = 0.0
    dist: list[float] = []
    current_session = session_dates[0] if session_dates else None
    for index, bar in enumerate(bars):
        session = session_dates[index]
        if current_session is not None and session != current_session:
            pv = 0.0
            vol = 0.0
        current_session = session
        typical = (bar.high + bar.low + bar.close) / 3.0
        pv += typical * max(bar.volume, 1.0)
        vol += max(bar.volume, 1.0)
        vwap = pv / vol
        dist.append(bar.close - vwap)
        signal = 0.0
        if index >= lookback:
            window = dist[index - lookback : index]
            mean = sum(window) / float(lookback)
            var = sum((item - mean) ** 2 for item in window) / float(lookback)
            stdev = var**0.5
            zed = 0.0 if stdev <= 1e-12 else (dist[-1] - mean) / stdev
            if zed > z_entry:
                signal = -1.0
            elif zed < -z_entry:
                signal = 1.0
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _range_compression(
    bars: Sequence[ResearchBar],
    *,
    lookback: int,
    pct: float,
    geometry: Geometry,
    breaks: Sequence[bool],
) -> tuple[float, ...]:
    ranges = [item.high - item.low for item in bars]
    book = _Book()
    out: list[float] = []
    for index, bar in enumerate(bars):
        signal = 0.0
        if index >= lookback:
            window = sorted(ranges[index - lookback : index])
            cap = window[max(0, int(pct * (len(window) - 1)))]
            compressed = ranges[index - 1] <= cap if index > 0 else False
            if compressed:
                mid = 0.5 * (bars[index - 1].high + bars[index - 1].low)
                if bar.close > mid:
                    signal = 1.0
                elif bar.close < mid:
                    signal = -1.0
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _close_reversal(
    bars: Sequence[ResearchBar],
    *,
    streak: int,
    geometry: Geometry,
    breaks: Sequence[bool],
) -> tuple[float, ...]:
    book = _Book()
    out: list[float] = []
    for index, bar in enumerate(bars):
        signal = 0.0
        if index >= streak:
            window = bars[index - streak : index]
            up = all(item.close > item.open for item in window)
            down = all(item.close < item.open for item in window)
            if up:
                signal = -1.0
            elif down:
                signal = 1.0
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _time_of_day(
    bars: Sequence[ResearchBar],
    *,
    first_bars: int,
    geometry: Geometry,
    breaks: Sequence[bool],
    session_dates: Sequence[date],
    rth: Sequence[bool],
) -> tuple[float, ...]:
    first_rth: dict[date, list[int]] = {}
    for index, session in enumerate(session_dates):
        if rth[index]:
            first_rth.setdefault(session, []).append(index)
    book = _Book()
    out: list[float] = []
    for index, bar in enumerate(bars):
        signal = 0.0
        opening_idx = first_rth.get(session_dates[index], [])
        if opening_idx and opening_idx[0] < index <= opening_idx[0] + first_bars:
            opening = bars[opening_idx[0]]
            if bar.close > opening.open:
                signal = -1.0
            elif bar.close < opening.open:
                signal = 1.0
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _trend_pullback(
    bars: Sequence[ResearchBar],
    *,
    lookback: int,
    geometry: Geometry,
    breaks: Sequence[bool],
    quiet: Sequence[bool] | None,
) -> tuple[float, ...]:
    closes = [item.close for item in bars]
    book = _Book()
    out: list[float] = []
    for index, bar in enumerate(bars):
        signal = 0.0
        allowed = True if quiet is None else bool(quiet[index])
        if allowed and index >= lookback:
            window = closes[index - lookback : index]
            trend = window[-1] - window[0]
            mid = sum(window) / float(lookback)
            if trend > 0.0 and bar.close < mid:
                signal = 1.0
            elif trend < 0.0 and bar.close > mid:
                signal = -1.0
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _volatility_expansion(
    bars: Sequence[ResearchBar],
    *,
    lookback: int,
    pct: float,
    geometry: Geometry,
    breaks: Sequence[bool],
) -> tuple[float, ...]:
    ranges = [item.high - item.low for item in bars]
    book = _Book()
    out: list[float] = []
    for index, bar in enumerate(bars):
        signal = 0.0
        if index >= lookback:
            window = sorted(ranges[index - lookback : index])
            cap = window[max(0, int(pct * (len(window) - 1)))]
            expanded = ranges[index] > cap
            if expanded:
                if bar.close >= bar.open:
                    signal = 1.0
                else:
                    signal = -1.0
        out.append(book.step(bar, geometry, _adv(bars, index), signal, flatten=_flat(breaks, index)))
    return tuple(out)


def _manage(pos: float, entry: float, bar: ResearchBar, geometry: Geometry) -> tuple[float, float]:
    if pos == 0.0:
        return 0.0, entry
    target = geometry.target_ticks * geometry.tick_size
    stop = geometry.stop_ticks * geometry.tick_size
    if pos > 0.0:
        hit_stop = bar.low <= entry - stop
        hit_target = bar.high >= entry + target
        if hit_stop:
            return 0.0, 0.0
        if hit_target:
            return 0.0, 0.0
        return pos, entry
    hit_stop = bar.high >= entry + stop
    hit_target = bar.low <= entry - target
    if hit_stop:
        return 0.0, 0.0
    if hit_target:
        return 0.0, 0.0
    return pos, entry


def _tape(
    bars: Sequence[ResearchBar],
    positions: Sequence[float],
    root: str,
    *,
    breaks: Sequence[bool] | None = None,
) -> Tape:
    spec = spec_for(root)
    n = len(bars)
    hole = tuple(False for _ in bars) if breaks is None else tuple(breaks)
    if n != len(positions) or n != len(hole):
        raise StrategyRefused("positions must align with bars")
    equity = 100_000.0
    gross: list[float] = [0.0]
    markets: list[MarketSnapshot] = []
    volumes = [max(item.volume, 1.0) for item in bars]
    avg_vol = sum(volumes) / float(n)
    for index, bar in enumerate(bars):
        markets.append(MarketSnapshot(volume=max(bar.volume, 1.0), average_volume=avg_vol, volatility_price=2.0))
        if index == 0:
            continue
        if hole[index]:
            gross.append(0.0)
            continue
        prev = bars[index - 1]
        delta = bar.close - prev.close
        qty = float(positions[index])
        gross.append(qty * delta * spec.multiplier / equity)
    return tuple(gross), tuple(float(item) for item in positions), tuple(markets)
