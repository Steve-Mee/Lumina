"""Wired evaluate_candidate → gate → fitness → propose_research_order."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_research.propose import propose_research_order
from lumina_research.risk_core import DecisionKind, OrderProposal, RiskCore, load_default_config
from lumina_research.validation.pipeline import evaluate_candidate, missing_evaluation
from lumina_research.validation.trial_registry import TrialRegistry
from tests.research.synthetic import always_long, constant_markets, costed, noise_returns


def _proposal() -> OrderProposal:
    return OrderProposal(
        agent_id="edge",
        instrument="MES",
        side="buy",
        quantity=1.0,
        price=5000.0,
        notional=1_000.0,
        cluster_id="es_family",
        submitted_at_utc=datetime.now(timezone.utc),
    )


@pytest.mark.unit
def test_evaluate_candidate_wires_costs_registry_gate_and_fitness(tmp_path: Path) -> None:
    audit = tmp_path / "pipe.jsonl"
    registry = TrialRegistry(audit)
    n = 360
    eps = noise_returns(n=n, sigma=0.008, seed=3)
    positions = always_long(n)
    markets = constant_markets(n)
    peers: list[tuple[float, ...]] = []
    for strength in (0.85, 0.7, 0.55, 0.4):
        gross = tuple(0.004 * strength + eps[i] for i in range(n))
        net, _prov = costed(gross, positions)
        peers.append(net)
        registry.record(config_id=f"peer-{strength}", agent_id="edge", metrics={"strength": strength})
    candidate_gross = tuple(0.004 + eps[i] for i in range(n))
    evaluation = evaluate_candidate(
        agent_id="edge",
        config_id="edge-0",
        gross_returns=candidate_gross,
        positions=positions,
        markets=markets,
        spec="MES",
        registry=registry,
        peer_net_returns=peers,
        audit_path=audit,
        market_returns=candidate_gross,
    )
    assert evaluation.results.cost_provenance is not None
    assert evaluation.results.cost_provenance.is_valid()
    assert evaluation.report.oos_distribution.is_complete()
    assert evaluation.report.dsr.n_trials == registry.n_trials
    assert "oos_distribution" in evaluation.report.to_audit_metrics()
    assert "dsr" in evaluation.report.to_audit_metrics()
    assert "pbo" in evaluation.report.to_audit_metrics()
    events = audit.read_text(encoding="utf-8")
    assert '"event": "trial"' in events
    assert '"event": "gate"' in events
    if evaluation.passed:
        assert evaluation.fitness is not None

    core = RiskCore(load_default_config(), equity=100_000.0)
    core.heartbeat(datetime.now(timezone.utc))
    if not evaluation.passed:
        decision = propose_research_order(_proposal(), core=core, evaluation=evaluation)
        assert decision.kind is DecisionKind.REJECTED
        assert decision.reason == "validation_gate"
    else:
        decision = propose_research_order(_proposal(), core=core, evaluation=evaluation)
        assert decision.kind is DecisionKind.APPROVED


@pytest.mark.unit
def test_failed_gate_blocks_propose_even_if_risk_would_approve(tmp_path: Path) -> None:
    audit = tmp_path / "fail.jsonl"
    registry = TrialRegistry(audit)
    evaluation = missing_evaluation(agent_id="overfit", audit_path=audit, registry=registry)
    assert evaluation.passed is False
    core = RiskCore(load_default_config(), equity=100_000.0)
    core.heartbeat(datetime.now(timezone.utc))
    decision = propose_research_order(_proposal(), core=core, evaluation=evaluation)
    assert decision.kind is DecisionKind.REJECTED
    assert decision.reason == "validation_gate"
