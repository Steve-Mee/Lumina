"""P2 real-data path: prepare tapes, daily resample, holdout eval. No orders."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from lumina_research.cycles.catalog import HypothesisSpec
from lumina_research.cycles.daily import daily_net_tape, unique_sessions
from lumina_research.cycles.data import LoadedTape, MIN_BARS
from lumina_research.cycles.geometry import require_geometry
from lumina_research.cycles.holdout import P2_HOLDOUT_START_NS, P2_PIN_MIN_BARS, access_bars
from lumina_research.cycles.prepare import PreparedTape, prepare_tape
from lumina_research.cycles.strategies import Tape, simulate
from lumina_research.cycles.wf_sizes import TARGET_OOS_WINDOWS, walk_forward_sizes
from lumina_research.validation.cost_model import apply_costs
from lumina_research.validation.metrics import annualized_sharpe

DAILY_RESAMPLE_MIN_BARS = P2_PIN_MIN_BARS
_MATERIALIZE_CACHE: dict[tuple[object, ...], Tape] = {}


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
    bars = access_bars(pinned, purpose=purpose)
    if len(bars) < MIN_BARS:
        raise ValueError(f"{tape.instrument} {purpose} split is shorter than {MIN_BARS} bars")
    return prepare_tape(tape.instrument, bars)


def with_walk_forward_sizes(specs: tuple[HypothesisSpec, ...], prepared: Mapping[str, PreparedTape]) -> tuple[HypothesisSpec, ...]:
    counts = [len(unique_sessions(tape.session_dates)) for tape in prepared.values()]
    n_days = min(counts) if counts else 0
    if n_days < 40:
        return specs
    is_size, oos_size, _formed = walk_forward_sizes(n_days)
    return tuple(replace(spec, is_size=is_size, oos_size=oos_size) for spec in specs)


def clear_materialize_cache() -> None:
    _MATERIALIZE_CACHE.clear()


def materialize_spec(spec: HypothesisSpec, prepared: PreparedTape) -> Tape:
    key = (
        spec.config_id,
        prepared.instrument,
        prepared.bars[0].ts_ns if prepared.bars else 0,
        prepared.bars[-1].ts_ns if prepared.bars else 0,
        len(prepared.bars),
        prepared.dropped,
        prepared.n_breaks,
    )
    hit = _MATERIALIZE_CACHE.get(key)
    if hit is not None:
        return hit
    geometry = require_geometry(root=spec.instrument, target_ticks=spec.target_ticks, stop_ticks=spec.stop_ticks)
    gross, positions, markets = simulate(
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
    )
    if len(prepared.bars) < DAILY_RESAMPLE_MIN_BARS:
        built = gross, positions, markets
        _MATERIALIZE_CACHE[key] = built
        return built
    costed = apply_costs(
        gross_returns=gross,
        positions=positions,
        equity=100_000.0,
        spec=spec.instrument,
        markets=markets,
    )
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


def window_note(specs: tuple[HypothesisSpec, ...]) -> str:
    if not specs:
        return "n/a"
    spec = specs[0]
    return f"walk-forward is_size={spec.is_size} oos_size={spec.oos_size} target_windows={TARGET_OOS_WINDOWS}"
