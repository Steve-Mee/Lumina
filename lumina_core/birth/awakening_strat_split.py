"""G2: per-phase 60/40 splitter. Not a chronological tail cut."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.birth.awakening_occupancy_tape import (
    OccupancyProtocolError,
    assert_gen_counts_balanced,
    count_generator_labels,
)

STRAT_HOLD_PCT = 0.40  # applied INSIDE each phase block
STRAT_TRAIN_PCT = 0.60  # per-block cut 0.60
SPLITTER_NAME = "per_phase_60_40"
MIN_BLOCK_LEN = 5


class StratProtocolError(RuntimeError):
    """AWAKENING_STRATIFIED_SPLIT protocol crime (fail-closed)."""


@dataclass(slots=True)
class StratSplit:
    train: list[dict[str, Any]]
    holdout: list[dict[str, Any]]
    train_idx: list[int]
    hold_idx: list[int]
    train_phases: list[str]
    hold_phases: list[str]
    train_gen: dict[str, int]
    hold_gen: dict[str, int]


def phase_runs(gen_phase: list[str]) -> list[tuple[int, int, str]]:
    """Contiguous runs of gen_phase as half-open [start, end)."""
    if not gen_phase:
        return []
    runs: list[tuple[int, int, str]] = []
    start = 0
    current = str(gen_phase[0])
    for i in range(1, len(gen_phase)):
        label = str(gen_phase[i])
        if label != current:
            runs.append((start, i, current))
            start = i
            current = label
    runs.append((start, len(gen_phase), current))
    return runs


def assert_split_gen_balanced(phases: list[str], side: str) -> dict[str, int]:
    """gen counts per split n/3 ± 2 — TRAIN and HOLDOUT each."""
    counts = count_generator_labels(list(phases))
    try:
        assert_gen_counts_balanced(counts)
    except OccupancyProtocolError as exc:
        raise StratProtocolError(f"S_MISSING: {side} gen counts not n/3 ± 2 ({exc})") from exc
    return counts


def split_per_phase_60_40(
    ticks: list[dict[str, Any]],
    gen_phase: list[str],
    *,
    train_pct: float = STRAT_TRAIN_PCT,
) -> StratSplit:
    """First 60% of each contiguous phase block → train; last 40% → holdout. no shuffle."""
    if len(ticks) != len(gen_phase):
        raise StratProtocolError("S_MISSING: ticks/phase length mismatch")
    if abs(float(train_pct) - 0.60) > 1e-12:
        raise StratProtocolError("S_MISSING: per-block cut must be 0.60")
    train: list[dict[str, Any]] = []
    hold: list[dict[str, Any]] = []
    train_idx: list[int] = []
    hold_idx: list[int] = []
    train_ph: list[str] = []
    hold_ph: list[str] = []
    last_train = -1
    last_hold = -1
    for start, end, _label in phase_runs(gen_phase):
        length = end - start
        if length < MIN_BLOCK_LEN:
            raise StratProtocolError(f"S_MISSING: phase block L={length} < {MIN_BLOCK_LEN}")
        cut = int(length * 0.60)  # per-block cut 0.60
        if not (0 < cut < length):
            raise StratProtocolError("S_MISSING: cut not interior to block")
        for i in range(start, start + cut):
            if i <= last_train:
                raise StratProtocolError("S_MISSING: train order broken (no shuffle)")
            train.append(ticks[i])
            train_idx.append(i)
            train_ph.append(str(gen_phase[i]))
            last_train = i
        for i in range(start + cut, end):
            if i <= last_hold:
                raise StratProtocolError("S_MISSING: holdout order broken (no shuffle)")
            hold.append(ticks[i])
            hold_idx.append(i)
            hold_ph.append(str(gen_phase[i]))
            last_hold = i
    if not train or not hold:
        raise StratProtocolError("S_MISSING: empty train or holdout after per-phase cut")
    return StratSplit(
        train=train,
        holdout=hold,
        train_idx=train_idx,
        hold_idx=hold_idx,
        train_phases=train_ph,
        hold_phases=hold_ph,
        train_gen=assert_split_gen_balanced(train_ph, "TRAIN"),
        hold_gen=assert_split_gen_balanced(hold_ph, "HOLDOUT"),
    )


__all__ = [
    "SPLITTER_NAME",
    "STRAT_HOLD_PCT",
    "STRAT_TRAIN_PCT",
    "StratProtocolError",
    "StratSplit",
    "assert_split_gen_balanced",
    "phase_runs",
    "split_per_phase_60_40",
]
