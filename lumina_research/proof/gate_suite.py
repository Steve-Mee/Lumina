"""Phase 1 acceptance on independent synthetics. Gate floors are not changed."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from lumina_research.proof.independent import INDEPENDENT_SEEDS, student_t
from lumina_research.validation.cost_model import CostModel, MarketSnapshot, apply_costs
from lumina_research.validation.cpcv import CPCVConfig, run_cpcv
from lumina_research.validation.dsr import deflated_sharpe_ratio
from lumina_research.validation.gate import passes_validation_gate
from lumina_research.validation.pbo import probability_of_backtest_overfitting, slice_series
from lumina_research.validation.pipeline import evaluate_candidate
from lumina_research.validation.regimes import regime_robustness
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import CostProvenance, GateReport, ValidationResults
from lumina_research.validation.walk_forward import WalkForwardConfig, run_walk_forward, static_return_scorer

N_OBS = 360
_MARKETS = tuple(MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=2.0) for _ in range(N_OBS))


@dataclass(frozen=True, slots=True)
class GateCase:
    name: str
    seed: int
    expected_pass: bool
    passed: bool
    reject_reasons: tuple[str, ...]
    pbo: float | None
    dsr: float | None
    wfe: float | None
    n_oos_windows: int
    purge_applied: bool
    embargo_applied: bool
    n_trials: int
    median_oos: float | None


@dataclass(frozen=True, slots=True)
class GateSuiteReport:
    cases: tuple[GateCase, ...]
    passed: bool


def run_gate_suite(*, audit_dir: Path, seed: int = INDEPENDENT_SEEDS[0]) -> GateSuiteReport:
    """Overfit/noise must die. Planted edge after costs may pass. CPCV/DSR/WF behave."""
    cases = (
        _overfit_case(audit_dir / "overfit.jsonl", seed=seed),
        _noise_case(audit_dir / "noise.jsonl", seed=seed + 11),
        _healthy_case(audit_dir / "healthy.jsonl", seed=seed + 23),
        _pipeline_case(audit_dir / "pipeline.jsonl", seed=seed + 41),
    )
    passed = all(item.passed == item.expected_pass for item in cases) and all(
        item.n_oos_windows >= 6 and item.purge_applied and item.embargo_applied and item.n_trials >= 1 for item in cases
    )
    return GateSuiteReport(cases=cases, passed=passed)


def _overfit_case(audit: Path, *, seed: int) -> GateCase:
    registry = TrialRegistry(audit)
    tape = _ar1_noise(n=N_OBS, sigma=0.012, phi=0.35, seed=seed)
    nets: list[tuple[float, ...]] = []
    provenances: list[CostProvenance] = []
    is_end = 180
    is_scores: list[float] = []
    for index in range(24):
        positions = _random_positions(n=N_OBS, seed=seed + 10_000 + index)
        net, provenance = _costed(tape, positions)
        nets.append(net)
        provenances.append(provenance)
        is_scores.append(sum(net[:is_end]))
        registry.record(config_id=f"overfit-{index}", agent_id="proof_overfit", metrics={"is_sum": is_scores[-1]})
    best = max(range(len(is_scores)), key=lambda i: is_scores[i])
    results = _assemble(
        agent_id="proof_overfit",
        audit_path=audit,
        net_returns=nets[best],
        provenance=provenances[best],
        registry=registry,
        configs_net=nets,
    )
    passed, report = passes_validation_gate(results, registry=registry)
    return _case("overfit_ar1_random_search", seed, False, passed, report, registry)


def _noise_case(audit: Path, *, seed: int) -> GateCase:
    registry = TrialRegistry(audit)
    tape = _ar1_noise(n=N_OBS, sigma=0.01, phi=0.2, seed=seed)
    positions = _random_positions(n=N_OBS, seed=seed + 3)
    net, provenance = _costed(tape, positions)
    registry.record(config_id="noise-0", agent_id="proof_noise", metrics={"kind": "noise"})
    peers: list[tuple[float, ...]] = []
    for index in range(8):
        extra_pos = _random_positions(n=N_OBS, seed=seed + 50 + index)
        extra, _prov = _costed(tape, extra_pos)
        peers.append(extra)
        registry.record(config_id=f"noise-peer-{index}", agent_id="proof_noise", metrics={"peer": index})
    results = _assemble(
        agent_id="proof_noise",
        audit_path=audit,
        net_returns=net,
        provenance=provenance,
        registry=registry,
        configs_net=[net, *peers],
    )
    passed, report = passes_validation_gate(results, registry=registry)
    return _case("noise_ar1", seed, False, passed, report, registry)


def _healthy_case(audit: Path, *, seed: int) -> GateCase:
    registry = TrialRegistry(audit)
    strengths = (1.0, 0.85, 0.7, 0.55, 0.4)
    nets: list[tuple[float, ...]] = []
    provenances: list[CostProvenance] = []
    positions = tuple(1.0 for _ in range(N_OBS))
    mu = 0.0045
    for index, strength in enumerate(strengths):
        gross = _planted_student(n=N_OBS, mu=mu * strength, sigma=0.008, seed=seed + index)
        net, provenance = _costed(gross, positions)
        nets.append(net)
        provenances.append(provenance)
        registry.record(config_id=f"edge-{index}", agent_id="proof_edge", metrics={"strength": strength})
    results = _assemble(
        agent_id="proof_edge",
        audit_path=audit,
        net_returns=nets[0],
        provenance=provenances[0],
        registry=registry,
        configs_net=nets,
    )
    passed, report = passes_validation_gate(results, registry=registry)
    return _case("healthy_student_t_drift", seed, True, passed, report, registry)


def _pipeline_case(audit: Path, *, seed: int) -> GateCase:
    registry = TrialRegistry(audit)
    gross = _planted_student(n=N_OBS, mu=0.0045, sigma=0.008, seed=seed)
    positions = tuple(1.0 for _ in range(N_OBS))
    peers: list[tuple[float, ...]] = []
    for index in range(4):
        peer_g = _planted_student(n=N_OBS, mu=0.0045 * (1.0 - 0.12 * index), sigma=0.008, seed=seed + 7 + index)
        peer, _prov = _costed(peer_g, positions)
        peers.append(peer)
        registry.record(config_id=f"pipe-peer-{index}", agent_id="proof_pipe", metrics={"i": index})
    evaluation = evaluate_candidate(
        agent_id="proof_pipe",
        config_id="pipe-0",
        gross_returns=gross,
        positions=positions,
        markets=_MARKETS,
        spec="MES",
        registry=registry,
        peer_net_returns=peers,
        audit_path=audit,
    )
    return _case("pipeline_evaluate_candidate", seed, True, evaluation.passed, evaluation.report, registry)


def _case(
    name: str,
    seed: int,
    expected: bool,
    passed: bool,
    report: GateReport,
    registry: TrialRegistry,
) -> GateCase:
    return GateCase(
        name=name,
        seed=seed,
        expected_pass=expected,
        passed=passed,
        reject_reasons=tuple(report.reject_reasons),
        pbo=report.pbo.pbo,
        dsr=report.dsr.probability,
        wfe=report.wfe.wfe,
        n_oos_windows=report.n_oos_windows,
        purge_applied=report.purge_applied,
        embargo_applied=report.embargo_applied,
        n_trials=registry.n_trials,
        median_oos=report.median_oos_after_costs,
    )


def _ar1_noise(*, n: int, sigma: float, phi: float, seed: int) -> tuple[float, ...]:
    rng = random.Random(seed)
    value = 0.0
    out: list[float] = []
    for _ in range(n):
        value = phi * value + sigma * rng.gauss(0.0, 1.0)
        out.append(value)
    return tuple(out)


def _planted_student(*, n: int, mu: float, sigma: float, seed: int) -> tuple[float, ...]:
    rng = random.Random(seed)
    drifts = (mu * 1.6, mu * 1.6, -mu * 0.35, mu * 1.6, mu * 1.6, -mu * 0.35)
    sigmas = (sigma * 1.8, sigma * 0.55, sigma * 1.8, sigma * 0.55, sigma * 1.8, sigma * 0.55)
    block = n // 6
    out: list[float] = []
    for index, (drift, noise) in enumerate(zip(drifts, sigmas, strict=True)):
        length = block if index < 5 else n - 5 * block
        scale = noise * ((3.0 / 5.0) ** 0.5)
        for _ in range(length):
            out.append(drift + scale * student_t(rng, df=5))
    return tuple(out)


def _random_positions(*, n: int, seed: int) -> tuple[float, ...]:
    rng = random.Random(seed)
    return tuple(float(rng.choice((-1.0, 1.0))) for _ in range(n))


def _costed(gross: Sequence[float], positions: Sequence[float]) -> tuple[tuple[float, ...], CostProvenance]:
    series = apply_costs(
        gross_returns=gross,
        positions=positions,
        equity=100_000.0,
        spec="MES",
        markets=_MARKETS,
        model=CostModel(),
    )
    return series.net_returns, series.provenance


def _assemble(
    *,
    agent_id: str,
    audit_path: Path,
    net_returns: Sequence[float],
    provenance: CostProvenance,
    registry: TrialRegistry,
    configs_net: Sequence[Sequence[float]],
) -> ValidationResults:
    net = tuple(float(item) for item in net_returns)
    wf = run_walk_forward(
        len(net),
        WalkForwardConfig(is_size=60, oos_size=30, mode="rolling", embargo=1, label_horizon=1),
        static_return_scorer(net),
    )
    cpcv = run_cpcv(net, CPCVConfig(n_groups=6, n_test_groups=2, embargo=1, label_horizon=1))
    dsr = deflated_sharpe_ratio(net, registry=registry)
    rows = tuple(tuple(float(item) for item in row) for row in configs_net) or (net,)
    matrix = [slice_series(row, 8) for row in rows]
    pbo = probability_of_backtest_overfitting(matrix)
    regimes = regime_robustness(net)
    return ValidationResults(
        agent_id=agent_id,
        audit_path=audit_path,
        oos_distribution=cpcv.oos_distribution,
        dsr=dsr,
        pbo=pbo,
        wfe=wf.wfe,
        cost_provenance=provenance,
        median_oos_after_costs=float(sorted(wf.oos_means)[len(wf.oos_means) // 2]) if wf.oos_means else 0.0,
        n_oos_windows=len(wf.windows),
        regimes=regimes,
        n_trials_registry=registry.n_trials,
        purge_applied=cpcv.purge_applied,
        embargo_applied=cpcv.embargo_applied,
    )


