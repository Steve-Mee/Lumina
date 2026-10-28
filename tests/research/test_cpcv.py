"""CPCV path reconstruction: φ = k/N * C(N,k) and each observation once per path."""

from __future__ import annotations

import itertools

import pytest

from lumina_research.validation.cpcv import (
    CPCVConfig,
    assign_groups,
    combination_count,
    path_count,
    reconstruct_paths,
    run_cpcv,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("n_groups", "k"),
    [(6, 2), (8, 2), (8, 3), (10, 2), (7, 3)],
)
def test_path_count_identity(n_groups: int, k: int) -> None:
    phi = path_count(n_groups, k)
    assert phi * n_groups == k * combination_count(n_groups, k)
    combos = tuple(itertools.combinations(range(n_groups), k))
    path_map = reconstruct_paths(n_groups, combos)
    assert len(path_map) == phi
    assert len(combos) == combination_count(n_groups, k)


@pytest.mark.unit
def test_each_observation_exactly_once_per_path() -> None:
    n_groups, k, n_obs = 6, 2, 60
    groups = assign_groups(n_obs, n_groups)
    combos = tuple(itertools.combinations(range(n_groups), k))
    path_map = reconstruct_paths(n_groups, combos)
    universe = list(range(n_obs))
    for path in path_map:
        seen: list[int] = []
        for group_id, combo_index in enumerate(path):
            assert group_id in combos[combo_index]
            seen.extend(groups[group_id].index)
        assert sorted(seen) == universe
        assert len(seen) == n_obs


@pytest.mark.unit
def test_run_cpcv_stitches_full_paths() -> None:
    returns = tuple(float(index) for index in range(48))
    result = run_cpcv(returns, CPCVConfig(n_groups=6, n_test_groups=2, embargo=1, label_horizon=1))
    assert result.n_paths == path_count(6, 2)
    assert result.n_combinations == combination_count(6, 2)
    assert result.purge_applied is True
    assert result.embargo_applied is True
    assert result.oos_distribution.is_complete()
    assert len(result.path_sharpes) == result.n_paths
    for fold in result.folds:
        train_set = set(fold.train_index)
        test_set = set(fold.test_index)
        assert train_set.isdisjoint(test_set)
        for index in fold.train_index:
            assert index not in test_set
