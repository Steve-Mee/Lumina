"""Drift-aware multi-seed null for D13. Pre-registered 2026-10-29.

A permutation of session signs keeps the up/down count. On a tape with
positive drift that imbalance still clears A2. Production builder (18:17):
linear OLS detrend of session OC vs time index, session-shuffle of residual
signs, count-balance, then greedy magnitude-balance on ``|OC|`` inside each
walk-forward partition. Detrend and balance both stay required.

Replacing the session shuffle with an ISO-week block-shuffle would preserve
intra-week drift and raise FPR. Week-block of planted signs stays the
report-only extra 8 seeds, never the production shuffle.

Primary gate (18:17): a seed is a false edge when A2 fires **and** +OOS≥7/8.
Exact ``n_a2`` stays diagnostic. The null fails when ``n_edge >= 4/32``
(4 is fail, not monitor). Target FPR 5–10%. Majority ``16/32`` is not the gate.
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
# Team 18:17: 4/32 is fail (band 4–5). Not borderline/monitor.
NULL_FAIL_AT_OFFSET = 1
NULL_BUILDER_V1 = "mean_shuffle"
NULL_BUILDER_V2 = "linear_magnitude"
NULL_BUILDER = NULL_BUILDER_V2
# Gate: A2 and +OOS>=0.875 (7/8). Raw A2 (+OOS>=0.60) is diagnostic only.
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
    """Last reliable count: ``3`` of 32 (10% cap). ``4`` fails."""
    return max_a2_hits(n_seeds)


def fail_closed_hit_count(n_seeds: int) -> int:
    """First fail count: ``4`` of 32."""
    return max_a2_hits(n_seeds) + NULL_FAIL_AT_OFFSET


def borderline_a2_hits(n_seeds: int) -> int:
    """Retired 18:17 alias for the fail-at count. ``4`` is fail, not monitor."""
    return fail_closed_hit_count(n_seeds)


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

    Gate uses calibrated ``n_edge`` (A2 and +OOS≥7/8). Raw ``n_a2`` is
    diagnostic. ``≤3/32`` reliable; ``≥4/32`` unreliable (4 is fail).
    """
    if n_seeds < 1:
        raise ValueError("n_seeds must be >= 1")
    if n_a2 < 0:
        raise ValueError("n_a2 must be >= 0")
    cap = fail_closed_a2_cap(n_seeds)
    fail_at = fail_closed_hit_count(n_seeds)
    exact = f"{int(n_a2)}/{int(n_seeds)}"
    if n_a2 <= cap:
        status = "reliable"
        reliable = True
    else:
        status = "unreliable"
        reliable = False
    return NullReliability(
        n_a2=int(n_a2),
        n_seeds=int(n_seeds),
        exact=exact,
        ten_pct_cap=cap,
        borderline_count=fail_at,
        within_ten_pct=n_a2 <= cap,
        borderline=False,
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


def mean_shuffle_balance_null_signals(
    planted: Sequence[float],
    *,
    seed: int,
    session_dates: Sequence[date],
    oc_by_date: Mapping[date, float],
    is_size: int,
    oos_size: int,
    embargo: int = NULL_EMBARGO,
) -> tuple[float, ...]:
    """v1 builder (before 18:17): mean detrend, session shuffle, count-balance."""
    return _partition_null_signals(
        planted,
        seed=seed,
        session_dates=session_dates,
        oc_by_date=oc_by_date,
        is_size=is_size,
        oos_size=oos_size,
        embargo=embargo,
        builder=NULL_BUILDER_V1,
    )


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
    """v2 builder (18:17): linear detrend, session shuffle, count+magnitude balance."""
    return _partition_null_signals(
        planted,
        seed=seed,
        session_dates=session_dates,
        oc_by_date=oc_by_date,
        is_size=is_size,
        oos_size=oos_size,
        embargo=embargo,
        builder=NULL_BUILDER,
    )


def null_signals_for_builder(
    planted: Sequence[float],
    *,
    seed: int,
    session_dates: Sequence[date],
    oc_by_date: Mapping[date, float],
    is_size: int,
    oos_size: int,
    embargo: int = NULL_EMBARGO,
    builder: str = NULL_BUILDER,
) -> tuple[float, ...]:
    if builder == NULL_BUILDER_V1:
        return mean_shuffle_balance_null_signals(
            planted,
            seed=seed,
            session_dates=session_dates,
            oc_by_date=oc_by_date,
            is_size=is_size,
            oos_size=oos_size,
            embargo=embargo,
        )
    if builder != NULL_BUILDER_V2:
        raise ValueError(f"unknown null builder {builder!r}")
    return drift_aware_null_signals(
        planted,
        seed=seed,
        session_dates=session_dates,
        oc_by_date=oc_by_date,
        is_size=is_size,
        oos_size=oos_size,
        embargo=embargo,
    )


def _partition_null_signals(
    planted: Sequence[float],
    *,
    seed: int,
    session_dates: Sequence[date],
    oc_by_date: Mapping[date, float],
    is_size: int,
    oos_size: int,
    embargo: int,
    builder: str,
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
        if builder == NULL_BUILDER_V1:
            mean_oc = sum(ocs) / float(len(ocs))
            residuals = [oc - mean_oc for oc in ocs]
            signs = _signs_from_residuals(residuals, planted, signed, first_index)
            rng.shuffle(signs)
            balanced = _balance_signs(signs)
        else:
            residuals = _linear_residuals(ocs)
            signs = _signs_from_residuals(residuals, planted, signed, first_index)
            rng.shuffle(signs)
            balanced = _balance_signed_magnitude(_balance_signs(signs), ocs)
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


def _linear_residuals(values: Sequence[float]) -> list[float]:
    count = len(values)
    if count < 2:
        mean = sum(values) / float(count) if count else 0.0
        return [float(item) - mean for item in values]
    sum_x = float(count * (count - 1)) / 2.0
    sum_xx = float((count - 1) * count * (2 * count - 1)) / 6.0
    sum_y = sum(float(item) for item in values)
    sum_xy = sum(float(index) * float(item) for index, item in enumerate(values))
    denom = float(count) * sum_xx - sum_x * sum_x
    if denom == 0.0:
        mean = sum_y / float(count)
        return [float(item) - mean for item in values]
    slope = (float(count) * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / float(count)
    return [float(item) - (intercept + slope * float(index)) for index, item in enumerate(values)]


def _signs_from_residuals(
    residuals: Sequence[float],
    planted: Sequence[float],
    signed: Sequence[date],
    first_index: Mapping[date, int],
) -> list[float]:
    out: list[float] = []
    for day, residual in zip(signed, residuals, strict=True):
        if residual > 0.0:
            out.append(1.0)
        elif residual < 0.0:
            out.append(-1.0)
        else:
            out.append(float(planted[first_index[day]]))
    return out


def _week_block_shuffle_in_window(
    days: Sequence[date],
    signs: Sequence[float],
    rng: random.Random,
) -> list[float]:
    weeks: dict[tuple[int, int], list[float]] = {}
    order: list[tuple[int, int]] = []
    for day, sign in zip(days, signs, strict=True):
        iso = day.isocalendar()
        key = (int(iso.year), int(iso.week))
        if key not in weeks:
            weeks[key] = []
            order.append(key)
        weeks[key].append(float(sign))
    shuffled = list(order)
    rng.shuffle(shuffled)
    flat: list[float] = []
    for key in shuffled:
        flat.extend(weeks[key])
    return flat


def _balance_signed_magnitude(signs: Sequence[float], moves: Sequence[float]) -> list[float]:
    out = [float(item) for item in signs]
    mags = [abs(float(item)) for item in moves]
    if len(out) != len(mags):
        raise ValueError("signs and moves must align")
    for _ in range(len(out)):
        current = sum(sign * mag for sign, mag in zip(out, mags, strict=True))
        best_abs = abs(current)
        swap: tuple[int, int] | None = None
        pos = [index for index, value in enumerate(out) if value > 0.0]
        neg = [index for index, value in enumerate(out) if value < 0.0]
        for left in pos:
            for right in neg:
                candidate = current - 2.0 * mags[left] + 2.0 * mags[right]
                if abs(candidate) + 1e-12 < best_abs:
                    best_abs = abs(candidate)
                    swap = (left, right)
        if swap is None:
            break
        left, right = swap
        out[left], out[right] = out[right], out[left]
    return out


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
