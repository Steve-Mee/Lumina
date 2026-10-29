"""Drift-aware multi-seed null for D13. Pre-registered 2026-10-29.

A permutation of session signs keeps the up/down count. On a tape with
positive drift that imbalance still clears A2. This builder **detrends and
balances** signs inside each non-overlapping walk-forward partition
(onderzoeksteam 17:34: keep both; Q-NULL-2).

Fail-closed (Q-NULL-1, 17:34): a null is unreliable when too many of the 32
seeds *look like an edge*. Majority ``16/32`` is not the gate. Exact
``n_a2/n_seeds`` is always reported as an A2 diagnostic (``4/32`` =
borderline/monitor, e.g. MES ATR).

Raw A2 (median>0 and +OOS≥0.60 on 8 windows) has P≈0.36 under a fair null,
so P(n_a2≥4)≈1 and cannot be the cycle stop. The gate uses the calibrated
7/8 tail (``NULL_CALIBRATED_POSITIVE_SHARE``): a seed is a false edge only
when A2 fires *and* +OOS≥0.875. Then the same 3/4/5 classifier applies to
``n_edge``. P(n_edge≥4 | 32)≈0.025, inside a conservative 5–10% Type I band.

ISO calendar-week block-shuffle is an extra reported check, never the gate.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
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
# Team 17:34: 4/32 is the edge of the fail region (MES ATR). Not a silent pass.
NULL_BORDERLINE_SHARE_OFFSET = 1
# Calibrated "looks like an edge" for the 32-seed gate. A2 is median>0 and
# +OOS>=0.60 (5/8). On 8 fair windows P(A2)≈0.36, so P(n_a2>=4)≈1 and a true
# null would always fail. 7/8 is Bin(8,0.5) one-sided p≈0.035; then
# P(n_edge>=4 | 32)≈0.025, inside a conservative 5–10% Type I band.
NULL_CALIBRATED_POSITIVE_SHARE = 0.875


def default_null_seeds() -> tuple[int, ...]:
    return tuple(NULL_SEED_BASE + index for index in range(NULL_N_SEEDS))


def default_block_seeds() -> tuple[int, ...]:
    return tuple(NULL_BLOCK_SEED_BASE + index for index in range(NULL_BLOCK_N_SEEDS))


def max_a2_hits(n_seeds: int, *, share: float = NULL_A2_MAX_SHARE) -> int:
    """Fail-closed cap: ``n_a2 <= floor(0.10 * n_seeds)`` is reliable (3 of 32)."""
    if n_seeds < 1:
        raise ValueError("n_seeds must be >= 1")
    return int(math.floor(share * float(n_seeds)))


def fail_closed_a2_cap(n_seeds: int) -> int:
    """Classifier cap for both A2 diagnostics and calibrated 7/8 edge counts."""
    return max_a2_hits(n_seeds)


def borderline_a2_hits(n_seeds: int) -> int:
    """Exactly one above the 10% cap (4 of 32). Monitor, do not hard-stop."""
    return max_a2_hits(n_seeds) + NULL_BORDERLINE_SHARE_OFFSET


def majority_a2_cap(n_seeds: int) -> int:
    """Historical majority lock (16 of 32). Not fail-closed after 17:34."""
    if n_seeds < 1:
        raise ValueError("n_seeds must be >= 1")
    return n_seeds // 2


@dataclass(frozen=True, slots=True)
class NullReliability:
    n_a2: int
    n_seeds: int
    exact: str
    ten_pct_cap: int
    borderline_count: int
    within_ten_pct: bool
    borderline: bool
    reliable: bool
    status: str


def null_seed_is_false_edge(*, detected: bool, pct_positive: float) -> bool:
    """Calibrated null-edge: A2 and +OOS in the 7/8 tail. Planted A2 is unchanged."""
    if not detected:
        return False
    if not math.isfinite(pct_positive):
        return False
    return float(pct_positive) >= NULL_CALIBRATED_POSITIVE_SHARE


def classify_null_a2(n_a2: int, n_seeds: int) -> NullReliability:
    """Classify a 32-seed count. Always keep the exact fraction.

    Used for the A2 diagnostic (``n_a2``) and the calibrated 7/8 gate
    (``n_edge``). Same bar: ``≤3`` reliable, ``4`` borderline/monitor,
    ``≥5`` unreliable. Cycle stop uses ``n_edge``, not raw A2.
    """
    if n_seeds < 1:
        raise ValueError("n_seeds must be >= 1")
    if n_a2 < 0:
        raise ValueError("n_a2 must be >= 0")
    cap = fail_closed_a2_cap(n_seeds)
    edge = borderline_a2_hits(n_seeds)
    exact = f"{int(n_a2)}/{int(n_seeds)}"
    if n_a2 <= cap:
        status = "reliable"
        reliable = True
        borderline = False
    elif n_a2 == edge:
        status = "borderline"
        reliable = True
        borderline = True
    else:
        status = "unreliable"
        reliable = False
        borderline = False
    return NullReliability(
        n_a2=int(n_a2),
        n_seeds=int(n_seeds),
        exact=exact,
        ten_pct_cap=cap,
        borderline_count=edge,
        within_ten_pct=n_a2 <= cap,
        borderline=borderline,
        reliable=reliable,
        status=status,
    )


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
    """Detrend session OC **and** balance signs per walk-forward partition.

    Both steps are required (Q-NULL-2). Do not drop either.
    """
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
    """ISO calendar-week block shuffle. Report-only extra check, never the gate.

    Q-NULL-3: calendar week (ISO week), 8 seeds. Month blocks are too coarse.
    """
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
