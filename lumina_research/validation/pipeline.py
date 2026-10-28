"""Single evaluation path: costs → trials → WF/CPCV/DSR/PBO/regimes → gate → fitness."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from lumina_research.fitness import FitnessRefused, FitnessScore, compute_fitness
from lumina_research.validation.contracts import ContractSpec
from lumina_research.validation.cost_model import CostModel, MarketSnapshot, apply_costs
from lumina_research.validation.cpcv import CPCVConfig, run_cpcv
from lumina_research.validation.dsr import deflated_sharpe_ratio
from lumina_research.validation.gate import passes_validation_gate
from lumina_research.validation.pbo import probability_of_backtest_overfitting, slice_series
from lumina_research.validation.regimes import regime_robustness
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import (
    CostProvenance,
    DSRSnapshot,
    GateReport,
    OOSDistribution,
    PBOSnapshot,
    RegimeSnapshot,
    ValidationResults,
    WFESnapshot,
)
from lumina_research.validation.walk_forward import WalkForwardConfig, run_walk_forward, static_return_scorer


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    passed: bool
    report: GateReport
    fitness: FitnessScore | None
    results: ValidationResults
    net_returns: tuple[float, ...]
    turnover: float


def evaluate_candidate(
    *,
    agent_id: str,
    config_id: str,
    gross_returns: Sequence[float],
    positions: Sequence[float],
    markets: Sequence[MarketSnapshot],
    spec: ContractSpec | str,
    registry: TrialRegistry,
    peer_net_returns: Sequence[Sequence[float]],
    audit_path: Path | None = None,
    equity: float = 100_000.0,
    model: CostModel | None = None,
    wf_mode: Literal["rolling", "expanding"] = "rolling",
    is_size: int = 60,
    oos_size: int = 30,
    embargo: int = 1,
    label_horizon: int = 1,
    n_cpcv_groups: int = 6,
    n_cpcv_test_groups: int = 2,
    pbo_slices: int = 8,
) -> CandidateEvaluation:
    """Always apply the four-leg cost model, record the trial, then gate.

    `peer_net_returns` are already-costed series of other configs (required for PBO).
    """
    path = audit_path if audit_path is not None else registry.audit_path
    costed = apply_costs(
        gross_returns=gross_returns,
        positions=positions,
        equity=equity,
        spec=spec,
        markets=markets,
        model=model,
    )
    net = costed.net_returns
    provenance = costed.provenance
    turnover = _turnover(positions)
    registry.record(
        config_id=config_id,
        agent_id=agent_id,
        metrics={"turnover": turnover, "n_obs": len(net)},
    )
    wf = run_walk_forward(
        len(net),
        WalkForwardConfig(
            is_size=is_size,
            oos_size=oos_size,
            mode=wf_mode,
            embargo=embargo,
            label_horizon=label_horizon,
        ),
        static_return_scorer(net),
    )
    cpcv = run_cpcv(
        net,
        CPCVConfig(
            n_groups=n_cpcv_groups,
            n_test_groups=n_cpcv_test_groups,
            embargo=embargo,
            label_horizon=label_horizon,
        ),
    )
    dsr = deflated_sharpe_ratio(net, registry=registry)
    matrix = [slice_series(net, pbo_slices), *[slice_series(row, pbo_slices) for row in peer_net_returns]]
    pbo = probability_of_backtest_overfitting(matrix)
    regimes = regime_robustness(net)
    oos_means = wf.oos_means
    results = ValidationResults(
        agent_id=agent_id,
        audit_path=path,
        oos_distribution=cpcv.oos_distribution,
        dsr=dsr,
        pbo=pbo,
        wfe=wf.wfe,
        cost_provenance=provenance,
        median_oos_after_costs=_median(oos_means),
        n_oos_windows=len(wf.windows),
        regimes=regimes,
        n_trials_registry=registry.n_trials,
        purge_applied=cpcv.purge_applied,
        embargo_applied=cpcv.embargo_applied,
    )
    passed, report = passes_validation_gate(results, registry=registry)
    fitness: FitnessScore | None
    try:
        fitness = compute_fitness(report, turnover=turnover)
    except FitnessRefused:
        fitness = None
    return CandidateEvaluation(
        passed=passed,
        report=report,
        fitness=fitness,
        results=results,
        net_returns=net,
        turnover=turnover,
    )


def missing_evaluation(
    *,
    agent_id: str,
    audit_path: Path,
    registry: TrialRegistry,
    provenance: CostProvenance | None = None,
) -> CandidateEvaluation:
    """Fail-closed bundle used when an upstream step cannot form metrics."""
    results = ValidationResults(
        agent_id=agent_id,
        audit_path=audit_path,
        oos_distribution=OOSDistribution.missing(),
        dsr=DSRSnapshot.missing(),
        pbo=PBOSnapshot.missing(),
        wfe=WFESnapshot.missing(),
        cost_provenance=provenance,
        median_oos_after_costs=math.nan,
        n_oos_windows=0,
        regimes=RegimeSnapshot.missing(),
        n_trials_registry=registry.n_trials,
        purge_applied=False,
        embargo_applied=False,
    )
    passed, report = passes_validation_gate(results, registry=registry)
    return CandidateEvaluation(
        passed=passed,
        report=report,
        fitness=None,
        results=results,
        net_returns=(),
        turnover=math.nan,
    )


def _turnover(positions: Sequence[float]) -> float:
    series = tuple(float(item) for item in positions)
    if len(series) < 2:
        return 0.0
    traded = sum(abs(series[index] - series[index - 1]) for index in range(1, len(series)))
    return traded / float(len(series) - 1)


def _median(values: Sequence[float]) -> float:
    ordered = sorted(float(item) for item in values if math.isfinite(item))
    if not ordered:
        return math.nan
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])
