"""Maturation progress SSOT tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lumina_core.maturity.maturation_progress import (
    MaturationPhase,
    load_maturation_progress,
    maturation_eligible_for_real,
    record_maturation_milestone,
    resolve_current_phase,
)
from lumina_core.maturity.milestone_hooks import (
    hook_birth_started,
    hook_evolution_proof_passed,
    hook_promotion_gate_passed,
    hook_sim_real_guard_stable,
)


@pytest.mark.unit
def test_record_milestone_advances_phase(tmp_path: Path) -> None:
    record_maturation_milestone(tmp_path, "genesis_contract_signed")
    record_maturation_milestone(tmp_path, "birth_started")
    progress = load_maturation_progress(tmp_path)
    assert progress.current_phase == MaturationPhase.BIRTH
    assert "birth_started" in progress.milestones_reached


@pytest.mark.unit
def test_resolve_current_phase_picks_highest() -> None:
    from lumina_core.maturity.maturation_progress import MaturationProgress

    progress = MaturationProgress(
        milestones_reached=["birth_started", "evolution_proof_passed"]
    )
    assert resolve_current_phase(progress) == MaturationPhase.AWAKENING


@pytest.mark.unit
def test_first_sim_order_milestone(tmp_path: Path) -> None:
    record_maturation_milestone(tmp_path, "deck_unlocked")
    record_maturation_milestone(tmp_path, "first_sim_order_placed")
    progress = load_maturation_progress(tmp_path)
    assert progress.current_phase == MaturationPhase.PLAYGROUND


@pytest.mark.unit
def test_maturation_eligible_for_real_all_milestones(tmp_path: Path) -> None:
    for mid in (
        "birth_certificate_issued",
        "evolution_proof_passed",
        "sim_real_guard_stable",
        "promotion_gate_passed",
    ):
        record_maturation_milestone(tmp_path, mid)

    with patch(
        "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
        side_effect=lambda _root: load_maturation_progress(tmp_path),
    ), patch(
        "lumina_core.maturity.maturation_progress.sync_stability_milestone",
    ):
        ok, blockers = maturation_eligible_for_real(tmp_path)

    assert ok is True
    assert blockers == []


@pytest.mark.unit
def test_maturation_eligible_for_real_missing_blockers(tmp_path: Path) -> None:
    record_maturation_milestone(tmp_path, "birth_certificate_issued")

    with patch(
        "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
        side_effect=lambda _root: load_maturation_progress(tmp_path),
    ), patch(
        "lumina_core.maturity.maturation_progress.sync_stability_milestone",
    ):
        ok, blockers = maturation_eligible_for_real(tmp_path)

    assert ok is False
    assert len(blockers) >= 2
    assert any("Evolution Proof" in item for item in blockers)


@pytest.mark.unit
def test_milestone_hooks_idempotent(tmp_path: Path) -> None:
    hook_birth_started(tmp_path, training_mode="certified", trade_budget=10_000)
    hook_birth_started(tmp_path, training_mode="certified", trade_budget=10_000)
    progress = load_maturation_progress(tmp_path)
    assert progress.milestones_reached.count("birth_started") == 1

    hook_evolution_proof_passed(tmp_path, oos_winrate=0.5)
    hook_sim_real_guard_stable(tmp_path, consecutive_green_days=5)
    hook_promotion_gate_passed(tmp_path, mode="real", dna_hash="abc")
    progress = load_maturation_progress(tmp_path)
    assert "evolution_proof_passed" in progress.milestones_reached
    assert "sim_real_guard_stable" in progress.milestones_reached
    assert "promotion_gate_passed" in progress.milestones_reached
