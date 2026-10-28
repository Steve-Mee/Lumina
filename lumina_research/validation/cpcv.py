"""Combinatorial Purged CV (López de Prado, AFML ch. 12).

N groups, k test groups, purge on the label horizon t1, embargo, and path
reconstruction with φ = k/N * C(N, k) = C(N-1, k-1) paths. Each observation
appears exactly once per path.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Sequence

from lumina_research.validation.metrics import annualized_sharpe
from lumina_research.validation.types import OOSDistribution


class CPCVError(ValueError):
    """CPCV split, purge, or path reconstruction failed."""


@dataclass(frozen=True, slots=True)
class CPCVConfig:
    n_groups: int
    n_test_groups: int
    embargo: int = 0
    label_horizon: int = 0
    periods_per_year: float = 252.0

    def __post_init__(self) -> None:
        if self.n_groups < 3:
            raise CPCVError("n_groups must be >= 3")
        if self.n_test_groups < 1 or self.n_test_groups >= self.n_groups:
            raise CPCVError("n_test_groups must be in [1, N)")
        if self.embargo < 0 or self.label_horizon < 0:
            raise CPCVError("embargo and label_horizon must be >= 0")


@dataclass(frozen=True, slots=True)
class GroupSplit:
    group_id: int
    start: int
    end: int
    index: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CombinationFold:
    combination_index: int
    test_groups: tuple[int, ...]
    train_index: tuple[int, ...]
    test_index: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CPCVResult:
    n_groups: int
    n_test_groups: int
    n_combinations: int
    n_paths: int
    path_map: tuple[tuple[int, ...], ...]
    path_sharpes: tuple[float, ...]
    oos_distribution: OOSDistribution
    folds: tuple[CombinationFold, ...]
    groups: tuple[GroupSplit, ...]
    purge_applied: bool
    embargo_applied: bool


def binomial(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    return math.comb(n, k)


def path_count(n_groups: int, n_test_groups: int) -> int:
    """φ = k/N * C(N, k) = C(N-1, k-1)."""
    combinations = binomial(n_groups, n_test_groups)
    phi = n_test_groups * combinations // n_groups
    expected = binomial(n_groups - 1, n_test_groups - 1)
    if phi != expected:
        raise CPCVError(f"path count identity failed: {phi} != {expected}")
    return phi


def combination_count(n_groups: int, n_test_groups: int) -> int:
    return binomial(n_groups, n_test_groups)


def reconstruct_paths(n_groups: int, test_combinations: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    """path_map[p][g] = combination index that tests group g on path p."""
    if not test_combinations:
        raise CPCVError("no combinations")
    k = len(test_combinations[0])
    if any(len(combo) != k for combo in test_combinations):
        raise CPCVError("all combinations must have k test groups")
    n_combos = len(test_combinations)
    n_paths = path_count(n_groups, k)
    combos_by_group: list[list[int]] = [[] for _ in range(n_groups)]
    for combo_index, combo in enumerate(test_combinations):
        seen: set[int] = set()
        for group in combo:
            if group < 0 or group >= n_groups or group in seen:
                raise CPCVError(f"invalid test group {group} in combination {combo_index}")
            seen.add(group)
            combos_by_group[group].append(combo_index)
    for group, hits in enumerate(combos_by_group):
        if len(hits) != n_paths:
            raise CPCVError(f"group {group} is tested {len(hits)} times; expected {n_paths}")
    path_map = tuple(tuple(combos_by_group[group][path] for group in range(n_groups)) for path in range(n_paths))
    _assert_each_observation_once_per_path(path_map, tuple(tuple(combo) for combo in test_combinations), n_groups)
    if n_combos != combination_count(n_groups, k):
        raise CPCVError("combination list does not match C(N, k)")
    return path_map


def assign_groups(n_obs: int, n_groups: int) -> tuple[GroupSplit, ...]:
    if n_obs < n_groups:
        raise CPCVError("need at least one observation per group")
    base, remainder = divmod(n_obs, n_groups)
    groups: list[GroupSplit] = []
    cursor = 0
    for group_id in range(n_groups):
        width = base + (1 if group_id < remainder else 0)
        end = cursor + width
        groups.append(GroupSplit(group_id=group_id, start=cursor, end=end, index=tuple(range(cursor, end))))
        cursor = end
    if cursor != n_obs:
        raise CPCVError("group assignment did not cover n_obs")
    return tuple(groups)


def run_cpcv(
    returns: Sequence[float],
    config: CPCVConfig,
    t1: Sequence[int] | None = None,
) -> CPCVResult:
    series = tuple(float(item) for item in returns)
    n_obs = len(series)
    groups = assign_groups(n_obs, config.n_groups)
    combos = tuple(itertools.combinations(range(config.n_groups), config.n_test_groups))
    path_map = reconstruct_paths(config.n_groups, combos)
    horizons = _t1(n_obs, config.label_horizon, t1)
    folds: list[CombinationFold] = []
    combo_group_returns: list[dict[int, tuple[float, ...]]] = []
    for combo_index, test_groups in enumerate(combos):
        test_index = tuple(index for group in test_groups for index in groups[group].index)
        test_set = set(test_index)
        raw_train = tuple(index for group in range(config.n_groups) if group not in test_groups for index in groups[group].index)
        train_index = _purge_train(raw_train, test_set, horizons, config.embargo, n_obs)
        folds.append(
            CombinationFold(
                combination_index=combo_index,
                test_groups=tuple(test_groups),
                train_index=train_index,
                test_index=test_index,
            )
        )
        per_group = {group: tuple(series[index] for index in groups[group].index) for group in test_groups}
        combo_group_returns.append(per_group)
    path_sharpes: list[float] = []
    path_returns: list[tuple[float, ...]] = []
    for path in path_map:
        stitched: list[float] = []
        for group_id, combo_index in enumerate(path):
            stitched.extend(combo_group_returns[combo_index][group_id])
        path_tuple = tuple(stitched)
        if len(path_tuple) != n_obs:
            raise CPCVError("path length != n_obs; an observation was dropped or duplicated")
        path_returns.append(path_tuple)
        path_sharpes.append(annualized_sharpe(path_tuple, periods_per_year=config.periods_per_year))
    return CPCVResult(
        n_groups=config.n_groups,
        n_test_groups=config.n_test_groups,
        n_combinations=len(combos),
        n_paths=len(path_map),
        path_map=path_map,
        path_sharpes=tuple(path_sharpes),
        oos_distribution=OOSDistribution.from_values(path_sharpes),
        folds=tuple(folds),
        groups=groups,
        purge_applied=True,
        embargo_applied=True,
    )


def _assert_each_observation_once_per_path(
    path_map: tuple[tuple[int, ...], ...],
    combos: tuple[tuple[int, ...], ...],
    n_groups: int,
) -> None:
    for path in path_map:
        if len(path) != n_groups:
            raise CPCVError("path does not assign every group")
        tested: list[int] = []
        for group_id, combo_index in enumerate(path):
            if group_id not in combos[combo_index]:
                raise CPCVError("path maps a group to a combination that does not test it")
            tested.append(group_id)
        if sorted(tested) != list(range(n_groups)):
            raise CPCVError("a path does not test each group exactly once")


def _t1(n_obs: int, horizon: int, t1: Sequence[int] | None) -> tuple[int, ...]:
    if t1 is None:
        return tuple(min(n_obs, index + horizon) for index in range(n_obs))
    if len(t1) != n_obs:
        raise CPCVError("t1 must match n_obs")
    return tuple(int(value) for value in t1)


def _purge_train(
    train_index: tuple[int, ...],
    test_set: set[int],
    t1: Sequence[int],
    embargo: int,
    n_obs: int,
) -> tuple[int, ...]:
    if not test_set:
        return train_index
    test_min = min(test_set)
    test_max = max(test_set)
    embargo_end = min(n_obs, test_max + 1 + embargo)
    kept: list[int] = []
    for index in train_index:
        label_end = t1[index]
        overlaps = index <= test_max and label_end >= test_min
        in_embargo = test_max < index < embargo_end
        if overlaps or in_embargo:
            continue
        kept.append(index)
    return tuple(kept)
