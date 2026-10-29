"""Mandatory positive control: planted edge of known size on the real tape.

A session-direction lookahead on RTH MES/MNQ must be detected by the same
Validation Gate path. A shuffled-direction null must not be detected.
The research cycle fails closed if the positive control is not detected.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence

from lumina_research.cycles.atr import ATR_N_SESSIONS, causal_session_atr
from lumina_research.cycles.daily import daily_net_tape, unique_sessions
from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.execution import ExecutionResult, run_execution
from lumina_research.cycles.geometry import require_geometry
from lumina_research.cycles.null_model import (
    NULL_EMBARGO,
    default_block_seeds,
    default_null_seeds,
    drift_aware_null_signals,
    majority_a2_cap,
    max_a2_hits,
    remap_session_net,
    session_open_close,
    signal_map_by_session,
    week_block_shuffle_signals,
)
from lumina_research.cycles.p2_cycle import market_series
from lumina_research.cycles.prepare import PreparedTape
from lumina_research.validation.cost_model import MarketSnapshot, apply_costs
from lumina_research.validation.pipeline import CandidateEvaluation, evaluate_candidate
from lumina_research.validation.static_rules import STATIC_POSITIVE_SHARE_MIN, structural_decay
from lumina_research.validation.trial_registry import TrialRegistry

Tape = tuple[tuple[float, ...], tuple[float, ...], tuple[MarketSnapshot, ...]]
# Pre-registered 2026-10-29 (Steve OK). 1:1 limit-move ceiling so 1m noise cannot
# clip the session-OC known size. Catalog templates keep their own geometry.
CONTROL_TARGET_TICKS = 20_000
CONTROL_STOP_TICKS = 20_000
CONTROL_TIME_STOP_BARS = 2_000
CONTROL_SESSION_FILTER = "rth"
CONTROL_ATR_MULTIPLE = 1.5
CONTROL_ATR_SESSIONS = ATR_N_SESSIONS
PLANTED_HORIZON_NOTE = (
    "Planted edge: at the first RTH bar of each session, the control knows the "
    "sign of that session's last-RTH-close minus first-RTH-open (unadjusted). "
    "It holds that direction until RTH close (session flatten, C10). Brackets "
    "are 1:1 20000/20000 ticks (CME 20% limit-move ceiling; not an 8-tick clip) "
    "so a shuffled 50% null is not a 2R artefact. time_stop_bars=2000 cannot "
    "fire inside one RTH session. Four-leg costs unchanged. Known size is the "
    "session RTH open-to-close move minus costs."
)


class PositiveControlFailed(RuntimeError):
    """The pipeline did not detect the planted edge; the cycle must not continue."""

    def __init__(self, message: str, report: ControlReport | None = None) -> None:
        super().__init__(message)
        self.report = report


@dataclass(frozen=True, slots=True)
class ControlOutcome:
    name: str
    detected: bool
    median_oos: float
    pct_positive: float
    dsr: float
    passed_gate: bool
    n_days: int
    n_trials: int
    note: str


@dataclass(frozen=True, slots=True)
class NullSeedOutcome:
    seed: int
    kind: str
    detected: bool
    median_oos: float
    pct_positive: float
    dsr: float
    n_trials: int


@dataclass(frozen=True, slots=True)
class NullAudit:
    n_seeds: int
    n_a2: int
    a2_share: float
    max_a2: int
    ten_pct_cap: int
    reliable: bool
    a2_within_ten_pct: bool
    median_of_medians: float
    planted_beats_null: bool
    drift_seeds: tuple[NullSeedOutcome, ...]
    block_seeds: tuple[NullSeedOutcome, ...]
    n_trials_this_root: int


@dataclass(frozen=True, slots=True)
class ControlReport:
    positive: ControlOutcome
    null: ControlOutcome
    accepted: bool
    null_audit: NullAudit | None = None


def rth_session_direction(
    bars: Sequence[ResearchBar],
    session_dates: Sequence[date],
    rth: Sequence[bool],
) -> tuple[float, ...]:
    first: dict[date, int] = {}
    last: dict[date, int] = {}
    for index, session in enumerate(session_dates):
        if not rth[index]:
            continue
        first.setdefault(session, index)
        last[session] = index
    signals = [0.0] * len(bars)
    for session, start in first.items():
        end = last[session]
        move = bars[end].close - bars[start].open
        if move > 0.0:
            signals[start] = 1.0
        elif move < 0.0:
            signals[start] = -1.0
    return tuple(signals)


def shuffle_signals(signals: Sequence[float], *, seed: int) -> tuple[float, ...]:
    idx = [index for index, value in enumerate(signals) if value != 0.0]
    values = [signals[index] for index in idx]
    rng = random.Random(seed)
    rng.shuffle(values)
    out = [0.0] * len(signals)
    for index, value in zip(idx, values, strict=True):
        out[index] = value
    return tuple(out)


def build_null_signals(
    planted: Sequence[float],
    *,
    seed: int,
    session_dates: Sequence[date],
    oc_by_date: Mapping[date, float],
    is_size: int,
    oos_size: int,
    embargo: int = NULL_EMBARGO,
) -> tuple[float, ...]:
    """Patch point for the identity-null attack. Production is drift-aware."""
    return drift_aware_null_signals(
        planted,
        seed=seed,
        session_dates=session_dates,
        oc_by_date=oc_by_date,
        is_size=is_size,
        oos_size=oos_size,
        embargo=embargo,
    )


def execute_control(
    prepared: PreparedTape,
    signals: Sequence[float],
    *,
    root: str,
    geometry_mode: str = "unclipped",
    atr_points: Sequence[float] | None = None,
) -> ExecutionResult:
    if geometry_mode == "atr":
        geometry = require_geometry(root=root, target_ticks=1, stop_ticks=1)
        series = atr_points
        if series is None:
            series = causal_session_atr(
                prepared.bars,
                prepared.session_dates,
                prepared.rth,
                n_sessions=CONTROL_ATR_SESSIONS,
            )
        return run_execution(
            bars=prepared.bars,
            signals=signals,
            geometry=geometry,
            breaks=prepared.breaks,
            rth=prepared.rth,
            session_dates=prepared.session_dates,
            session_filter=CONTROL_SESSION_FILTER,
            time_stop_bars=CONTROL_TIME_STOP_BARS,
            session_end_flatten=True,
            atr_points=series,
            target_atr=CONTROL_ATR_MULTIPLE,
            stop_atr=CONTROL_ATR_MULTIPLE,
        )
    geometry = require_geometry(
        root=root,
        target_ticks=CONTROL_TARGET_TICKS,
        stop_ticks=CONTROL_STOP_TICKS,
    )
    return run_execution(
        bars=prepared.bars,
        signals=signals,
        geometry=geometry,
        breaks=prepared.breaks,
        rth=prepared.rth,
        session_dates=prepared.session_dates,
        session_filter=CONTROL_SESSION_FILTER,
        time_stop_bars=CONTROL_TIME_STOP_BARS,
        session_end_flatten=True,
    )


def _costed_daily(
    prepared: PreparedTape,
    executed: ExecutionResult,
    root: str,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    costed = apply_costs(
        gross_returns=executed.gross,
        positions=executed.positions,
        equity=100_000.0,
        spec=root,
        markets=executed.markets,
    )
    daily_gross = daily_net_tape(executed.gross, prepared.session_dates)[0]
    daily_net = daily_net_tape(costed.net_returns, prepared.session_dates)[0]
    return daily_gross, daily_net


def _from_daily_net(daily_net: Sequence[float]) -> Tape:
    n = len(daily_net)
    if n < 1:
        raise PositiveControlFailed("empty daily control tape")
    positions = tuple(0.0 for _ in range(n))
    markets = tuple(MarketSnapshot(volume=1.0, average_volume=1.0, volatility_price=0.0) for _ in range(n))
    return tuple(float(item) for item in daily_net), positions, markets


def _seed_outcome(seed: int, kind: str, evaluation: CandidateEvaluation, detected: bool) -> NullSeedOutcome:
    return NullSeedOutcome(
        seed=int(seed),
        kind=kind,
        detected=bool(detected),
        median_oos=float(evaluation.report.median_oos_after_costs),
        pct_positive=float(evaluation.report.oos_distribution.pct_positive),
        dsr=float(evaluation.report.dsr.probability),
        n_trials=int(evaluation.report.dsr.n_trials),
    )


def _median(values: Sequence[float]) -> float:
    ordered = sorted(float(item) for item in values)
    count = len(ordered)
    mid = count // 2
    if count % 2 == 1:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _detected(evaluation: CandidateEvaluation, *, null_median: float | None) -> bool:
    report = evaluation.report
    median = report.median_oos_after_costs
    pct = report.oos_distribution.pct_positive
    decay = structural_decay(report.oos_distribution.values)
    if not math.isfinite(median) or not math.isfinite(pct):
        return False
    if median <= 0.0 or pct < STATIC_POSITIVE_SHARE_MIN or decay:
        return False
    if null_median is not None and math.isfinite(null_median) and median <= null_median:
        return False
    return True


def _outcome(name: str, evaluation: CandidateEvaluation, detected: bool, note: str) -> ControlOutcome:
    return ControlOutcome(
        name=name,
        detected=detected,
        median_oos=float(evaluation.report.median_oos_after_costs),
        pct_positive=float(evaluation.report.oos_distribution.pct_positive),
        dsr=float(evaluation.report.dsr.probability),
        passed_gate=bool(evaluation.passed),
        n_days=int(evaluation.results.n_days),
        n_trials=int(evaluation.report.dsr.n_trials),
        note=note,
    )


def run_controls(
    *,
    prepared: Mapping[str, PreparedTape],
    registry: TrialRegistry,
    audit_path: Path,
    is_size: int,
    oos_size: int,
    market_returns: Sequence[float],
    n_days: int,
    null_seeds: Sequence[int] | None = None,
    block_seeds: Sequence[int] | None = None,
    embargo: int = NULL_EMBARGO,
    fail_closed: bool = True,
    geometry_mode: str = "unclipped",
) -> ControlReport:
    tape = prepared.get("MES") or next(iter(prepared.values()))
    root = tape.instrument
    planted = rth_session_direction(tape.bars, tape.session_dates, tape.rth)
    oc_by_date = session_open_close(tape.bars, tape.session_dates, tape.rth)
    seeds = tuple(null_seeds) if null_seeds is not None else default_null_seeds()
    extra = tuple(block_seeds) if block_seeds is not None else default_block_seeds()
    if not seeds:
        raise PositiveControlFailed("null seeds must be pre-registered and non-empty")
    n_before = int(registry.n_trials)
    atr_series = None
    if geometry_mode == "atr":
        atr_series = causal_session_atr(
            tape.bars,
            tape.session_dates,
            tape.rth,
            n_sessions=CONTROL_ATR_SESSIONS,
        )
    pos_exec = execute_control(tape, planted, root=root, geometry_mode=geometry_mode, atr_points=atr_series)
    daily_gross, daily_net = _costed_daily(tape, pos_exec, root=root)
    sessions = unique_sessions(tape.session_dates)
    planted_map = signal_map_by_session(planted, tape.session_dates)
    pos_tape = _from_daily_net(daily_net)
    remap_ok = geometry_mode == "unclipped"
    drift_dailies: list[tuple[float, ...]] = []
    for seed in seeds:
        null_signals = build_null_signals(
            planted,
            seed=int(seed),
            session_dates=tape.session_dates,
            oc_by_date=oc_by_date,
            is_size=is_size,
            oos_size=oos_size,
            embargo=embargo,
        )
        if remap_ok:
            null_map = signal_map_by_session(null_signals, tape.session_dates)
            drift_dailies.append(
                remap_session_net(
                    daily_gross=daily_gross,
                    daily_net=daily_net,
                    sessions=sessions,
                    planted_signs=planted_map,
                    null_signs=null_map,
                )
            )
        else:
            null_exec = execute_control(
                tape,
                null_signals,
                root=root,
                geometry_mode=geometry_mode,
                atr_points=atr_series,
            )
            _gross, null_daily = _costed_daily(tape, null_exec, root=root)
            drift_dailies.append(null_daily)
    try:
        planted_eval = evaluate_candidate(
            agent_id="positive_control",
            config_id="control-planted-session",
            gross_returns=pos_tape[0],
            positions=pos_tape[1],
            markets=pos_tape[2],
            spec=root,
            registry=registry,
            peer_net_returns=tuple(drift_dailies),
            audit_path=audit_path,
            is_size=is_size,
            oos_size=oos_size,
            has_fit_step=False,
            market_returns=market_returns,
            n_days=n_days,
        )
        drift_rows: list[tuple[int, CandidateEvaluation, bool]] = []
        for seed, daily in zip(seeds, drift_dailies, strict=True):
            null_eval = evaluate_candidate(
                agent_id="positive_control",
                config_id=f"control-null-drift-{seed}",
                gross_returns=daily,
                positions=pos_tape[1],
                markets=pos_tape[2],
                spec=root,
                registry=registry,
                peer_net_returns=(pos_tape[0],),
                audit_path=audit_path,
                is_size=is_size,
                oos_size=oos_size,
                has_fit_step=False,
                market_returns=market_returns,
                n_days=n_days,
            )
            drift_rows.append((int(seed), null_eval, _detected(null_eval, null_median=None)))
        block_rows: list[tuple[int, CandidateEvaluation, bool]] = []
        for seed in extra:
            block_signals = week_block_shuffle_signals(planted, tape.session_dates, seed=int(seed))
            if remap_ok:
                block_map = signal_map_by_session(block_signals, tape.session_dates)
                block_daily = remap_session_net(
                    daily_gross=daily_gross,
                    daily_net=daily_net,
                    sessions=sessions,
                    planted_signs=planted_map,
                    null_signs=block_map,
                )
            else:
                block_exec = execute_control(
                    tape,
                    block_signals,
                    root=root,
                    geometry_mode=geometry_mode,
                    atr_points=atr_series,
                )
                _bg, block_daily = _costed_daily(tape, block_exec, root=root)
            block_eval = evaluate_candidate(
                agent_id="positive_control",
                config_id=f"control-null-block-{seed}",
                gross_returns=block_daily,
                positions=pos_tape[1],
                markets=pos_tape[2],
                spec=root,
                registry=registry,
                peer_net_returns=(pos_tape[0],),
                audit_path=audit_path,
                is_size=is_size,
                oos_size=oos_size,
                has_fit_step=False,
                market_returns=market_returns,
                n_days=n_days,
            )
            block_rows.append((int(seed), block_eval, _detected(block_eval, null_median=None)))
    except PositiveControlFailed:
        raise
    except Exception as exc:
        raise PositiveControlFailed(f"control evaluation failed: {exc}") from exc
    medians = tuple(float(row[1].report.median_oos_after_costs) for row in drift_rows)
    finite = tuple(value for value in medians if math.isfinite(value))
    median_of_medians = _median(finite) if finite else math.nan
    n_a2 = sum(1 for row in drift_rows if row[2])
    ten_pct_cap = max_a2_hits(len(seeds))
    max_hits = majority_a2_cap(len(seeds))
    reliable = n_a2 <= max_hits
    within_ten = n_a2 <= ten_pct_cap
    pos_detected = _detected(planted_eval, null_median=median_of_medians)
    planted_beats = (
        math.isfinite(float(planted_eval.report.median_oos_after_costs))
        and math.isfinite(median_of_medians)
        and float(planted_eval.report.median_oos_after_costs) > median_of_medians
    )
    n_trials_root = int(registry.n_trials) - n_before
    audit = NullAudit(
        n_seeds=len(seeds),
        n_a2=n_a2,
        a2_share=float(n_a2) / float(len(seeds)),
        max_a2=max_hits,
        ten_pct_cap=ten_pct_cap,
        reliable=reliable,
        a2_within_ten_pct=within_ten,
        median_of_medians=float(median_of_medians),
        planted_beats_null=planted_beats,
        drift_seeds=tuple(_seed_outcome(seed, "drift", evaluation, hit) for seed, evaluation, hit in drift_rows),
        block_seeds=tuple(_seed_outcome(seed, "block", evaluation, hit) for seed, evaluation, hit in block_rows),
        n_trials_this_root=n_trials_root,
    )
    representative = drift_rows[0][1]
    report = ControlReport(
        positive=_outcome("planted_session_direction", planted_eval, pos_detected, PLANTED_HORIZON_NOTE),
        null=_outcome(
            "null_drift_aware_multiseed",
            representative,
            not reliable,
            (
                f"Drift-aware null, {len(seeds)} seeds, A2 hits {n_a2}/{len(seeds)} "
                f"(fail-closed cap {max_hits}, 10% diagnostic {ten_pct_cap}); "
                f"median-of-medians {median_of_medians:.6g}."
            ),
        ),
        accepted=pos_detected and reliable and planted_beats,
        null_audit=audit,
    )
    if fail_closed and not report.accepted:
        raise PositiveControlFailed(
            "positive control was not detected or the null control looked like an edge",
            report=report,
        )
    return report


def run_controls_per_instrument(
    *,
    prepared: Mapping[str, PreparedTape],
    registry: TrialRegistry,
    audit_path: Path,
    is_size: int,
    oos_size: int,
    n_days_by_root: Mapping[str, int] | None = None,
    geometry_mode: str = "unclipped",
    block_seeds: Sequence[int] | None = None,
) -> tuple[dict[str, ControlReport], dict[str, str]]:
    """D13 on each tape. A failed root does not stop a passing sibling."""
    accepted: dict[str, ControlReport] = {}
    failed: dict[str, str] = {}
    for root in sorted(prepared):
        tape = prepared[root]
        days = len(unique_sessions(tape.session_dates))
        if n_days_by_root is not None and root in n_days_by_root:
            days = int(n_days_by_root[root])
        try:
            accepted[root] = run_controls(
                prepared={root: tape},
                registry=registry,
                audit_path=audit_path,
                is_size=is_size,
                oos_size=oos_size,
                market_returns=market_series(tape),
                n_days=days,
                geometry_mode=geometry_mode,
                block_seeds=block_seeds,
            )
        except PositiveControlFailed as exc:
            failed[root] = str(exc)
    return accepted, failed
