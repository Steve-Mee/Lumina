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

from lumina_research.cycles.daily import daily_net_tape, unique_sessions
from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.execution import ExecutionResult, run_execution
from lumina_research.cycles.geometry import require_geometry
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
class ControlReport:
    positive: ControlOutcome
    null: ControlOutcome
    accepted: bool


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


def execute_control(prepared: PreparedTape, signals: Sequence[float], *, root: str) -> ExecutionResult:
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


def _gate_tape(prepared: PreparedTape, executed: ExecutionResult, *, root: str) -> Tape:
    """Session-day net returns. The planted edge is a session-direction hypothesis."""
    costed = apply_costs(
        gross_returns=executed.gross,
        positions=executed.positions,
        equity=100_000.0,
        spec=root,
        markets=executed.markets,
    )
    return daily_net_tape(costed.net_returns, prepared.session_dates)


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
) -> ControlReport:
    tape = prepared.get("MES") or next(iter(prepared.values()))
    root = tape.instrument
    planted = rth_session_direction(tape.bars, tape.session_dates, tape.rth)
    null = shuffle_signals(planted, seed=20261029)
    pos_exec = execute_control(tape, planted, root=root)
    null_exec = execute_control(tape, null, root=root)
    pos_tape = _gate_tape(tape, pos_exec, root=root)
    null_tape = _gate_tape(tape, null_exec, root=root)
    try:
        planted_eval = evaluate_candidate(
            agent_id="positive_control",
            config_id="control-planted-session",
            gross_returns=pos_tape[0],
            positions=pos_tape[1],
            markets=pos_tape[2],
            spec=root,
            registry=registry,
            peer_net_returns=(null_tape[0],),
            audit_path=audit_path,
            is_size=is_size,
            oos_size=oos_size,
            has_fit_step=False,
            market_returns=market_returns,
            n_days=n_days,
        )
        null_eval = evaluate_candidate(
            agent_id="positive_control",
            config_id="control-null-shuffle",
            gross_returns=null_tape[0],
            positions=null_tape[1],
            markets=null_tape[2],
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
    except Exception as exc:
        raise PositiveControlFailed(f"control evaluation failed: {exc}") from exc
    null_detected = _detected(null_eval, null_median=None)
    pos_detected = _detected(planted_eval, null_median=null_eval.report.median_oos_after_costs)
    report = ControlReport(
        positive=_outcome("planted_session_direction", planted_eval, pos_detected, PLANTED_HORIZON_NOTE),
        null=_outcome(
            "null_shuffled_direction",
            null_eval,
            null_detected,
            "Shuffled session signs; no lookahead.",
        ),
        accepted=pos_detected and not null_detected,
    )
    if not report.accepted:
        raise PositiveControlFailed("positive control was not detected or the null control looked like an edge")
    return report


def run_controls_per_instrument(
    *,
    prepared: Mapping[str, PreparedTape],
    registry: TrialRegistry,
    audit_path: Path,
    is_size: int,
    oos_size: int,
    n_days_by_root: Mapping[str, int] | None = None,
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
            )
        except PositiveControlFailed as exc:
            failed[root] = str(exc)
    return accepted, failed
