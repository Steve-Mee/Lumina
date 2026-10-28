"""Phase D: certificate / Perfect Birth readiness SSOT (never hollow declare)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.maturity_readiness import (
    certificate_path_ready,
    certificate_readiness_blockers,
    maturity_artifact_presence,
)


@pytest.mark.unit
def test_certificate_not_ready_mid_stage2_plateau() -> None:
    blockers = certificate_readiness_blockers(
        stages_passed_count=1,
        plateau_active=True,
        expectancy_stall=True,
        needs_attention=False,
        certificate_present=False,
    )
    assert "curriculum_stages_1/5" in blockers
    assert "plateau_active" in blockers
    assert "expectancy_stall" in blockers
    assert "certificate_absent" in blockers
    assert (
        certificate_path_ready(
            stages_passed_count=1,
            plateau_active=True,
            needs_attention=False,
        )
        is False
    )


@pytest.mark.unit
def test_certificate_path_ready_only_after_full_curriculum_idle() -> None:
    assert (
        certificate_path_ready(
            stages_passed_count=5,
            plateau_active=False,
            needs_attention=False,
        )
        is True
    )
    assert (
        certificate_path_ready(
            stages_passed_count=3,
            plateau_active=False,
            needs_attention=False,
        )
        is False
    )
    assert (
        certificate_path_ready(
            stages_passed_count=5,
            plateau_active=True,
            needs_attention=False,
        )
        is False
    )
    assert (
        certificate_path_ready(
            stages_passed_count=5,
            plateau_active=False,
            needs_attention=True,
        )
        is False
    )


@pytest.mark.unit
def test_maturity_artifact_presence_honest_absence(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    arts = maturity_artifact_presence(tmp_path)
    assert arts["certificate_present"] is False
    assert arts["evolution_proof_present"] is False
    assert arts["perfect_birth_flag_present"] is False
    (tmp_path / "state" / "lumina_birth_certificate.json").write_text("{}", encoding="utf-8")
    arts2 = maturity_artifact_presence(tmp_path)
    assert arts2["certificate_present"] is True
    assert arts2["evolution_proof_present"] is False
