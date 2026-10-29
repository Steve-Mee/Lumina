"""P2 real-data path: prepare tapes, daily resample, holdout eval. No orders."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from lumina_research.cycles.atr import causal_session_atr
from lumina_research.cycles.catalog import HypothesisSpec
from lumina_research.cycles.daily import bar_market_returns, daily_market_returns, daily_net_tape, unique_sessions
from lumina_research.cycles.data import LoadedTape, MIN_BARS
from lumina_research.cycles.diagnostics import ConfigDiagnostics, from_trades
from lumina_research.cycles.execution import ClosedTrade, run_execution
from lumina_research.cycles.geometry import require_geometry
from lumina_research.cycles.holdout import P2_HOLDOUT_START_NS, P2_PIN_MIN_BARS, access_bars
from lumina_research.cycles.prepare import PreparedTape, prepare_tape
from lumina_research.cycles.roll_verify import require_friday_roll
from lumina_research.cycles.strategies import Tape, simulate_full
from lumina_research.cycles.wf_sizes import TARGET_OOS_WINDOWS, walk_forward_sizes
from lumina_research.validation.cost_model import apply_costs
from lumina_research.validation.metrics import annualized_sharpe
from lumina_research.validation.types import RegimeSnapshot

DAILY_RESAMPLE_MIN_BARS = P2_PIN_MIN_BARS
_MATERIALIZE_CACHE: dict[tuple[object, ...], Tape] = {}
_DIAG_CACHE: dict[str, ConfigDiagnostics] = {}
_MARKET_CACHE: dict[str, tuple[float, ...]] = {}


@dataclass(frozen=True, slots=True)
class HoldoutEvalRow:
    config_id: str
    family: str
    instrument: str
    n_days: int
    mean_net: float
    sharpe: float
    n_positive_days: int
    max_drawdown: float


def pin_tape(tape: LoadedTape) -> LoadedTape:
    start = P2_HOLDOUT_START_NS if len(tape.bars) >= P2_PIN_MIN_BARS else None
    if start is None:
        return tape
    return LoadedTape(
        instrument=tape.instrument,
        bar_size=tape.bar_size,
        path=tape.path,
        bars=tape.bars,
        holdout_start_ns=start,
    )


def prepare_for_purpose(tape: LoadedTape, *, purpose: str) -> PreparedTape:
    pinned = pin_tape(tape)
    bars = access_bars(pinned, purpose=purpose, pinned_start_ns=pinned.holdout_start_ns)
    if len(bars) < MIN_BARS:
        raise ValueError(f"{tape.instrument} {purpose} split is shorter than {MIN_BARS} bars")
    return prepare_tape(tape.instrument, bars)


def with_walk_forward_sizes(
    specs: tuple[HypothesisSpec, ...], prepared: Mapping[str, PreparedTape]
) -> tuple[HypothesisSpec, ...]:
    counts = [len(unique_sessions(tape.session_dates)) for tape in prepared.values()]
    n_days = min(counts) if counts else 0
    if n_days < 40:
        return specs
    is_size, oos_size, _formed = walk_forward_sizes(n_days)
    return tuple(replace(spec, is_size=is_size, oos_size=oos_size) for spec in specs)


def session_day_count(prepared: Mapping[str, PreparedTape]) -> int:
    counts = [len(unique_sessions(tape.session_dates)) for tape in prepared.values()]
    return min(counts) if counts else 0


def clear_materialize_cache() -> None:
    _MATERIALIZE_CACHE.clear()
    _DIAG_CACHE.clear()
    _MARKET_CACHE.clear()


def market_series(prepared: PreparedTape) -> tuple[float, ...]:
    if len(prepared.bars) < DAILY_RESAMPLE_MIN_BARS:
        return bar_market_returns(prepared.bars, prepared.breaks)
    return daily_market_returns(prepared.bars, prepared.session_dates)


def cached_diagnostics(config_id: str) -> ConfigDiagnostics | None:
    return _DIAG_CACHE.get(config_id)


def materialize_spec(spec: HypothesisSpec, prepared: PreparedTape) -> Tape:
    require_friday_roll()
    key = (
        spec.config_id,
        prepared.instrument,
        prepared.bars[0].ts_ns if prepared.bars else 0,
        prepared.bars[-1].ts_ns if prepared.bars else 0,
        len(prepared.bars),
        prepared.dropped,
        prepared.n_breaks,
        spec.session_filter,
        spec.time_stop_bars,
        spec.threshold,
        spec.lookback,
        spec.target_atr,
        spec.stop_atr,
        spec.disable_brackets,
        spec.atr_n_sessions,
    )
    hit = _MATERIALIZE_CACHE.get(key)
    if hit is not None:
        return hit
    geometry = require_geometry(root=spec.instrument, target_ticks=spec.target_ticks, stop_ticks=spec.stop_ticks)
    atr_points = None
    if spec.target_atr is not None or spec.disable_brackets:
        atr_points = causal_session_atr(
            prepared.bars,
            prepared.session_dates,
            prepared.rth,
            n_sessions=spec.atr_n_sessions,
        )
    executed = simulate_full(
        family=spec.family,
        bars=prepared.bars,
        geometry=geometry,
        lookback=spec.lookback,
        threshold=spec.threshold,
        mode=spec.mode,
        breaks=prepared.breaks,
        session_dates=prepared.session_dates,
        rth=prepared.rth,
        quiet=prepared.quiet,
        signal_bars=prepared.signal_bars,
        session_filter=spec.session_filter,
        time_stop_bars=spec.time_stop_bars,
        session_end_flatten=spec.session_end_flatten,
        atr_points=atr_points,
        target_atr=spec.target_atr,
        stop_atr=spec.stop_atr,
        disable_brackets=spec.disable_brackets,
    )
    costed = apply_costs(
        gross_returns=executed.gross,
        positions=executed.positions,
        equity=100_000.0,
        spec=spec.instrument,
        markets=executed.markets,
    )
    unbracket_trades: tuple[ClosedTrade, ...] = ()
    one_r_trades: tuple[ClosedTrade, ...] = ()
    if spec.target_atr is not None or spec.disable_brackets:
        unb = run_execution(
            bars=prepared.bars,
            signals=executed.signals,
            geometry=geometry,
            breaks=prepared.breaks,
            rth=prepared.rth,
            session_dates=prepared.session_dates,
            session_filter=spec.session_filter,
            time_stop_bars=60,
            session_end_flatten=True,
            atr_points=atr_points,
            disable_brackets=True,
        )
        unbracket_trades = unb.trades
        if spec.stop_atr is not None and not spec.disable_brackets:
            one = run_execution(
                bars=prepared.bars,
                signals=executed.signals,
                geometry=geometry,
                breaks=prepared.breaks,
                rth=prepared.rth,
                session_dates=prepared.session_dates,
                session_filter=spec.session_filter,
                time_stop_bars=spec.time_stop_bars,
                session_end_flatten=spec.session_end_flatten,
                atr_points=atr_points,
                target_atr=spec.stop_atr,
                stop_atr=spec.stop_atr,
            )
            one_r_trades = one.trades
    _DIAG_CACHE[spec.config_id] = from_trades(
        trades=executed.trades,
        geometry=geometry,
        costed=costed,
        is_sharpes=(),
        oos_sharpes=(),
        regimes=RegimeSnapshot.missing(),
        n_trials=0,
        n_days=len(unique_sessions(prepared.session_dates)),
        pct_positive_oos=float("nan"),
        unbracket_trades=unbracket_trades,
        one_r_trades=one_r_trades,
        unbracket_n_bars=60,
    )
    _MARKET_CACHE[prepared.instrument] = market_series(prepared)
    if len(prepared.bars) < DAILY_RESAMPLE_MIN_BARS:
        built = executed.gross, executed.positions, executed.markets
        _MATERIALIZE_CACHE[key] = built
        return built
    built = daily_net_tape(costed.net_returns, prepared.session_dates)
    _MATERIALIZE_CACHE[key] = built
    return built


def evaluate_holdout(spec: HypothesisSpec, prepared: PreparedTape) -> HoldoutEvalRow:
    tape = materialize_spec(spec, prepared)
    net = tape[0]
    peak = 0.0
    wealth = 0.0
    max_dd = 0.0
    positive = 0
    for value in net:
        wealth += float(value)
        peak = max(peak, wealth)
        max_dd = max(max_dd, peak - wealth)
        if value > 0.0:
            positive += 1
    mean = sum(net) / float(len(net)) if net else 0.0
    return HoldoutEvalRow(
        config_id=spec.config_id,
        family=spec.family,
        instrument=spec.instrument,
        n_days=len(net),
        mean_net=float(mean),
        sharpe=float(annualized_sharpe(net)),
        n_positive_days=positive,
        max_drawdown=float(max_dd),
    )


def window_note(specs: tuple[HypothesisSpec, ...], n_days: int = 0) -> str:
    if not specs:
        return "n/a"
    spec = specs[0]
    days = f"n_days={n_days} " if n_days > 0 else ""
    return (
        f"{days}walk-forward is_size={spec.is_size} oos_size={spec.oos_size} "
        f"target_windows={TARGET_OOS_WINDOWS} units=globex_session_days"
    )
