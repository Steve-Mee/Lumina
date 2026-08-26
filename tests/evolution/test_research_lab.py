"""Strategy Research Lab — catalog seeds + champion-challenger."""
from __future__ import annotations

from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA
from lumina_core.evolution.research_lab.catalog import CATALOG_SEEDS, inject_catalog_challengers
from lumina_core.evolution.research_lab.champion_challenger import champion_challenger_decision
from lumina_core.evolution.research_lab.cycle import gate_winner, research_lab_enabled


def test_catalog_has_named_families() -> None:
    families = {str(s["strategy_family"]) for s in CATALOG_SEEDS}
    assert "trend" in families
    assert "vwap" in families
    assert "mean_reversion" in families
    assert "orb" in families
    assert "session" in families


def test_inject_catalog_challengers_adds_seeds(tmp_path) -> None:
    reg = DNARegistry(jsonl_path=tmp_path / "dna.jsonl", sqlite_path=tmp_path / "dna.sqlite")
    base = PolicyDNA.create(
        prompt_id="active",
        version="v1",
        content={"candidate_name": "champ"},
        fitness_score=1.0,
        generation=1,
    )
    out = inject_catalog_challengers(reg, [base], generation_offset=0, max_inject=2)
    assert len(out) == 3
    assert any(str(c.prompt_id).startswith("catalog:") for c in out)


def test_champion_holds_on_untruthful_fitness() -> None:
    champ = PolicyDNA.create(
        prompt_id="champ",
        version="v1",
        content={"candidate_name": "champ"},
        fitness_score=12.0,
        generation=1,
    )
    chal = PolicyDNA.create(
        prompt_id="chal",
        version="v1",
        content={"candidate_name": "chal"},
        fitness_score=0.0,
        generation=2,
    )
    decision = champion_challenger_decision(
        champion=champ,
        challenger=chal,
        challenger_fitness=float("-inf"),
        previous_fitness=12.0,
    )
    assert decision["keep_champion"] is True
    assert decision["truthful_fitness"] is False
    assert decision["promote_challenger"] is False


def test_challenger_wins_on_truthful_lift() -> None:
    champ = PolicyDNA.create(
        prompt_id="champ",
        version="v1",
        content={"candidate_name": "champ"},
        fitness_score=1.0,
        generation=1,
    )
    chal = PolicyDNA.create(
        prompt_id="chal",
        version="v1",
        content={"candidate_name": "chal"},
        fitness_score=0.0,
        generation=2,
    )
    dna, fit, decision = gate_winner(
        champion=champ,
        challenger=chal,
        challenger_fitness=5.0,
        previous_fitness=1.0,
        sim_results=None,
        mode="sim",
    )
    assert dna.hash == chal.hash
    assert fit == 5.0
    assert decision["promote_challenger"] is True


def test_research_lab_disabled_in_real() -> None:
    assert research_lab_enabled("sim") is True
    assert research_lab_enabled("birth") is True
    assert research_lab_enabled("real") is False
    assert research_lab_enabled("live") is False


def test_research_lab_axis_never_auto_in_real() -> None:
    from lumina_core.architecture_meta.evolution_axes import axis_allowed_for_mode

    sim = axis_allowed_for_mode("strategy_research_lab", capital_mode="sim")
    assert sim["allowed"] is True
    assert sim.get("auto") is True
    real = axis_allowed_for_mode("strategy_research_lab", capital_mode="real")
    assert real.get("auto") is False
