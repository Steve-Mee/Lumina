"""Drift-aware multi-seed null for D13. Pre-registered 2026-10-29.

A permutation of session signs keeps the up/down count. On a tape with
positive drift that imbalance still clears A2. This builder detrends and
balances signs inside each non-overlapping walk-forward partition.
"""

from __future__ import annotations

import math
import random
from datetime import date
from typing import Mapping, Sequence

from lumina_research.cycles.daily import unique_sessions
from lumina_research.cycles.data import ResearchBar

NULL_N_SEEDS = 32
NULL_SEED_BASE = 20261029
NULL_A2_MAX_SHARE = 0.10
NULL_BLOCK_N_SEEDS = 8
NULL_BLOCK_SEED_BASE = 20261129
NULL_EMBARGO = 1


def default_null_seeds() -> tuple[int, ...]:
    return tuple(NULL_SEED_BASE + index for index in range(NULL_N_SEEDS))


def default_block_seeds() -> tuple[int, ...]:
    return tuple(NULL_BLOCK_SEED_BASE + index for index in range(NULL_BLOCK_N_SEEDS))


def max_a2_hits(n_seeds: int, *, share: float = NULL_A2_MAX_SHARE) -> int:
    """Ten-percent diagnostic cap. Not the fail-closed reliability bar."""
    if n_seeds < 1:
        raise ValueError("n_seeds must be >= 1")
    return int(math.floor(share * float(n_seeds)))


def majority_a2_cap(n_seeds: int) -> int:
    """Fail-closed: strict majority of seeds must not hit A2."""
    if n_seeds < 1:
        raise ValueError("n_seeds must be >= 1")
    return n_seeds // 2


def session_open_close(
    bars: Sequence[ResearchBar],
    session_dates: Sequence[date],
    rth: Sequence[bool],
) -> dict[date, float]:
    if len(bars) != len(session_dates) or len(bars) != len(rth):
        raise ValueError("open-close series must align")
    first: dict[date, int] = {}
    last: dict[date, int] = {}
    for index, session in enumerate(session_dates):
        if not rth[index]:
            continue
        first.setdefault(session, index)
        last[session] = index
    return {session: bars[last[session]].close - bars[start].open for session, start in first.items()}


def signal_map_by_session(
    signals: Sequence[float],
    session_dates: Sequence[date],
) -> dict[date, float]:
    if len(signals) != len(session_dates):
        raise ValueError("signals and session dates must align")
    out: dict[date, float] = {}
    for value, session in zip(signals, session_dates, strict=True):
        if value != 0.0 and session not in out:
            out[session] = float(value)
    return out


def partition_session_windows(
    n_sessions: int,
    *,
    is_size: int,
    oos_size: int,
    embargo: int = NULL_EMBARGO,
) -> tuple[tuple[int, int], ...]:
    """Non-overlapping [start, end) ranges covering ``[0, n_sessions)``."""
    if n_sessions < 0:
        raise ValueError("n_sessions must be >= 0")
    if is_size < 1 or oos_size < 1 or embargo < 0:
        raise ValueError("invalid walk-forward sizes")
    ranges: list[tuple[int, int]] = []
    cursor = 0
    is_end = min(is_size, n_sessions)
    if is_end > 0:
        ranges.append((0, is_end))
        cursor = is_end
    if embargo > 0 and cursor < n_sessions:
        end = min(cursor + embargo, n_sessions)
        ranges.append((cursor, end))
        cursor = end
    while cursor < n_sessions:
        end = min(cursor + oos_size, n_sessions)
        ranges.append((cursor, end))
        cursor = end
    return tuple(ranges)


