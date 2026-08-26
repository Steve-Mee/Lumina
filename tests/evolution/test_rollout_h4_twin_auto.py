"""H4: Twin-gated non-radical / SIM auto-apply; radical+constitution stays human."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.evolution.rollout import EvolutionRolloutFramework


@pytest.mark.unit
def test_non_radical_sim_auto_allows(tmp_path: Path) -> None:
    fw = EvolutionRolloutFramework(audit_path=tmp_path / "rollout.jsonl")
    d = fw.evaluate_promotion(
        mode="sim",
        previous_fitness=0.40,
        winner_fitness=0.42,
        shadow_status="ok",
        shadow_passed=True,
        explicit_human_approval=False,
        twin_risk_flags=[],
        twin_confidence=0.9,
        twin_recommendation=True,
    )
    assert d.allow_promotion is True
    assert d.radical_mutation is False
    assert d.live_orders_blocked is True


@pytest.mark.unit
def test_radical_paper_pending_without_twin(tmp_path: Path) -> None:
    fw = EvolutionRolloutFramework(audit_path=tmp_path / "rollout.jsonl")
    d = fw.evaluate_promotion(
        mode="paper",
        previous_fitness=0.20,
        winner_fitness=0.60,  # large delta → radical
        shadow_status="ok",
        shadow_passed=True,
        explicit_human_approval=False,
        twin_risk_flags=[],
        twin_confidence=0.5,
        twin_recommendation=True,
    )
    assert d.radical_mutation is True
    # ADR-0037: birth/SIM/paper judgment → Twin (or escalation), not free-form human
    assert d.stage == "pending_twin_judgment"
    assert d.allow_promotion is False


@pytest.mark.unit
def test_twin_high_conf_auto_on_paper_without_constitution_flags(tmp_path: Path) -> None:
    fw = EvolutionRolloutFramework(audit_path=tmp_path / "rollout.jsonl")
    d = fw.evaluate_promotion(
        mode="paper",
        previous_fitness=0.20,
        winner_fitness=0.60,
        shadow_status="ok",
        shadow_passed=True,
        explicit_human_approval=False,
        twin_risk_flags=[],
        twin_confidence=0.85,
        twin_recommendation=True,
    )
    assert d.allow_promotion is True
    assert d.reason == "twin_gated_sim_auto_apply"
    assert d.live_orders_blocked is True


@pytest.mark.unit
def test_constitution_flag_blocks_twin_auto(tmp_path: Path) -> None:
    fw = EvolutionRolloutFramework(audit_path=tmp_path / "rollout.jsonl")
    d = fw.evaluate_promotion(
        mode="paper",
        previous_fitness=0.20,
        winner_fitness=0.60,
        shadow_status="ok",
        shadow_passed=True,
        explicit_human_approval=False,
        twin_risk_flags=["constitution_veto_post_twin"],
        twin_confidence=0.99,
        twin_recommendation=True,
    )
    assert d.allow_promotion is False
    # Constitution/capital risk flags → hard block (never Twin-auto)
    assert d.stage == "blocked_constitution_or_capital_risk"


@pytest.mark.unit
def test_real_radical_never_twin_auto(tmp_path: Path) -> None:
    fw = EvolutionRolloutFramework(audit_path=tmp_path / "rollout.jsonl")
    d = fw.evaluate_promotion(
        mode="real",
        previous_fitness=0.20,
        winner_fitness=0.60,
        shadow_status="ok",
        shadow_passed=True,
        explicit_human_approval=False,
        twin_risk_flags=[],
        twin_confidence=0.99,
        twin_recommendation=True,
    )
    assert d.allow_promotion is False
    assert d.live_orders_blocked is True
    assert d.stage == "pending_human_approval"
    assert "real_capital" in d.reason
