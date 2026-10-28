"""Walk-forward: rolling/expanding, min 6 OOS, WFE, parameter stability."""

from __future__ import annotations

import pytest

from lumina_research.validation.walk_forward import (
    WalkForwardConfig,
    WalkForwardError,
    parameter_stability,
    run_walk_forward,
    split_walk_forward,
    static_return_scorer,
)


@pytest.mark.unit
def test_rolling_requires_six_non_overlapping_oos() -> None:
    config = WalkForwardConfig(is_size=20, oos_size=10, mode="rolling", embargo=0)
    with pytest.raises(WalkForwardError, match="6"):
        split_walk_forward(20 + 5 * 10, config)
    windows = split_walk_forward(20 + 6 * 10, config)
    assert len(windows) == 6
    oos_spans = [(w.oos_start, w.oos_end) for w in windows]
    for left, right in zip(oos_spans, oos_spans[1:]):
        assert left[1] <= right[0]


@pytest.mark.unit
def test_expanding_is_grows() -> None:
    config = WalkForwardConfig(is_size=20, oos_size=10, mode="expanding", embargo=0)
    windows = split_walk_forward(20 + 6 * 10, config)
    is_lengths = [w.is_end - w.is_start for w in windows]
    assert is_lengths == sorted(is_lengths)
    assert is_lengths[0] == 20
    assert is_lengths[-1] > is_lengths[0]


@pytest.mark.unit
def test_wfe_and_parameter_stability() -> None:
    returns = tuple(0.01 + 0.005 * ((index % 7) - 3) / 3.0 for index in range(200))
    config = WalkForwardConfig(is_size=40, oos_size=20, mode="rolling")
    result = run_walk_forward(len(returns), config, static_return_scorer(returns, {"lookback": 5.0}))
    assert result.wfe.n_windows >= 6
    assert result.wfe.wfe > 0.0
    assert result.wfe.parameter_stability == pytest.approx(1.0)
    rows = ({"k": 1.0}, {"k": 1.1}, {"k": 0.9})
    assert 0.0 < parameter_stability(rows) < 1.0
