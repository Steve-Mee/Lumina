"""Human gate tests (marker + decision)."""

from __future__ import annotations

from pathlib import Path

from lumina_core.architecture_meta.controller import ArchMutationProposal, ArchMutationType
from lumina_core.architecture_meta.promotion_gate import ArchPromotionGate


def test_write_and_approve_flow(tmp_path: Path):
    gate = ArchPromotionGate(pending_root=tmp_path)
    prop = ArchMutationProposal(
        proposal_id="arch-test-001",
        mutation_type=ArchMutationType.EXTRACT_PURE_HELPER,
        target_file="lumina_core/safety/constitutional_guard.py",
        description="test",
        diff="---\n+++",
        expected_delta=0.2,
        rationale="test",
        before_score=6.0,
    )
    pdir = gate.write_proposal_bundle(prop, {"delta": 0.21}, "readme")
    approved, _ = gate.is_approved("arch-test-001")
    assert not approved

    (pdir / "APPROVED").write_text("approved by test-human for evolvability")
    approved2, approver = gate.is_approved("arch-test-001")
    assert approved2
    assert "test-human" in approver
    applied = gate.apply_if_approved(prop)
    assert applied.approved is False
    assert "COUNCIL" in applied.reason
    (pdir / "COUNCIL.json").write_text('{"allowed": true, "reason": "council"}', encoding="utf-8")
    applied_ok = gate.apply_if_approved(prop)
    assert applied_ok.approved is True
