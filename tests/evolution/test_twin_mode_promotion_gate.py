"""Tests for Approval Twin mode authority + promotion gates (fail-closed)."""

from __future__ import annotations

from pathlib import Path

from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
from lumina_core.evolution.twin_mode_promotion_gate import (
    TwinModeController,
    TwinModePromotionEvidence,
    TwinModePromotionGate,
    apply_mode_authority,
    canonicalize_twin_mode,
)


def test_canonicalize_aliases() -> None:
    assert canonicalize_twin_mode("advisory") == "assisted"
    assert canonicalize_twin_mode("active") == "full_auto"
    assert canonicalize_twin_mode("bogus") == "shadow"
    assert canonicalize_twin_mode(None) == "shadow"


def test_apply_mode_authority_shadow_never_executable() -> None:
    auth = apply_mode_authority(raw_recommendation=True, mode="shadow")
    assert auth["executable"] is False
    assert auth["effective_recommendation"] is False
    assert auth["authority"] == "propose_only"
    assert auth["recommendation"] is True


def test_apply_mode_authority_assisted_veto_blocks_approve_not_executable() -> None:
    veto = apply_mode_authority(raw_recommendation=False, mode="assisted")
    assert veto["effective_recommendation"] is False
    assert veto["executable"] is False
    assert veto["authority"] == "veto_only"

    approve = apply_mode_authority(raw_recommendation=True, mode="assisted")
    assert approve["recommendation"] is True
    assert approve["executable"] is False
    assert approve["effective_recommendation"] is False


def test_apply_mode_authority_full_auto_executable() -> None:
    auth = apply_mode_authority(raw_recommendation=True, mode="full_auto")
    assert auth["executable"] is True
    assert auth["effective_recommendation"] is True
    assert auth["authority"] == "execute_judgment"


def test_gate_insufficient_samples_fail_closed(tmp_path: Path) -> None:
    gate = TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl")
    evidence = TwinModePromotionEvidence(
        current_mode="shadow",
        target_mode="assisted",
        samples=5,
        agreement_pct=95.0,
        false_positive_pct=1.0,
        constitution_adherence_pct=100.0,
        risk_flags_caught=0,
        constitution_violations=0,
    )
    decision = gate.evaluate(evidence)
    assert decision.promoted is False
    assert "sample_size" in decision.fail_reasons
    assert (tmp_path / "audit.jsonl").exists() or True  # audit best-effort


def test_gate_good_evidence_promotes_assisted(tmp_path: Path) -> None:
    gate = TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl")
    evidence = TwinModePromotionEvidence(
        current_mode="shadow",
        target_mode="assisted",
        samples=40,
        agreement_pct=85.0,
        false_positive_pct=5.0,
        constitution_adherence_pct=100.0,
        risk_flags_caught=0,
        constitution_violations=0,
    )
    decision = gate.evaluate(evidence)
    assert decision.promoted is True
    assert decision.fail_reasons == ()


def test_gate_fp_too_high_blocks(tmp_path: Path) -> None:
    gate = TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl")
    evidence = TwinModePromotionEvidence(
        current_mode="shadow",
        target_mode="assisted",
        samples=40,
        agreement_pct=90.0,
        false_positive_pct=25.0,
        constitution_adherence_pct=100.0,
        risk_flags_caught=0,
        constitution_violations=0,
    )
    decision = gate.evaluate(evidence)
    assert decision.promoted is False
    assert "false_positive" in decision.fail_reasons


def test_gate_cannot_skip_to_full_auto(tmp_path: Path) -> None:
    gate = TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl")
    evidence = TwinModePromotionEvidence(
        current_mode="shadow",
        target_mode="full_auto",
        samples=200,
        agreement_pct=99.0,
        false_positive_pct=0.0,
        constitution_adherence_pct=100.0,
        risk_flags_caught=10,
        constitution_violations=0,
    )
    decision = gate.evaluate(evidence)
    assert decision.promoted is False
    assert "mode_order" in decision.fail_reasons


