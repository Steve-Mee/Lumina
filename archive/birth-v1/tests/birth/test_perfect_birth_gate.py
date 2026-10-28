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
    perfect_birth_status,
    perfect_birth_unlock_valid,
    phase2_shadow_campaign_profile,
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
def test_force_declares_with_audit_but_does_not_unlock(tmp_path: Path) -> None:
    """Track B: force writes audited flag/evidence but never unlocks Phase 2."""
    weak = PerfectBirthKpis(certificate_valid=False)
    payload = declare_perfect_birth(tmp_path, kpis=weak, force=True, record_maturity=False)
    assert payload["declared"] is True
    assert payload["forced"] is True
    assert Path(payload["flag_path"]).is_file()
    ok, detail = perfect_birth_unlock_valid(
        flag_path=Path(payload["flag_path"]),
        require_evidence=True,
    )
    assert ok is False
    assert "forced" in detail or "not_valid" in detail or "not_passed" in detail


@pytest.mark.unit
def test_hollow_flag_without_evidence_invalid(tmp_path: Path) -> None:
    flag = tmp_path / "perfect_birth_complete.flag"
    flag.write_text("now\n", encoding="utf-8")
    ok, detail = perfect_birth_unlock_valid(flag_path=flag, require_evidence=True)
    assert ok is False
    assert "evidence" in detail


@pytest.mark.unit
def test_perfect_birth_status_shows_failures(tmp_path: Path) -> None:
    status = perfect_birth_status(tmp_path)
    assert status["would_pass"] is False
    assert isinstance(status["failures"], list)
    assert len(status["failures"]) >= 1
    assert "phase2_shadow_profile" in status
    assert status["phase2_shadow_profile"]["phase2_execution_mode"] == "shadow"
    assert status["unlock_valid"] is False


@pytest.mark.unit
def test_phase2_shadow_profile_never_apply_default() -> None:
    profile = phase2_shadow_campaign_profile()
    assert profile["phase2_execution_mode"] == "shadow"
    assert profile["phase2_require_perfect_birth_evidence"] is True


@pytest.mark.unit
def test_maybe_auto_declare_disabled_by_default(tmp_path: Path) -> None:
    from lumina_core.birth.perfect_birth_gate import maybe_auto_declare_perfect_birth

    out = maybe_auto_declare_perfect_birth(tmp_path, force_enabled=False)
    assert out["declared"] is False
    assert out["reason"] == "auto_declare_disabled"
    assert not (tmp_path / "state" / "perfect_birth_complete.flag").is_file()


@pytest.mark.unit
def test_maybe_auto_declare_when_enabled_and_kpis_pass(tmp_path: Path) -> None:
    from lumina_core.birth.perfect_birth_gate import maybe_auto_declare_perfect_birth

    # Without KPIs: conjunction fails — no hollow flag
    first = maybe_auto_declare_perfect_birth(tmp_path, force_enabled=True)
    assert first.get("declared") is False
    assert not (tmp_path / "state" / "perfect_birth_complete.flag").is_file()

    # With injected passing KPIs: auto-declare writes flag+evidence
    declared = maybe_auto_declare_perfect_birth(
        tmp_path, force_enabled=True, kpis=_passing_kpis()
    )
    assert declared["declared"] is True
    assert declared["passed"] is True
    assert declared.get("auto_declare") is True
    assert Path(declared["flag_path"]).is_file()

    # Second call is no-op (already unlocked)
    again = maybe_auto_declare_perfect_birth(tmp_path, force_enabled=True)
    assert again["declared"] is False
    assert again["reason"] == "already_unlocked"

    from lumina_core.maturity.continuum import load_continuum

    assert load_continuum(tmp_path).get("advance_mode") == "auto_evolve"


