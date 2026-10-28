"""Wave 0 honesty: twin fail-closed + research lab keep-champion."""

from __future__ import annotations

from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.generation_runner_phases import fail_closed_twin_decision
from lumina_core.evolution.research_lab.cycle import gate_winner


def test_fail_closed_twin_decision_not_true() -> None:
    d = fail_closed_twin_decision("boom")
    assert d["recommendation"] is False
    assert d["effective_recommendation"] is False
    assert d["executable"] is False
    assert "twin_evaluate_failed" in d["risk_flags"]


def test_gate_error_keeps_champion(monkeypatch) -> None:
    champ = PolicyDNA.create(
        prompt_id="champ",
        version="v1",
        content={"n": "c"},
        fitness_score=12.0,
        generation=1,
    )
    chal = PolicyDNA.create(
        prompt_id="chal",
        version="v1",
        content={"n": "h"},
        fitness_score=0.0,
        generation=2,
    )

    def _boom(**_kwargs):  # noqa: ANN003
        raise RuntimeError("gate down")

    monkeypatch.setattr(
        "lumina_core.evolution.research_lab.cycle.apply_champion_challenger_gate",
        _boom,
    )
    dna, fit, decision = gate_winner(
        champion=champ,
        challenger=chal,
        challenger_fitness=99.0,
        previous_fitness=12.0,
        sim_results=None,
        mode="sim",
    )
    assert dna.hash == champ.hash
    assert fit == 12.0
    assert decision.get("keep_champion") is True
    assert decision.get("promote_challenger") is False
