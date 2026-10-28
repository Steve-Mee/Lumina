"""Synthetic series for gate tests. No network, no downloads."""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Sequence

from lumina_research.validation.cost_model import CostModel, MarketSnapshot, apply_costs
from lumina_research.validation.cpcv import CPCVConfig, run_cpcv
from lumina_research.validation.dsr import deflated_sharpe_ratio
from lumina_research.validation.pbo import probability_of_backtest_overfitting, slice_series
from lumina_research.validation.regimes import regime_robustness
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import CostProvenance, ValidationResults
from lumina_research.validation.walk_forward import WalkForwardConfig, run_walk_forward, static_return_scorer


def gauss(rng: random.Random) -> float:
    return rng.gauss(0.0, 1.0)


def drift_returns(*, n: int, mu: float, sigma: float, seed: int) -> tuple[float, ...]:
    rng = random.Random(seed)
    return tuple(mu + sigma * gauss(rng) for _ in range(n))


def noise_returns(*, n: int, sigma: float, seed: int) -> tuple[float, ...]:
    return drift_returns(n=n, mu=0.0, sigma=sigma, seed=seed)


def constant_markets(n: int) -> tuple[MarketSnapshot, ...]:
    snap = MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=2.0)
    return tuple(snap for _ in range(n))


def always_long(n: int) -> tuple[float, ...]:
    return tuple(1.0 for _ in range(n))


def random_positions(*, n: int, seed: int) -> tuple[float, ...]:
    rng = random.Random(seed)
    return tuple(float(rng.choice((-1.0, 1.0))) for _ in range(n))


def costed(
    gross: Sequence[float],
    positions: Sequence[float],
    *,
    equity: float = 100_000.0,
    root: str = "MES",
) -> tuple[tuple[float, ...], object]:
    series = apply_costs(
        gross_returns=gross,
        positions=positions,
        equity=equity,
        spec=root,
        markets=constant_markets(len(gross)),
        model=CostModel(),
    )
    return series.net_returns, series.provenance


def assemble_results(
    *,
    agent_id: str,
    audit_path: Path,
    net_returns: Sequence[float],
    provenance: object,
    registry: TrialRegistry,
    configs_net: Sequence[Sequence[float]],
    wf_mode: str = "rolling",
) -> ValidationResults:
    n = len(net_returns)
    wf = run_walk_forward(
        n,
        WalkForwardConfig(is_size=60, oos_size=30, mode=wf_mode, embargo=1, label_horizon=1),
        static_return_scorer(net_returns),
    )
    cpcv = run_cpcv(net_returns, CPCVConfig(n_groups=6, n_test_groups=2, embargo=1, label_horizon=1))
    dsr = deflated_sharpe_ratio(net_returns, registry=registry)
    matrix = [slice_series(row, 8) for row in configs_net]
    pbo = probability_of_backtest_overfitting(matrix)
    regimes = regime_robustness(net_returns)
    if not isinstance(provenance, CostProvenance):
        raise TypeError("cost provenance required")
    return ValidationResults(
        agent_id=agent_id,
        audit_path=audit_path,
        oos_distribution=cpcv.oos_distribution,
        dsr=dsr,
        pbo=pbo,
        wfe=wf.wfe,
        cost_provenance=provenance,
        median_oos_after_costs=float(_median(wf.oos_means)),
        n_oos_windows=len(wf.windows),
        regimes=regimes,
        n_trials_registry=registry.n_trials,
    )


def _median(values: Sequence[float]) -> float:
    ordered = sorted(float(item) for item in values)
    mid = len(ordered) // 2
    if not ordered:
        return math.nan
    if len(ordered) % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])
