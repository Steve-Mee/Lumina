"""CPCV path reconstruction: φ = k/N * C(N,k) and each observation once per path."""

from __future__ import annotations

import itertools

import pytest

from lumina_research.validation.cpcv import (
    CPCVConfig,
    CPCVError,
    assign_groups,
    combination_count,
    path_count,
    reconstruct_paths,
    run_cpcv,
)
from lumina_research.validation.purge import contiguous_segments, purge_train_indices


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


@pytest.mark.unit
def test_purge_uses_per_segment_overlap_not_minmax_span() -> None:
    n_obs, horizon, embargo = 60, 8, 3
    t1 = tuple(min(n_obs, index + horizon) for index in range(n_obs))
    # Non-contiguous test: groups 0 and 3 (bars 0-9 and 30-39 if 6 groups of 10).
    test_index = tuple(list(range(0, 10)) + list(range(30, 40)))
    train_index = tuple(i for i in range(n_obs) if i not in set(test_index))
    kept = set(purge_train_indices(train_index, test_index, t1, embargo, n_obs))
    # Mid-group bars 13-18 sit between the two test segments and do not overlap
    # labels or embargo; min-max span would over-purge them.
    for index in range(13, 19):
        assert index in kept
    # Label overlap into the second test segment must still be purged (t1[22]=30).
    assert 22 not in kept
    for index in kept:
        label_end = t1[index]
        assert not any(index <= test_i <= label_end for test_i in test_index)
        for _start, end in contiguous_segments(test_index):
            embargo_end = min(n_obs, end + 1 + embargo)
            assert not (end < index < embargo_end)


@pytest.mark.unit
def test_cpcv_noncontiguous_folds_have_no_label_leakage() -> None:
    returns = tuple(0.01 * ((index % 5) - 2) for index in range(60))
    result = run_cpcv(returns, CPCVConfig(n_groups=6, n_test_groups=2, embargo=3, label_horizon=8))
    n_obs = 60
    t1 = tuple(min(n_obs, index + 8) for index in range(n_obs))
    for fold in result.folds:
        for index in fold.train_index:
            label_end = t1[index]
            for test_i in fold.test_index:
                assert not (index <= test_i <= label_end)


@pytest.mark.unit
def test_cpcv_rejects_too_few_groups() -> None:
    with pytest.raises(CPCVError):
        CPCVConfig(n_groups=2, n_test_groups=1)
