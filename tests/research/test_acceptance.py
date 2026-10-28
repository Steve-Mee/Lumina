"""Acceptance: dummy overfit is rejected; synthetic edge after costs can pass."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_research.validation.gate import passes_validation_gate
from tests.research.synthetic import (
    always_long,
    assemble_results,
    costed,
    noise_returns,
    random_positions,
)
from lumina_research.validation.trial_registry import TrialRegistry


N = 360


@pytest.mark.unit
def test_dummy_overfit_random_search_is_rejected(tmp_path: Path) -> None:
    audit = tmp_path / "overfit.jsonl"
    registry = TrialRegistry(audit)
    market = noise_returns(n=N, sigma=0.01, seed=7)
    nets: list[tuple[float, ...]] = []
    provenances = []
    is_end = 180
    is_scores: list[float] = []
    for index in range(24):
        positions = random_positions(n=N, seed=1000 + index)
        net, provenance = costed(market, positions)
        nets.append(net)
        provenances.append(provenance)
        is_scores.append(sum(net[:is_end]))
        registry.record(config_id=f"noise-{index}", agent_id="overfit", metrics={"is_sum": is_scores[-1]})
    best = max(range(len(is_scores)), key=lambda i: is_scores[i])
    results = assemble_results(
        agent_id="overfit",
        audit_path=audit,
        net_returns=nets[best],
        provenance=provenances[best],
        registry=registry,
        configs_net=nets,
    )
    passed, report = passes_validation_gate(results, registry=registry)
    assert passed is False
    assert report.reject_reasons
    metrics = report.to_audit_metrics()
    assert metrics["oos_distribution"] is not None
    assert metrics["dsr"] is not None
    assert metrics["pbo"] is not None
    assert report.pbo.pbo > 0.25 or report.dsr.probability < 0.95 or report.median_oos_after_costs < 0.0


@pytest.mark.unit
def test_synthetic_edge_after_costs_can_pass(tmp_path: Path) -> None:
    audit = tmp_path / "edge.jsonl"
    registry = TrialRegistry(audit)
    eps = noise_returns(n=N, sigma=0.008, seed=3)
    strengths = (1.0, 0.85, 0.7, 0.55, 0.4)
    nets: list[tuple[float, ...]] = []
    provenances = []
    mu = 0.004
    positions = always_long(N)
    for index, strength in enumerate(strengths):
        gross = tuple(mu * strength + eps[i] for i in range(N))
        net, provenance = costed(gross, positions)
        nets.append(net)
        provenances.append(provenance)
        registry.record(config_id=f"edge-{index}", agent_id="edge", metrics={"strength": strength})
    results = assemble_results(
        agent_id="edge",
        audit_path=audit,
        net_returns=nets[0],
        provenance=provenances[0],
        registry=registry,
        configs_net=nets,
    )
    passed, report = passes_validation_gate(results, registry=registry)
    assert report.oos_distribution.is_complete()
    assert report.dsr.n_trials == 5
    assert report.wfe.n_windows >= 6
    assert report.cost_provenance is not None
    assert passed is True, report.reject_reasons
    assert report.dsr.probability >= 0.95
    assert report.pbo.pbo <= 0.50
    assert report.wfe.wfe >= 0.5
    assert report.median_oos_after_costs >= 0.0


@pytest.mark.unit
def test_agents_md_requires_gate_first() -> None:
    text = (Path(__file__).resolve().parents[2] / "project-dna" / "lumina" / "AGENTS.md").read_text(encoding="utf-8")
    assert "Every task starts with the Validation Gate" in text
    assert "until that gate exists and its tests pass" in text
