"""H7 / ADR-0036: Birth exit is survival — not Perfect Birth / REAL / promotion."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.maturity.birth_exit import (
    POST_BIRTH_ONLY_MILESTONES,
    assert_milestone_not_birth_exit_gate,
    birth_exit_policy_dict,
    birth_exit_status_payload,
    effective_stage1_floors,
    evaluate_birth_exit,
    is_birth_exit_sufficient,
)
from lumina_core.maturity.maturation_progress import (
    MaturationPhase,
    MaturationProgress,
    save_maturation_progress,
)
from lumina_core.maturity.phase_specs import evaluate_exit_proofs


def test_policy_excludes_perfect_birth_and_real() -> None:
    pol = birth_exit_policy_dict()
    denied = set(pol["birth_exit_does_not_require"])
    assert "perfect_birth_flag" in denied
    assert "promotion_gate_passed" in denied or "promotion_gate_passed" in POST_BIRTH_ONLY_MILESTONES
    assert "real_capital" in denied
    assert pol["after_birth"]["next_phase"] == "awakening"
    assert assert_milestone_not_birth_exit_gate("perfect_birth_autonomy_proven")
    assert assert_milestone_not_birth_exit_gate("promotion_gate_passed")
    assert not assert_milestone_not_birth_exit_gate("birth_certificate_issued")


def test_survival_floors_default_not_skill() -> None:
    floors = effective_stage1_floors(None)
    assert floors["mode"] == "survival"
    assert floors["wr_floor"] == pytest.approx(0.20)
    assert floors["expectancy_floor"] == pytest.approx(-0.50)
    assert floors["skill_floors_deferred"]["wr_floor"] == pytest.approx(0.35)


def test_birth_exit_false_without_artifacts(tmp_path: Path) -> None:
    d = evaluate_birth_exit(tmp_path)
    assert d.exited is False
    assert d.missing
    assert is_birth_exit_sufficient(tmp_path) is False


def test_birth_exit_true_with_completed_flag_only(tmp_path: Path) -> None:
    """Curriculum complete is enough — no Perfect Birth required."""
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "lumina_birth_completed.flag").write_text("ok", encoding="utf-8")
    # Post-birth milestones present must not block
    save_maturation_progress(
        tmp_path,
        MaturationProgress(
            current_phase=MaturationPhase.BIRTH,
            milestones_reached=[
                "birth_started",
                "perfect_birth_autonomy_proven",  # must not be required
                "promotion_gate_passed",
            ],
        ),
    )
    d = evaluate_birth_exit(tmp_path)
    assert d.exited is True
    assert "birth_curriculum_complete" in d.proofs or "birth_artifacts_ok" in d.proofs
    # Conflation list may include post-birth milestones (informational)
    assert "perfect_birth_autonomy_proven" in d.conflation_blockers
    assert d.next_phase == "awakening"

    ok, missing, learned = evaluate_exit_proofs(tmp_path, "birth")
    assert ok is True
    assert missing == []
    assert learned.get("birth_exit", {}).get("exited") is True


def test_birth_exit_status_payload_shape(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True)
    (tmp_path / "state" / "lumina_birth_completed.flag").write_text("1", encoding="utf-8")
    payload = birth_exit_status_payload(tmp_path)
    assert payload["schema"] == "birth_exit_v1"
    assert payload["exited"] is True
    assert payload["perfect_birth_required_for_birth_exit"] is False
    assert payload["real_eligible_required_for_birth_exit"] is False


def test_certificate_file_counts_as_exit(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "birth_certificate.json").write_text("{}", encoding="utf-8")
    d = evaluate_birth_exit(tmp_path)
    assert d.exited is True
    assert "birth_certificate_issued" in d.proofs
