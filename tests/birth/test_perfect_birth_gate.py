"""Slice C: Perfect Birth conjunction + declare path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.perfect_birth_gate import (
    MILESTONE_ID,
    PerfectBirthKpis,
    declare_perfect_birth,
    evaluate_perfect_birth_conjunction,
    perfect_birth_unlock_valid,
)


def _passing_kpis() -> PerfectBirthKpis:
    return PerfectBirthKpis(
        certificate_valid=True,
        constitution_violations=0,
        twin_steve_agreement_pct=85.0,
        twin_samples=40,
        autonomous_recovery_rate_pct=90.0,
        autonomous_recovery_attempts=12,
        auto_approved_pct=70.0,
        auto_approved_decisions=30,
        shadow_twin_alignment_pct=80.0,
        shadow_samples=10,
        terminal_notify_recent=0,
    )


@pytest.mark.unit
def test_conjunction_passes_all_kpis() -> None:
    result = evaluate_perfect_birth_conjunction(_passing_kpis())
    assert result.passed is True
    assert result.failures == []


@pytest.mark.unit
def test_conjunction_fails_on_low_twin() -> None:
    kpis = PerfectBirthKpis(
        certificate_valid=True,
        twin_steve_agreement_pct=50.0,
        twin_samples=40,
        autonomous_recovery_rate_pct=90.0,
        autonomous_recovery_attempts=12,
        auto_approved_pct=70.0,
        auto_approved_decisions=30,
        shadow_twin_alignment_pct=80.0,
        shadow_samples=10,
    )
    result = evaluate_perfect_birth_conjunction(kpis)
    assert result.passed is False
    assert any("twin_steve_agreement" in f for f in result.failures)


@pytest.mark.unit
def test_declare_writes_flag_and_evidence(tmp_path: Path) -> None:
    payload = declare_perfect_birth(
        tmp_path,
        kpis=_passing_kpis(),
        force=False,
        record_maturity=True,
    )
    assert payload["declared"] is True
    assert payload["passed"] is True
    flag = tmp_path / "state" / "perfect_birth_complete.flag"
    # declare uses DEFAULT_FLAG_REL under workspace
    flag = Path(payload["flag_path"])
    evidence = Path(payload["evidence_path"])
    assert flag.is_file()
    assert evidence.is_file()
    data = json.loads(evidence.read_text(encoding="utf-8"))
    assert data["passed"] is True

    ok, detail = perfect_birth_unlock_valid(
        flag_path=flag,
        require_evidence=True,
    )
    assert ok is True
    assert detail == "ok"

    # maturity milestone recorded
    maturity = tmp_path / "state" / "lumina_maturity_progress.json"
    if maturity.is_file():
        raw = json.loads(maturity.read_text(encoding="utf-8"))
        assert MILESTONE_ID in (raw.get("milestones_reached") or [])


@pytest.mark.unit
def test_declare_blocked_without_force(tmp_path: Path) -> None:
    weak = PerfectBirthKpis(certificate_valid=False)
    payload = declare_perfect_birth(tmp_path, kpis=weak, force=False, record_maturity=False)
    assert payload["declared"] is False
    assert payload["passed"] is False
    assert not (tmp_path / "state" / "perfect_birth_complete.flag").is_file()


@pytest.mark.unit
def test_force_declares_with_audit(tmp_path: Path) -> None:
    weak = PerfectBirthKpis(certificate_valid=False)
    payload = declare_perfect_birth(tmp_path, kpis=weak, force=True, record_maturity=False)
    assert payload["declared"] is True
    assert payload["forced"] is True
    assert Path(payload["flag_path"]).is_file()


@pytest.mark.unit
def test_hollow_flag_without_evidence_invalid(tmp_path: Path) -> None:
    flag = tmp_path / "perfect_birth_complete.flag"
    flag.write_text("now\n", encoding="utf-8")
    ok, detail = perfect_birth_unlock_valid(flag_path=flag, require_evidence=True)
    assert ok is False
    assert "evidence" in detail