def drift_aware_null_signals(
    planted: Sequence[float],
    *,
    seed: int,
    session_dates: Sequence[date],
    oc_by_date: Mapping[date, float],
    is_size: int,
    oos_size: int,
    embargo: int = NULL_EMBARGO,
) -> tuple[float, ...]:
    if len(planted) != len(session_dates):
        raise ValueError("planted signals and session dates must align")
    sessions = unique_sessions(session_dates)
    first_index = _first_signal_index(planted, session_dates)
    windows = partition_session_windows(
        len(sessions),
        is_size=is_size,
        oos_size=oos_size,
        embargo=embargo,
    )
    rng = random.Random(seed)
    assigned: dict[date, float] = {}
    for start, end in windows:
        block = sessions[start:end]
        signed = [day for day in block if day in first_index]
        if not signed:
            continue
        ocs = [float(oc_by_date.get(day, 0.0)) for day in signed]
        mean_oc = sum(ocs) / float(len(ocs))
        residuals: list[float] = []
        for day, oc in zip(signed, ocs, strict=True):
            delta = oc - mean_oc
            if delta > 0.0:
                residuals.append(1.0)
            elif delta < 0.0:
                residuals.append(-1.0)
            else:
                residuals.append(float(planted[first_index[day]]))
        rng.shuffle(residuals)
        balanced = _balance_signs(residuals)
        for day, sign in zip(signed, balanced, strict=True):
            assigned[day] = sign
    out = [0.0] * len(planted)
    for day, index in first_index.items():
        out[index] = assigned.get(day, 0.0)
    return tuple(out)


def week_block_shuffle_signals(
    planted: Sequence[float],
    session_dates: Sequence[date],
    *,
    seed: int,
) -> tuple[float, ...]:
    first_index = _first_signal_index(planted, session_dates)
    if not first_index:
        return tuple(0.0 for _ in planted)
    signed_days = [day for day in unique_sessions(session_dates) if day in first_index]
    weeks: dict[tuple[int, int], list[float]] = {}
    week_order: list[tuple[int, int]] = []
    for day in signed_days:
        iso = day.isocalendar()
        key = (int(iso.year), int(iso.week))
        if key not in weeks:
            weeks[key] = []
            week_order.append(key)
        weeks[key].append(float(planted[first_index[day]]))
    rng = random.Random(seed)
    shuffled_keys = list(week_order)
    rng.shuffle(shuffled_keys)
    flat: list[float] = []
    for key in shuffled_keys:
        flat.extend(weeks[key])
    out = [0.0] * len(planted)
    for day, sign in zip(signed_days, flat, strict=True):
        out[first_index[day]] = sign
    return tuple(out)


def remap_session_net(
    *,
    daily_gross: Sequence[float],
    daily_net: Sequence[float],
    sessions: Sequence[date],
    planted_signs: Mapping[date, float],
    null_signs: Mapping[date, float],
) -> tuple[float, ...]:
    """Flip session gross with the null sign; keep four-leg costs unsigned."""
    if len(daily_gross) != len(daily_net) or len(daily_net) != len(sessions):
        raise ValueError("daily series must align")
    out: list[float] = []
    for gross, net, day in zip(daily_gross, daily_net, sessions, strict=True):
        planted = float(planted_signs.get(day, 0.0))
        null = float(null_signs.get(day, 0.0))
        cost = float(gross) - float(net)
        if planted == 0.0 and null == 0.0:
            out.append(float(net))
            continue
        if planted == 0.0 or null == 0.0:
            out.append(0.0)
            continue
        out.append((null / planted) * float(gross) - cost)
    return tuple(out)


def _first_signal_index(
    planted: Sequence[float],
    session_dates: Sequence[date],
) -> dict[date, int]:
    out: dict[date, int] = {}
    for index, (value, session) in enumerate(zip(planted, session_dates, strict=True)):
        if value != 0.0 and session not in out:
            out[session] = index
    return out


def _balance_signs(values: Sequence[float]) -> list[float]:
    out = [float(item) for item in values]
    n_pos, n_neg = _sign_counts(out)
    while abs(n_pos - n_neg) > 1:
        want_pos = n_neg > n_pos
        flipped = False
        for index in range(len(out) - 1, -1, -1):
            value = out[index]
            if want_pos and value < 0.0:
                out[index] = 1.0
                flipped = True
                break
            if (not want_pos) and value > 0.0:
                out[index] = -1.0
                flipped = True
                break
        if not flipped:
            break
        n_pos, n_neg = _sign_counts(out)
    return out


def _sign_counts(values: Sequence[float]) -> tuple[int, int]:
    n_pos = sum(1 for item in values if item > 0.0)
    n_neg = sum(1 for item in values if item < 0.0)
    return n_pos, n_neg
