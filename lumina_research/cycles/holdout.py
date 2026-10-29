"""Fail-closed holdout lock for P2 NT8 1m MES/MNQ tapes.

Last HOLDOUT_MONTHS of calendar time is never used for template selection, first-cycle
ranking, parameter tuning, or Validation Gate calibration. Unknown purposes refuse.
A tape that cannot form a non-empty train AND holdout split also refuses.
Timestamps must be strictly increasing so a shuffled or future-dummy last row cannot
move the lock window. Real P2 NT8 tapes (>= P2_PIN_MIN_BARS) pin 2026-01-29T00:00:00Z.
"""

from __future__ import annotations

from datetime import datetime, timezone

from lumina_research.cycles.data import LoadedTape, ResearchBar

HOLDOUT_MONTHS = 9
HOLDOUT_MONTHS_MIN = 6
HOLDOUT_MONTHS_MAX = 12
NS_PER_DAY = 24 * 3600 * 1_000_000_000
DAYS_PER_MONTH = 30.4375
P2_HOLDOUT_START_UTC = datetime(2026, 1, 29, tzinfo=timezone.utc)
P2_HOLDOUT_START_NS = int(P2_HOLDOUT_START_UTC.timestamp() * 1_000_000_000)
P2_PIN_MIN_BARS = 10_000
LOCKED_PURPOSES: frozenset[str] = frozenset(
    {"selection", "template_selection", "tuning", "calibration", "gate", "first_cycle"}
)
EVAL_PURPOSES: frozenset[str] = frozenset({"evaluation", "holdout_eval"})


class HoldoutLocked(ValueError):
    """Holdout bars were requested for a forbidden purpose, or the split cannot be formed."""


def holdout_ns(months: int = HOLDOUT_MONTHS) -> int:
    if months < HOLDOUT_MONTHS_MIN or months > HOLDOUT_MONTHS_MAX:
        raise HoldoutLocked(f"holdout months must be in [{HOLDOUT_MONTHS_MIN}, {HOLDOUT_MONTHS_MAX}]")
    return int(float(months) * DAYS_PER_MONTH * float(NS_PER_DAY))


def holdout_start_ns(
    bars: tuple[ResearchBar, ...],
    *,
    months: int = HOLDOUT_MONTHS,
    pinned_start_ns: int | None = None,
) -> int:
    if len(bars) < 2:
        raise HoldoutLocked("tape too short to lock a holdout; fail-closed")
    previous = int(bars[0].ts_ns)
    for item in bars[1:]:
        current = int(item.ts_ns)
        if current <= previous:
            raise HoldoutLocked("tape timestamps must be strictly increasing; fail-closed")
        previous = current
    first = int(bars[0].ts_ns)
    last = int(bars[-1].ts_ns)
    start = int(pinned_start_ns) if pinned_start_ns is not None else last - holdout_ns(months)
    if start <= first or start >= last:
        raise HoldoutLocked("tape span cannot form a non-empty train and holdout split; fail-closed")
    train = sum(1 for item in bars if int(item.ts_ns) < start)
    locked = sum(1 for item in bars if int(item.ts_ns) >= start)
    if train < 1 or locked < 1:
        raise HoldoutLocked("holdout split left an empty side; fail-closed")
    return start


def split_holdout(
    bars: tuple[ResearchBar, ...],
    *,
    months: int = HOLDOUT_MONTHS,
    pinned_start_ns: int | None = None,
) -> tuple[tuple[ResearchBar, ...], tuple[ResearchBar, ...], int]:
    start = holdout_start_ns(bars, months=months, pinned_start_ns=pinned_start_ns)
    train = tuple(item for item in bars if int(item.ts_ns) < start)
    locked = tuple(item for item in bars if int(item.ts_ns) >= start)
    return train, locked, start


def access_bars(
    tape: LoadedTape,
    *,
    purpose: str,
    months: int = HOLDOUT_MONTHS,
    pinned_start_ns: int | None = None,
) -> tuple[ResearchBar, ...]:
    """Fail-closed accessor. Selection/tuning/gate see train only. Evaluation sees holdout only."""
    key = purpose.strip().lower()
    pin = pinned_start_ns if pinned_start_ns is not None else _auto_pin(tape)
    train, locked, start = split_holdout(tape.bars, months=months, pinned_start_ns=pin)
    if tape.holdout_start_ns is not None and int(tape.holdout_start_ns) != start:
        raise HoldoutLocked("holdout start drifted from the loaded tape; fail-closed")
    if key in LOCKED_PURPOSES:
        _refuse_if_holdout(train, start=start, purpose=key)
        return train
    if key in EVAL_PURPOSES:
        return locked
    raise HoldoutLocked(f"unknown holdout purpose {purpose!r}; fail-closed")


def _auto_pin(tape: LoadedTape) -> int | None:
    if len(tape.bars) >= P2_PIN_MIN_BARS:
        return P2_HOLDOUT_START_NS
    return None


def assert_not_holdout(ts_ns: int, *, holdout_start: int, purpose: str) -> None:
    key = purpose.strip().lower()
    if key in EVAL_PURPOSES:
        return
    if key not in LOCKED_PURPOSES:
        raise HoldoutLocked(f"unknown holdout purpose {purpose!r}; fail-closed")
    if int(ts_ns) >= int(holdout_start):
        raise HoldoutLocked(f"holdout access refused for purpose {key!r}")


def _refuse_if_holdout(bars: tuple[ResearchBar, ...], *, start: int, purpose: str) -> None:
    for item in bars:
        assert_not_holdout(item.ts_ns, holdout_start=start, purpose=purpose)