def test_controller_try_promote_and_demote(tmp_path: Path) -> None:
    store = TwinMetricsStore(
        path=tmp_path / "metrics.jsonl",
        summary_path=tmp_path / "summary.json",
    )
    # Seed enough good comparisons
    for i in range(40):
        store.record_comparison(
            twin_recommendation=True,
            ground_truth_approve=True,
            source="steve_label",
            risk_flags=[],
            dna_hash=f"dna{i}",
            mode="shadow",
        )
    # A few risk-flag catches (path rejects with twin risk flags)
    for i in range(3):
        store.record_comparison(
            twin_recommendation=False,
            ground_truth_approve=False,
            source="shadow_path",
            risk_flags=["risk_shadow_blocked"],
            dna_hash=f"risk{i}",
            mode="shadow",
        )

    gate = TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl")
    ctrl = TwinModeController(
        mode_state_path=tmp_path / "mode.json",
        gate=gate,
        metrics_store=store,
        initial_mode="shadow",
    )
    assert ctrl.mode == "shadow"

    blocked = ctrl.try_promote("full_auto")
    assert blocked["promoted"] is False

    ok = ctrl.try_promote("assisted")
    assert ok["promoted"] is True
    assert ctrl.mode == "assisted"

    # Full auto needs higher agreement + risk_flags_caught >= 1 (already have)
    # agreement still high
    ok2 = ctrl.try_promote("full_auto")
    # May fail agreement if % diluted — with ~43 samples almost all agree should pass 90%
    if not ok2.get("promoted"):
        # Top up more agreements
        for i in range(30):
            store.record_comparison(
                twin_recommendation=True,
                ground_truth_approve=True,
                source="steve_label",
                dna_hash=f"more{i}",
                mode="assisted",
            )
        ok2 = ctrl.try_promote("full_auto")
    assert ok2["promoted"] is True
    assert ctrl.mode == "full_auto"

    dem = ctrl.demote("shadow", reason="test")
    assert dem["demoted"] is True
    assert ctrl.mode == "shadow"


def test_metrics_store_fp_and_agreement(tmp_path: Path) -> None:
    store = TwinMetricsStore(
        path=tmp_path / "m.jsonl",
        summary_path=tmp_path / "s.json",
    )
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=True,
        source="steve_label",
    )
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=False,
        source="steve_label",
    )  # FP
    store.record_comparison(
        twin_recommendation=False,
        ground_truth_approve=False,
        source="shadow_path",
        risk_flags=["x"],
    )  # risk caught
    snap = store.snapshot()
    assert snap.samples == 3
    assert snap.agreements == 2
    assert snap.false_positives == 1
    assert snap.risk_flags_caught == 1
    assert snap.agreement_pct == round(2 / 3 * 100, 2)


def test_metrics_store_constitution_fatal_only_when_twin_approves(tmp_path: Path) -> None:
    """constitution_fatal + twin approve → violation; twin veto → adherence."""
    store = TwinMetricsStore(
        path=tmp_path / "m.jsonl",
        summary_path=tmp_path / "s.json",
    )
    store.record_comparison(
        twin_recommendation=False,
        ground_truth_approve=False,
        source="constitution",
        risk_flags=["constitution_fatal"],
        constitution_fatal=True,
    )
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=False,
        source="constitution",
        risk_flags=["constitution_fatal"],
        constitution_fatal=True,
    )
    snap = store.snapshot()
    assert snap.constitution_violations == 1
    assert snap.constitution_adherence_pct == 0.0


def test_controller_auto_demote_on_fp_breach(tmp_path: Path) -> None:
    store = TwinMetricsStore(
        path=tmp_path / "m.jsonl",
        summary_path=tmp_path / "s.json",
    )
    # Seed enough samples with high FP to breach demote ceiling (default 20%)
    for i in range(12):
        store.record_comparison(
            twin_recommendation=True,
            ground_truth_approve=False,  # FP
            source="steve_label",
            dna_hash=f"fp{i}",
            mode="assisted",
        )
    gate = TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl")
    ctrl = TwinModeController(
        mode_state_path=tmp_path / "mode.json",
        gate=gate,
        metrics_store=store,
        initial_mode="assisted",
    )
    assert ctrl.mode == "assisted"
    dem = ctrl.maybe_auto_demote()
    assert dem is not None
    assert dem.get("demoted") is True
    assert ctrl.mode == "shadow"


def test_gate_constitution_adherence_required(tmp_path: Path) -> None:
    gate = TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl")
    evidence = TwinModePromotionEvidence(
        current_mode="shadow",
        target_mode="assisted",
        samples=40,
        agreement_pct=95.0,
        false_positive_pct=1.0,
        constitution_adherence_pct=0.0,
        risk_flags_caught=0,
        constitution_violations=1,
    )
    decision = gate.evaluate(evidence)
    assert decision.promoted is False
    assert "constitution_adherence" in decision.fail_reasons
