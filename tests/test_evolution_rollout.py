from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.evolution.rollout import EvolutionRolloutFramework


@pytest.mark.unit
def test_real_mode_requires_shadow_before_promotion(tmp_path: Path) -> None:
    framework = EvolutionRolloutFramework(audit_path=tmp_path / "rollout.jsonl")
    decision = framework.evaluate_promotion(
        mode="real",
        previous_fitness=1.0,
        winner_fitness=1.05,
        shadow_status="pending",
        shadow_passed=False,
        explicit_human_approval=True,
        twin_risk_flags=[],
        selected_variant={"score": 1.05},
        all_variants=[{"score": 1.0}, {"score": 1.05}],
    )
    assert not decision.allow_promotion
    assert decision.stage == "shadow_validation"
    assert decision.live_orders_blocked


@pytest.mark.unit
def test_radical_mutation_requires_human_approval(tmp_path: Path) -> None:
    framework = EvolutionRolloutFramework(audit_path=tmp_path / "rollout.jsonl")
    decision = framework.evaluate_promotion(
        mode="real",
        previous_fitness=1.0,
        winner_fitness=1.8,
        shadow_status="passed",
        shadow_passed=True,
        explicit_human_approval=False,
        twin_risk_flags=["radical_position_resize"],
        selected_variant={"score": 1.8},
        all_variants=[{"score": 1.0}, {"score": 1.8}],
    )
    assert not decision.allow_promotion
    assert decision.radical_mutation
    assert decision.human_approval_required
    assert not decision.human_approval_granted
    assert decision.stage == "pending_human_approval"


@pytest.mark.unit
def test_real_mode_promotion_allowed_when_shadow_and_human_pass(tmp_path: Path) -> None:
    framework = EvolutionRolloutFramework(audit_path=tmp_path / "rollout.jsonl")
    decision = framework.evaluate_promotion(
        mode="real",
        previous_fitness=1.0,
        winner_fitness=1.2,
        shadow_status="passed",
        shadow_passed=True,
        explicit_human_approval=True,
        twin_risk_flags=[],
        selected_variant={"score": 1.2},
        all_variants=[{"score": 1.0}, {"score": 1.2}, {"score": 0.9}],
    )
    assert decision.allow_promotion
    assert decision.stage == "ready_for_promotion"
    assert decision.ab_verdict == "variant_beats_ab_mean"


@pytest.mark.unit
def test_rollout_decision_is_appended_to_audit_log(tmp_path: Path) -> None:
    audit_path = tmp_path / "rollout.jsonl"
    framework = EvolutionRolloutFramework(audit_path=audit_path)
    framework.evaluate_promotion(
        mode="sim",
        previous_fitness=1.0,
        winner_fitness=1.01,
        shadow_status="not_required",
        shadow_passed=False,
        explicit_human_approval=False,
        twin_risk_flags=[],
        selected_variant={"score": 1.01},
        all_variants=[{"score": 1.0}, {"score": 1.01}],
    )

    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event"] == "rollout_decision"
    assert payload["mode"] == "sim"