@pytest.mark.unit
def test_maybe_auto_declare_explicit_false_ignores_fabric_bundle(tmp_path: Path) -> None:
    from lumina_core.birth.fabric_foundation_bundle import PRE_DECLARE_KEYS
    from lumina_core.birth.perfect_birth_gate import maybe_auto_declare_perfect_birth

    path = tmp_path / "state" / "fabric_foundation_bundle.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({key: True for key in PRE_DECLARE_KEYS}),
        encoding="utf-8",
    )
    out = maybe_auto_declare_perfect_birth(
        tmp_path, force_enabled=False, kpis=_passing_kpis()
    )
    assert out["declared"] is False
    assert out["reason"] == "auto_declare_disabled"


@pytest.mark.unit
def test_status_includes_missing_sources_and_capital_safe(tmp_path: Path) -> None:
    status = perfect_birth_status(tmp_path, auto_declare_enabled=False)
    assert "missing_sources" in status
    assert status["capital_mode_safe"] is True
    assert status["auto_declare_enabled"] is False
    assert isinstance(status["next_step"], str)


@pytest.mark.unit
def test_campaign_report_checklist_and_actions(tmp_path: Path) -> None:
    from lumina_core.birth.perfect_birth_gate import build_perfect_birth_campaign_report

    report = build_perfect_birth_campaign_report(tmp_path, kpis=PerfectBirthKpis())
    assert report["schema"] == "perfect_birth_campaign_v1"
    assert report["unlock_valid"] is False
    assert report["checklist_total"] >= 10
    assert report["checklist_passed"] < report["checklist_total"]
    assert report["policy"]["hollow_flag_forbidden"] is True
    assert report["capital_mode_safe"] is True
    assert any(a for a in report["ordered_actions"])


@pytest.mark.unit
def test_campaign_report_ready_to_declare_when_kpis_pass(tmp_path: Path) -> None:
    from lumina_core.birth.perfect_birth_gate import build_perfect_birth_campaign_report

    report = build_perfect_birth_campaign_report(tmp_path, kpis=_passing_kpis())
    assert report["would_pass"] is True
    assert report["campaign_ready_to_declare"] is True
    assert report["unlock_valid"] is False
    assert any("declare_perfect_birth" in a for a in report["ordered_actions"])


@pytest.mark.unit
def test_campaign_report_unlocked_after_declare(tmp_path: Path) -> None:
    from lumina_core.birth.perfect_birth_gate import build_perfect_birth_campaign_report

    declare_perfect_birth(
        tmp_path, kpis=_passing_kpis(), force=False, record_maturity=False
    )
    report = build_perfect_birth_campaign_report(tmp_path, kpis=_passing_kpis())
    assert report["unlock_valid"] is True
    assert report["ok"] is True
    assert report["campaign_ready_to_declare"] is False


@pytest.mark.unit
def test_yaml_coercion_cannot_drop_perfect_birth_evidence_requirements() -> None:
    """Track B: config coercion clamps require flag+evidence to True."""
    from lumina_core.birth.config_coercion_curriculum_tail import curriculum_kwargs

    kwargs = curriculum_kwargs(
        {
            "phase2_require_perfect_birth_flag": False,
            "phase2_require_perfect_birth_evidence": False,
            "phase2_allow_sim_scaffold": True,
        }
    )
    assert kwargs["phase2_require_perfect_birth_flag"] is True
    assert kwargs["phase2_require_perfect_birth_evidence"] is True
    assert kwargs["phase2_allow_sim_scaffold"] is True


@pytest.mark.unit
def test_conjunction_fails_on_needs_attention_via_terminal_notify() -> None:
    kpis = PerfectBirthKpis(
        certificate_valid=True,
        twin_steve_agreement_pct=85.0,
        twin_samples=40,
        autonomous_recovery_rate_pct=90.0,
        autonomous_recovery_attempts=12,
        auto_approved_pct=70.0,
        auto_approved_decisions=30,
        shadow_twin_alignment_pct=80.0,
        shadow_samples=10,
        terminal_notify_recent=1,
    )
    result = evaluate_perfect_birth_conjunction(kpis)
    assert result.passed is False
    assert any("terminal_notify" in f for f in result.failures)
