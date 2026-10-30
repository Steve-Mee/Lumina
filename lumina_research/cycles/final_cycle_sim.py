"""Locked final-cycle execution for RV-01, RV-02, LH-01, LH-03. No live orders.

Pair legs are dollar-neutral (1 ES vs notional-matched NQ, min 1 NQ). LH-03
uses 5-minute ATR(14) strictly before the release — a parameter clarification,
not a new hypothesis.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from lumina_research.cycles.catalog import HypothesisSpec
from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.daily import daily_net_tape, unique_sessions
from lumina_research.cycles.diagnostics import ConfigDiagnostics, from_trades
from lumina_research.cycles.execution import (
    ClosedTrade,
    ExecutionResult,
    bar_volatility_price,
    causal_session_adv,
    run_execution,
)
from lumina_research.cycles.fills import trade_through_fill
from lumina_research.cycles.final_cycle import (
    LH01_TARGET_RANGE_MULT,
    LH03_ATR_MULT,
    LH03_LAG_NS,
    RV01_LOOKBACK_SESSIONS,
    RV01_MAX_HOLD_NS,
    RV01_Z_ENTRY,
    RV01_Z_EXIT,
    RV01_Z_STOP,
    RV02_ES_MULTIPLIER,
    RV02_NQ_MULTIPLIER,
    RV02_REL_GAP_PCT,
    VIX_FILTER_MAX,
    MacroEvent,
    five_minute_atr14_before,
    previous_vix_close,
    resample_five_minute,
    rth_sessions,
)
from lumina_research.cycles.geometry import require_geometry
from lumina_research.cycles.prepare import PreparedTape
from lumina_research.cycles.strategies import Tape
from lumina_research.validation.cost_model import CostedSeries, MarketSnapshot, apply_costs
from lumina_research.validation.types import RegimeSnapshot

EQUITY = 100_000.0
FINAL_CYCLE_RUN_IDS: frozenset[str] = frozenset({"p2s-rv-01", "p2s-rv-02", "p2s-lh-01", "p2s-lh-03"})
LH01_STOP_RANGE_MULT = 1.0
LH03_TARGET_SPIKE_MULT = 0.5
LH03_STOP_SPIKE_MULT = 1.5
LH03_TIME_STOP_BARS = 90
RV02_TIME_STOP_NS = 90 * 60 * 1_000_000_000
RV02_TARGET_FILL = 0.5
RV02_STOP_EXTEND = 1.5


@dataclass(frozen=True, slots=True)
class FinalCycleContext:
    es: PreparedTape
    nq: PreparedTape
    vix: tuple[tuple[date, float], ...]
    events: tuple[MacroEvent, ...]
    nq_bars: dict[int, ResearchBar]


_CONTEXT: FinalCycleContext | None = None


class FinalCycleSimRefused(RuntimeError):
    """Final-cycle simulation cannot run without the bound ES/NQ/VIX/macro context."""


def bind_context(ctx: FinalCycleContext) -> None:
    global _CONTEXT
    _CONTEXT = ctx


def clear_context() -> None:
    global _CONTEXT
    _CONTEXT = None


def get_context() -> FinalCycleContext:
    if _CONTEXT is None:
        raise FinalCycleSimRefused("final-cycle context is not bound")
    return _CONTEXT


def simulate_final_cycle(spec: HypothesisSpec, prepared: PreparedTape) -> tuple[Tape, ConfigDiagnostics]:
    ctx = get_context()
    if prepared.instrument != "ES" or spec.instrument != "ES":
        raise FinalCycleSimRefused("final-cycle specs execute against ES as the primary tape")
    if spec.config_id == "p2s-lh-01":
        executed, costed = _simulate_lh01(prepared)
    elif spec.config_id == "p2s-lh-03":
        executed, costed = _simulate_lh03(prepared, ctx.events)
    elif spec.config_id == "p2s-rv-01":
        executed, costed = _simulate_rv01(prepared, ctx)
    elif spec.config_id == "p2s-rv-02":
        executed, costed = _simulate_rv02(prepared, ctx)
    else:
        raise FinalCycleSimRefused(f"unsupported final-cycle id {spec.config_id}")
    geometry = require_geometry(root="ES", target_ticks=spec.target_ticks, stop_ticks=spec.stop_ticks)
    diag = from_trades(
        trades=executed.trades,
        geometry=geometry,
        costed=costed,
        is_sharpes=(),
        oos_sharpes=(),
        regimes=RegimeSnapshot.missing(),
        n_trials=0,
        n_days=len(unique_sessions(prepared.session_dates)),
        pct_positive_oos=float("nan"),
        target_atr=spec.target_atr,
        stop_atr=spec.stop_atr,
        disable_brackets=spec.disable_brackets,
    )
    built = daily_net_tape(costed.net_returns, prepared.session_dates)
    return built, diag


def _simulate_lh01(prepared: PreparedTape) -> tuple[ExecutionResult, CostedSeries]:
    signals, atr_points = _lh01_signals(prepared)
    geometry = require_geometry(root="ES", target_ticks=1, stop_ticks=1)
    executed = run_execution(
        bars=prepared.bars,
        signals=signals,
        geometry=geometry,
        breaks=prepared.breaks,
        rth=prepared.rth,
        session_dates=prepared.session_dates,
        session_filter="rth",
        time_stop_bars=2000,
        session_end_flatten=True,
        atr_points=atr_points,
        target_atr=LH01_TARGET_RANGE_MULT,
        stop_atr=LH01_STOP_RANGE_MULT,
    )
    return executed, _cost_es(executed)


def _simulate_lh03(
    prepared: PreparedTape,
    events: Sequence[MacroEvent],
) -> tuple[ExecutionResult, CostedSeries]:
    signals, atr_points = _lh03_signals(prepared, events)
    geometry = require_geometry(root="ES", target_ticks=1, stop_ticks=1)
    executed = run_execution(
        bars=prepared.bars,
        signals=signals,
        geometry=geometry,
        breaks=prepared.breaks,
        rth=prepared.rth,
        session_dates=prepared.session_dates,
        session_filter="globex",
        time_stop_bars=LH03_TIME_STOP_BARS,
        session_end_flatten=True,
        atr_points=atr_points,
        target_atr=LH03_TARGET_SPIKE_MULT,
        stop_atr=LH03_STOP_SPIKE_MULT,
    )
    return executed, _cost_es(executed)


def _lh01_signals(prepared: PreparedTape) -> tuple[tuple[float, ...], tuple[float, ...]]:
    sessions = rth_sessions(prepared.bars)
    n = len(prepared.bars)
    signals = [0.0] * n
    atr_points = [0.0] * n
    if len(sessions) < 8:
        return tuple(signals), tuple(atr_points)
    first_rth: dict[date, int] = {}
    last_rth: dict[date, int] = {}
    for index, (session, is_rth) in enumerate(zip(prepared.session_dates, prepared.rth, strict=True)):
        if not is_rth:
            continue
        first_rth.setdefault(session, index)
        last_rth[session] = index
    for index in range(7, len(sessions)):
        prior = sessions[index - 7 : index]
        nr7 = prior[-1]
        nr7_range = nr7.high - nr7.low
        if nr7_range <= 0.0:
            continue
        if nr7_range > min(item.high - item.low for item in prior) + 1e-12:
            continue
        day = sessions[index].session
        start = first_rth.get(day)
        end = last_rth.get(day)
        if start is None or end is None:
            continue
        fired = False
        for bar_i in range(start, end + 1):
            bar = prepared.bars[bar_i]
            broke_high = bar.high > nr7.high
            broke_low = bar.low < nr7.low
            if broke_high and broke_low:
                continue
            if broke_high:
                signals[bar_i] = 1.0
                fired = True
            elif broke_low:
                signals[bar_i] = -1.0
                fired = True
            if fired:
                for hold_i in range(bar_i, end + 1):
                    atr_points[hold_i] = nr7_range
                break
    return tuple(signals), tuple(atr_points)


def _lh03_signals(
    prepared: PreparedTape,
    events: Sequence[MacroEvent],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    n = len(prepared.bars)
    signals = [0.0] * n
    atr_points = [0.0] * n
    five_min = resample_five_minute(prepared.bars)
    ts_list = [item.ts_ns for item in prepared.bars]
    by_ts = {item.ts_ns: index for index, item in enumerate(prepared.bars)}
    for event in events:
        post_i = by_ts.get(event.event_ns + LH03_LAG_NS)
        if post_i is None:
            continue
        pre_index = bisect.bisect_left(ts_list, event.event_ns) - 1
        if pre_index < 0:
            continue
        pre = prepared.bars[pre_index]
        post = prepared.bars[post_i]
        atr = five_minute_atr14_before(five_min, event.event_ns)
        if atr is None:
            continue
        spike = abs(post.close - pre.close)
        if spike <= LH03_ATR_MULT * atr:
            continue
        signals[post_i] = -1.0 if post.close > pre.close else 1.0
        hold_end = min(n, post_i + LH03_TIME_STOP_BARS + 2)
        for hold_i in range(post_i, hold_end):
            atr_points[hold_i] = spike
    return tuple(signals), tuple(atr_points)


def _simulate_rv01(
    prepared: PreparedTape,
    ctx: FinalCycleContext,
) -> tuple[ExecutionResult, CostedSeries]:
    stats = _ratio_stats(prepared, ctx)
    nq_close = {ts: bar.close for ts, bar in ctx.nq_bars.items()}
    n = len(prepared.bars)
    pending_es = 0.0
    pending_nq = 0.0
    pending_limit_es = 0.0
    pending_limit_nq = 0.0
    es_pos = 0.0
    nq_pos = 0.0
    entry_ns = 0
    es_gross = [0.0] * n
    nq_gross = [0.0] * n
    es_positions = [0.0] * n
    nq_positions = [0.0] * n
    es_markets: list[MarketSnapshot] = []
    nq_markets: list[MarketSnapshot] = []
    trades: list[ClosedTrade] = []
    prev_es = prepared.bars[0].close
    prev_nq = ctx.nq_bars.get(prepared.bars[0].ts_ns)
    prev_nq_px = 0.0 if prev_nq is None else prev_nq.close
    last_rth = _last_rth_index(prepared)

    def flatten(index: int, bar: ResearchBar, nq_bar: ResearchBar | None, reason: str) -> None:
        nonlocal es_pos, nq_pos
        if es_pos == 0.0:
            return
        exit_es = bar.close
        exit_nq = entry_nq_px if nq_bar is None else nq_bar.close
        es_gross[index] += es_pos * (exit_es - prev_es) * RV02_ES_MULTIPLIER / EQUITY
        if nq_bar is not None:
            nq_gross[index] += nq_pos * (exit_nq - prev_nq_px) * RV02_NQ_MULTIPLIER / EQUITY
        es_usd = es_pos * (exit_es - entry_es_px) * RV02_ES_MULTIPLIER
        nq_usd = nq_pos * (exit_nq - entry_nq_px) * RV02_NQ_MULTIPLIER
        trades.append(
            ClosedTrade(
                side=es_pos,
                entry_price=entry_es_px,
                exit_price=exit_es,
                pnl_ticks=(es_usd + nq_usd) / 12.50,
                reason=reason,
            )
        )
        es_pos = 0.0
        nq_pos = 0.0

    entry_es_px = 0.0
    entry_nq_px = 0.0
    for index, bar in enumerate(prepared.bars):
        session = "rth" if prepared.rth[index] else "eth"
        nq_bar = ctx.nq_bars.get(bar.ts_ns)
        es_markets.append(_market(bar, prepared, index, session))
        nq_markets.append(_market(nq_bar, prepared, index, session) if nq_bar is not None else _empty_market(session))
        if prepared.breaks[index]:
            if es_pos != 0.0:
                flatten(index, bar, nq_bar, "break")
            pending_es = 0.0
            pending_nq = 0.0
            es_positions[index] = 0.0
            nq_positions[index] = 0.0
            prev_es = bar.close
            if nq_bar is not None:
                prev_nq_px = nq_bar.close
            continue
        if pending_es != 0.0 and es_pos == 0.0 and nq_bar is not None:
            es_adv = causal_session_adv(prepared.bars, prepared.rth, index)
            nq_adv = max(nq_bar.volume, 1.0)
            if trade_through_fill(side=pending_es, limit=pending_limit_es, bar=bar, average_volume=es_adv) and trade_through_fill(
                side=pending_nq, limit=pending_limit_nq, bar=nq_bar, average_volume=nq_adv
            ):
                es_pos = pending_es
                nq_pos = pending_nq
                entry_es_px = pending_limit_es
                entry_nq_px = pending_limit_nq
                entry_ns = bar.ts_ns
                prev_es = pending_limit_es
                prev_nq_px = pending_limit_nq
            pending_es = 0.0
            pending_nq = 0.0
        z_score = _ratio_z(bar, nq_close.get(bar.ts_ns), stats.get(prepared.session_dates[index]))
        abs_z = 0.0 if z_score is None else abs(z_score)
        if es_pos != 0.0:
            timed_out = bar.ts_ns >= entry_ns + RV01_MAX_HOLD_NS
            z_exit = z_score is not None and abs_z < RV01_Z_EXIT
            z_stop = z_score is not None and abs_z >= RV01_Z_STOP
            reason = ""
            if z_stop:
                reason = "stop"
            elif z_exit:
                reason = "target"
            elif timed_out:
                reason = "time_stop"
            if reason:
                flatten(index, bar, nq_bar, reason)
            else:
                es_gross[index] = es_pos * (bar.close - prev_es) * RV02_ES_MULTIPLIER / EQUITY
                if nq_bar is not None:
                    nq_gross[index] = nq_pos * (nq_bar.close - prev_nq_px) * RV02_NQ_MULTIPLIER / EQUITY
            es_positions[index] = es_pos
            nq_positions[index] = nq_pos
            prev_es = bar.close
            if nq_bar is not None:
                prev_nq_px = nq_bar.close
            continue
        if (
            prepared.rth[index]
            and es_pos == 0.0
            and pending_es == 0.0
            and z_score is not None
            and abs_z > RV01_Z_ENTRY
            and nq_bar is not None
        ):
            vix_prev = previous_vix_close(ctx.vix, prepared.session_dates[index])
            if vix_prev is not None and vix_prev < VIX_FILTER_MAX:
                nq_qty = _nq_qty(bar.close, nq_bar.close)
                if z_score > 0.0:
                    pending_es = -1.0
                    pending_nq = nq_qty
                else:
                    pending_es = 1.0
                    pending_nq = -nq_qty
                pending_limit_es = bar.close
                pending_limit_nq = nq_bar.close
        es_positions[index] = es_pos
        nq_positions[index] = nq_pos
        prev_es = bar.close
        if nq_bar is not None:
            prev_nq_px = nq_bar.close
        if index == last_rth.get(prepared.session_dates[index]) and es_pos == 0.0:
            pending_es = 0.0
            pending_nq = 0.0
    executed = ExecutionResult(
        gross=tuple(es_g + nq_g for es_g, nq_g in zip(es_gross, nq_gross, strict=True)),
        positions=tuple(es_positions),
        markets=tuple(es_markets),
        trades=tuple(trades),
        signals=tuple(0.0 for _ in prepared.bars),
    )
    return executed, _cost_pair(es_gross, es_positions, es_markets, nq_gross, nq_positions, nq_markets)


def _simulate_rv02(
    prepared: PreparedTape,
    ctx: FinalCycleContext,
) -> tuple[ExecutionResult, CostedSeries]:
    es_sessions = rth_sessions(prepared.bars)
    nq_sessions = {item.session: item for item in rth_sessions(ctx.nq.bars)}
    first_rth = _first_rth_index(prepared)
    last_rth = _last_rth_index(prepared)
    prev_by_session: dict[date, tuple[float, float]] = {}
    previous_session: date | None = None
    for session_row in es_sessions:
        nq_day = nq_sessions.get(session_row.session)
        if nq_day is None:
            continue
        if previous_session is not None and previous_session in nq_sessions:
            prev_es_sess = next(item for item in es_sessions if item.session == previous_session)
            prev_nq_sess = nq_sessions[previous_session]
            prev_by_session[session_row.session] = (prev_es_sess.close, prev_nq_sess.close)
        previous_session = session_row.session
    n = len(prepared.bars)
    pending_es = 0.0
    pending_nq = 0.0
    pending_limit_es = 0.0
    pending_limit_nq = 0.0
    entry_rel = 0.0
    ref_es = 0.0
    ref_nq = 0.0
    es_pos = 0.0
    nq_pos = 0.0
    entry_ns = 0
    entry_es_px = 0.0
    entry_nq_px = 0.0
    es_gross = [0.0] * n
    nq_gross = [0.0] * n
    es_positions = [0.0] * n
    nq_positions = [0.0] * n
    es_markets: list[MarketSnapshot] = []
    nq_markets: list[MarketSnapshot] = []
    trades: list[ClosedTrade] = []
    prev_es = prepared.bars[0].close
    first_nq = ctx.nq_bars.get(prepared.bars[0].ts_ns)
    prev_nq_px = 0.0 if first_nq is None else first_nq.close

    def flatten_gap(index: int, bar: ResearchBar, nq_bar: ResearchBar | None, reason: str) -> None:
        nonlocal es_pos, nq_pos
        if es_pos == 0.0:
            return
        exit_es = bar.close
        exit_nq = entry_nq_px if nq_bar is None else nq_bar.close
        es_gross[index] += es_pos * (exit_es - prev_es) * RV02_ES_MULTIPLIER / EQUITY
        if nq_bar is not None:
            nq_gross[index] += nq_pos * (nq_bar.close - prev_nq_px) * RV02_NQ_MULTIPLIER / EQUITY
        es_usd = es_pos * (exit_es - entry_es_px) * RV02_ES_MULTIPLIER
        nq_usd = nq_pos * (exit_nq - entry_nq_px) * RV02_NQ_MULTIPLIER
        trades.append(
            ClosedTrade(
                side=es_pos,
                entry_price=entry_es_px,
                exit_price=exit_es,
                pnl_ticks=(es_usd + nq_usd) / 12.50,
                reason=reason,
            )
        )
        es_pos = 0.0
        nq_pos = 0.0

    for index, bar in enumerate(prepared.bars):
        session = "rth" if prepared.rth[index] else "eth"
        nq_bar = ctx.nq_bars.get(bar.ts_ns)
        es_markets.append(_market(bar, prepared, index, session))
        nq_markets.append(_market(nq_bar, prepared, index, session) if nq_bar is not None else _empty_market(session))
        session_day = prepared.session_dates[index]
        if prepared.breaks[index]:
            if es_pos != 0.0:
                flatten_gap(index, bar, nq_bar, "break")
            pending_es = 0.0
            pending_nq = 0.0
            es_positions[index] = 0.0
            nq_positions[index] = 0.0
            prev_es = bar.close
            if nq_bar is not None:
                prev_nq_px = nq_bar.close
            continue
        if pending_es != 0.0 and es_pos == 0.0 and nq_bar is not None:
            es_adv = causal_session_adv(prepared.bars, prepared.rth, index)
            nq_adv = max(nq_bar.volume, 1.0)
            if trade_through_fill(side=pending_es, limit=pending_limit_es, bar=bar, average_volume=es_adv) and trade_through_fill(
                side=pending_nq, limit=pending_limit_nq, bar=nq_bar, average_volume=nq_adv
            ):
                es_pos = pending_es
                nq_pos = pending_nq
                entry_es_px = pending_limit_es
                entry_nq_px = pending_limit_nq
                entry_ns = bar.ts_ns
                prev_es = pending_limit_es
                prev_nq_px = pending_limit_nq
            pending_es = 0.0
            pending_nq = 0.0
        if es_pos != 0.0:
            reason = ""
            if nq_bar is not None and ref_es > 0.0 and ref_nq > 0.0:
                live_rel = ((bar.close / ref_es - 1.0) - (nq_bar.close / ref_nq - 1.0)) * 100.0
                if entry_rel > 0.0:
                    if live_rel <= RV02_TARGET_FILL * entry_rel:
                        reason = "target"
                    elif live_rel >= RV02_STOP_EXTEND * entry_rel:
                        reason = "stop"
                elif entry_rel < 0.0:
                    if live_rel >= RV02_TARGET_FILL * entry_rel:
                        reason = "target"
                    elif live_rel <= RV02_STOP_EXTEND * entry_rel:
                        reason = "stop"
            if not reason and bar.ts_ns >= entry_ns + RV02_TIME_STOP_NS:
                reason = "time_stop"
            if not reason and index == last_rth.get(session_day):
                reason = "session_end"
            if reason:
                flatten_gap(index, bar, nq_bar, reason)
            else:
                es_gross[index] = es_pos * (bar.close - prev_es) * RV02_ES_MULTIPLIER / EQUITY
                if nq_bar is not None:
                    nq_gross[index] = nq_pos * (nq_bar.close - prev_nq_px) * RV02_NQ_MULTIPLIER / EQUITY
            es_positions[index] = es_pos
            nq_positions[index] = nq_pos
            prev_es = bar.close
            if nq_bar is not None:
                prev_nq_px = nq_bar.close
            continue
        if (
            index == first_rth.get(session_day)
            and es_pos == 0.0
            and pending_es == 0.0
            and nq_bar is not None
            and session_day in prev_by_session
        ):
            ref_es, ref_nq = prev_by_session[session_day]
            nq_open_session = nq_sessions.get(session_day)
            if ref_es > 0.0 and ref_nq > 0.0 and nq_open_session is not None:
                es_gap = (bar.open / ref_es - 1.0) * 100.0
                nq_gap = (nq_open_session.open / ref_nq - 1.0) * 100.0
                rel = es_gap - nq_gap
                if abs(rel) > RV02_REL_GAP_PCT:
                    nq_qty = _nq_qty(bar.close, nq_bar.close)
                    if rel > 0.0:
                        pending_es = -1.0
                        pending_nq = nq_qty
                    else:
                        pending_es = 1.0
                        pending_nq = -nq_qty
                    pending_limit_es = bar.close
                    pending_limit_nq = nq_bar.close
                    entry_rel = rel
        es_positions[index] = es_pos
        nq_positions[index] = nq_pos
        prev_es = bar.close
        if nq_bar is not None:
            prev_nq_px = nq_bar.close
    executed = ExecutionResult(
        gross=tuple(es_g + nq_g for es_g, nq_g in zip(es_gross, nq_gross, strict=True)),
        positions=tuple(es_positions),
        markets=tuple(es_markets),
        trades=tuple(trades),
        signals=tuple(0.0 for _ in prepared.bars),
    )
    return executed, _cost_pair(es_gross, es_positions, es_markets, nq_gross, nq_positions, nq_markets)


def _ratio_stats(
    prepared: PreparedTape,
    ctx: FinalCycleContext,
) -> dict[date, tuple[float, float]]:
    es_sessions = rth_sessions(prepared.bars)
    nq_sessions = {item.session: item.close for item in rth_sessions(ctx.nq.bars)}
    es_close = {item.session: item.close for item in es_sessions}
    common = sorted(set(es_close) & set(nq_sessions))
    ratios = [es_close[day] / nq_sessions[day] for day in common]
    stats: dict[date, tuple[float, float]] = {}
    for index, day in enumerate(common):
        if index < RV01_LOOKBACK_SESSIONS:
            continue
        window = ratios[index - RV01_LOOKBACK_SESSIONS : index]
        mean = sum(window) / float(len(window))
        var = sum((item - mean) ** 2 for item in window) / float(len(window) - 1)
        if var <= 0.0:
            continue
        stats[day] = (mean, var**0.5)
    return stats


def _ratio_z(bar: ResearchBar, nq_px: float | None, fitted: tuple[float, float] | None) -> float | None:
    if nq_px is None or nq_px == 0.0 or fitted is None:
        return None
    mean, std = fitted
    if std <= 0.0:
        return None
    return (bar.close / nq_px - mean) / std


def _nq_qty(es_px: float, nq_px: float) -> float:
    if nq_px <= 0.0:
        return 1.0
    return max(1.0, (RV02_ES_MULTIPLIER * es_px) / (RV02_NQ_MULTIPLIER * nq_px))


def _first_rth_index(prepared: PreparedTape) -> dict[date, int]:
    first: dict[date, int] = {}
    for index, (session, is_rth) in enumerate(zip(prepared.session_dates, prepared.rth, strict=True)):
        if is_rth:
            first.setdefault(session, index)
    return first


def _last_rth_index(prepared: PreparedTape) -> dict[date, int]:
    last: dict[date, int] = {}
    for index, (session, is_rth) in enumerate(zip(prepared.session_dates, prepared.rth, strict=True)):
        if is_rth:
            last[session] = index
    return last


def _market(bar: ResearchBar, prepared: PreparedTape, index: int, session: str) -> MarketSnapshot:
    return MarketSnapshot(
        volume=max(bar.volume, 1.0),
        average_volume=causal_session_adv(prepared.bars, prepared.rth, index),
        volatility_price=bar_volatility_price(bar),
        session=session,
    )


def _empty_market(session: str) -> MarketSnapshot:
    return MarketSnapshot(volume=1.0, average_volume=1.0, volatility_price=0.0, session=session)


def _cost_es(executed: ExecutionResult) -> CostedSeries:
    return apply_costs(
        gross_returns=executed.gross,
        positions=executed.positions,
        equity=EQUITY,
        spec="ES",
        markets=executed.markets,
    )


def _cost_pair(
    es_gross: Sequence[float],
    es_pos: Sequence[float],
    es_markets: Sequence[MarketSnapshot],
    nq_gross: Sequence[float],
    nq_pos: Sequence[float],
    nq_markets: Sequence[MarketSnapshot],
) -> CostedSeries:
    es_costed = apply_costs(
        gross_returns=es_gross,
        positions=es_pos,
        equity=EQUITY,
        spec="ES",
        markets=es_markets,
    )
    nq_costed = apply_costs(
        gross_returns=nq_gross,
        positions=nq_pos,
        equity=EQUITY,
        spec="NQ",
        markets=nq_markets,
    )
    return CostedSeries(
        net_returns=tuple(a + b for a, b in zip(es_costed.net_returns, nq_costed.net_returns, strict=True)),
        gross_returns=tuple(a + b for a, b in zip(es_costed.gross_returns, nq_costed.gross_returns, strict=True)),
        costs_usd=tuple(a + b for a, b in zip(es_costed.costs_usd, nq_costed.costs_usd, strict=True)),
        provenance=es_costed.provenance,
        commission_usd=tuple(a + b for a, b in zip(es_costed.commission_usd, nq_costed.commission_usd, strict=True)),
        half_spread_usd=tuple(a + b for a, b in zip(es_costed.half_spread_usd, nq_costed.half_spread_usd, strict=True)),
        slippage_usd=tuple(a + b for a, b in zip(es_costed.slippage_usd, nq_costed.slippage_usd, strict=True)),
        impact_usd=tuple(a + b for a, b in zip(es_costed.impact_usd, nq_costed.impact_usd, strict=True)),
    )
