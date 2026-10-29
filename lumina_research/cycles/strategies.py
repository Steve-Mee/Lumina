"""Simple economically motivated position rules on OHLC bars. No live orders.

Indicators use ``signal_bars`` (back-adjusted). Fills and PnL use ``bars``
(unadjusted). Geometry is a pre-registered design choice per family, not a
Validation Gate floor.
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.execution import ExecutionResult, bar_volatility_price, run_execution
from lumina_research.cycles.geometry import Geometry
from lumina_research.cycles.sessions import annotate
from lumina_research.validation.contracts import spec_for
from lumina_research.validation.cost_model import MarketSnapshot

Tape = tuple[tuple[float, ...], tuple[float, ...], tuple[MarketSnapshot, ...]]
DEFAULT_SESSION_FILTER = "rth"
DEFAULT_TIME_STOP_BARS = 16


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
    signal_bars: Sequence[ResearchBar] | None = None,
    session_filter: str = DEFAULT_SESSION_FILTER,
    time_stop_bars: int = DEFAULT_TIME_STOP_BARS,
    session_end_flatten: bool = True,
) -> Tape:
    result = simulate_full(
        family=family,
        bars=bars,
        geometry=geometry,
        lookback=lookback,
        threshold=threshold,
        mode=mode,
        breaks=breaks,
        session_dates=session_dates,
        rth=rth,
        quiet=quiet,
        signal_bars=signal_bars,
        session_filter=session_filter,
        time_stop_bars=time_stop_bars,
        session_end_flatten=session_end_flatten,
    )
    return result.gross, result.positions, result.markets


def simulate_full(
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
    signal_bars: Sequence[ResearchBar] | None = None,
    session_filter: str = DEFAULT_SESSION_FILTER,
    time_stop_bars: int = DEFAULT_TIME_STOP_BARS,
    session_end_flatten: bool = True,
) -> ExecutionResult:
    if len(bars) < 241:
        raise StrategyRefused("need >= 241 bars for the Validation Gate")
    computed = annotate(bars)
    sessions = tuple(session_dates) if session_dates is not None else computed.session_dates
    rth_flags = tuple(rth) if rth is not None else computed.rth
    hole = tuple(breaks) if breaks is not None else tuple(False for _ in bars)
    indicators = tuple(signal_bars) if signal_bars is not None else tuple(bars)
    if len(indicators) != len(bars):
        raise StrategyRefused("signal_bars must align with trade bars")
    if family == "mean_reversion":
        signals = _mean_reversion(indicators, lookback=lookback, z_entry=threshold)
    elif family == "volume_imbalance":
        signals = _volume_imbalance(indicators, lookback=lookback, cutoff=threshold)
    elif family == "regime_momentum":
        signals = _regime_momentum(indicators, lookback=lookback, vol_pct=threshold, quiet=quiet)
    elif family == "opening_range":
        signals = _opening_range(indicators, or_bars=lookback, mode=mode, session_dates=sessions, rth=rth_flags)
    elif family == "overnight_gap":
        signals = _overnight_gap(bars, gap_ticks=threshold, geometry=geometry, session_dates=sessions, rth=rth_flags)
    elif family == "vwap_distance":
        signals = _vwap_distance(indicators, lookback=lookback, z_entry=threshold, session_dates=sessions)
    elif family == "range_compression":
        signals = _range_compression(indicators, lookback=lookback, pct=threshold)
    elif family == "close_reversal":
        signals = _close_reversal(indicators, streak=lookback)
    elif family == "time_of_day":
        signals = _time_of_day(indicators, first_bars=lookback, session_dates=sessions, rth=rth_flags)
    elif family == "trend_pullback":
        signals = _trend_pullback(indicators, lookback=lookback, quiet=quiet)
    elif family == "volatility_expansion":
        signals = _volatility_expansion(indicators, lookback=lookback, pct=threshold)
    else:
        raise StrategyRefused(f"unknown family {family!r}")
    return run_execution(
        bars=bars,
        signals=signals,
        geometry=geometry,
        breaks=hole,
        rth=rth_flags,
        session_dates=sessions,
        session_filter=session_filter,
        time_stop_bars=time_stop_bars,
        session_end_flatten=session_end_flatten,
    )


def _mean_reversion(bars: Sequence[ResearchBar], *, lookback: int, z_entry: float) -> tuple[float, ...]:
    closes = [item.close for item in bars]
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
        out.append(signal)
    return tuple(out)


def _volume_imbalance(bars: Sequence[ResearchBar], *, lookback: int, cutoff: float) -> tuple[float, ...]:
    signed: list[float] = []
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
        out.append(signal)
    return tuple(out)


def _regime_momentum(
    bars: Sequence[ResearchBar],
    *,
    lookback: int,
    vol_pct: float,
    quiet: Sequence[bool] | None,
) -> tuple[float, ...]:
    closes = [item.close for item in bars]
    rets = [0.0]
    for index in range(1, len(closes)):
        prev = closes[index - 1]
        rets.append(0.0 if prev == 0.0 else (closes[index] - prev) / prev)
    out: list[float] = []
    sq_hist: list[float] = []
    for index, _bar in enumerate(bars):
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
        out.append(signal)
    return tuple(out)


def _opening_range(
    bars: Sequence[ResearchBar],
    *,
    or_bars: int,
    mode: str,
    session_dates: Sequence[date],
    rth: Sequence[bool],
) -> tuple[float, ...]:
    first_rth: dict[date, list[int]] = {}
    for index, session in enumerate(session_dates):
        if rth[index]:
            first_rth.setdefault(session, []).append(index)
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
        out.append(signal)
    return tuple(out)


def _overnight_gap(
    bars: Sequence[ResearchBar],
    *,
    gap_ticks: float,
    geometry: Geometry,
    session_dates: Sequence[date],
    rth: Sequence[bool],
) -> tuple[float, ...]:
    """RTH close of the previous cash session → RTH open of today. Not the Globex halt."""
    spec = spec_for(geometry.root)
    last_rth_close: dict[date, float] = {}
    first_rth_index: dict[date, int] = {}
    for index, session in enumerate(session_dates):
        if rth[index]:
            last_rth_close[session] = bars[index].close
            first_rth_index.setdefault(session, index)
    sessions_in_order: list[date] = []
    seen: set[date] = set()
    for session in session_dates:
        if session not in seen:
            seen.add(session)
            sessions_in_order.append(session)
    prev_rth: dict[date, float] = {}
    previous_close: float | None = None
    for session in sessions_in_order:
        if previous_close is not None:
            prev_rth[session] = previous_close
        if session in last_rth_close:
            previous_close = last_rth_close[session]
    out = [0.0] * len(bars)
    for session, index in first_rth_index.items():
        prior = prev_rth.get(session)
        if prior is None:
            continue
        gap = (bars[index].open - prior) / spec.tick_size
        if gap >= gap_ticks:
            out[index] = -1.0
        elif gap <= -gap_ticks:
            out[index] = 1.0
    return tuple(out)


def _vwap_distance(
    bars: Sequence[ResearchBar],
    *,
    lookback: int,
    z_entry: float,
    session_dates: Sequence[date],
) -> tuple[float, ...]:
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
        out.append(signal)
    return tuple(out)


def _range_compression(bars: Sequence[ResearchBar], *, lookback: int, pct: float) -> tuple[float, ...]:
    ranges = [item.high - item.low for item in bars]
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
        out.append(signal)
    return tuple(out)


def _close_reversal(bars: Sequence[ResearchBar], *, streak: int) -> tuple[float, ...]:
    out: list[float] = []
    for index, _bar in enumerate(bars):
        signal = 0.0
        if index >= streak:
            window = bars[index - streak : index]
            up = all(item.close > item.open for item in window)
            down = all(item.close < item.open for item in window)
            if up:
                signal = -1.0
            elif down:
                signal = 1.0
        out.append(signal)
    return tuple(out)


def _time_of_day(
    bars: Sequence[ResearchBar],
    *,
    first_bars: int,
    session_dates: Sequence[date],
    rth: Sequence[bool],
) -> tuple[float, ...]:
    first_rth: dict[date, list[int]] = {}
    for index, session in enumerate(session_dates):
        if rth[index]:
            first_rth.setdefault(session, []).append(index)
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
        out.append(signal)
    return tuple(out)


def _trend_pullback(bars: Sequence[ResearchBar], *, lookback: int, quiet: Sequence[bool] | None) -> tuple[float, ...]:
    closes = [item.close for item in bars]
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
        out.append(signal)
    return tuple(out)


def _volatility_expansion(bars: Sequence[ResearchBar], *, lookback: int, pct: float) -> tuple[float, ...]:
    """Expansion when the bar range exceeds the ``pct`` percentile of prior ranges.

    Pre-registered at the 75th percentile (pct=0.75). The 25th percentile would
    fire on most bars and does not test the expansion hypothesis.
    """
    ranges = [item.high - item.low for item in bars]
    out: list[float] = []
    for index, bar in enumerate(bars):
        signal = 0.0
        if index >= lookback:
            window = sorted(ranges[index - lookback : index])
            cap = window[max(0, int(pct * (len(window) - 1)))]
            expanded = ranges[index] > cap
            if expanded:
                signal = 1.0 if bar.close >= bar.open else -1.0
        out.append(signal)
    return tuple(out)


def mark_to_market_tape(
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
        markets.append(
            MarketSnapshot(
                volume=max(bar.volume, 1.0),
                average_volume=avg_vol,
                volatility_price=bar_volatility_price(bar),
            )
        )
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
