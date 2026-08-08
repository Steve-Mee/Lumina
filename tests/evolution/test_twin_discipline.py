"""H4: Twin training discipline gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.evolution.twin_discipline import (
    birth_sim_high_conf_primary_ready,
    full_auto_allowed_for_capital_mode,
    discipline_snapshot,
    twin_primary_judgment_for_decision,
)
from lumina_core.evolution.twin_mode_types import apply_mode_authority
from lumina_core.evolution.twin_mode_controller import TwinModeController
from lumina_core.evolution.twin_mode_promotion_gate_impl import TwinModePromotionGate
from lumina_core.evolution.twin_mode_types import TwinModePromotionEvidence


@pytest.mark.unit
def test_high_conf_primary_requires_assisted_and_labels() -> None:
    bad = birth_sim_high_conf_primary_ready(
        twin_mode="shadow",
        agreement_pct=95.0,
        samples=100,
        steve_label_samples=50,
    )
    assert bad["ready"] is False
    assert "mode_is_shadow" in bad["failures"][0]

    good = birth_sim_high_conf_primary_ready(
        twin_mode="assisted",
        agreement_pct=85.0,
        samples=40,
        steve_label_samples=20,
        false_positive_pct=5.0,
    )
    assert good["ready"] is True


@pytest.mark.unit
def test_full_auto_forbidden_in_real_capital() -> None:
    ok, reason = full_auto_allowed_for_capital_mode("real")
    assert ok is False
    assert "real" in reason
    ok2, _ = full_auto_allowed_for_capital_mode("sim")
    assert ok2 is True


@pytest.mark.unit
def test_gate_rejects_full_auto_without_steve_labels(tmp_path: Path) -> None:
    gate = TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl")
    # Override thresholds via object attrs for unit test
    gate._min_steve_labels_full_auto = 40
    gate._min_samples_full_auto = 10
    gate._min_agreement_full_auto = 50.0
    gate._max_fp_full_auto = 50.0
    gate._min_risk_flags_caught_full_auto = 0
    gate._require_constitution_100 = False

    evidence = TwinModePromotionEvidence(
        current_mode="assisted",
        target_mode="full_auto",
        samples=100,
        agreement_pct=95.0,
        false_positive_pct=1.0,
        constitution_adherence_pct=100.0,
        risk_flags_caught=5,
        constitution_violations=0,
        steve_label_samples=5,  # below 40
        capital_mode="sim",
    )
    decision = gate.evaluate(evidence)
    assert decision.promoted is False
    assert "steve_labels" in decision.fail_reasons


@pytest.mark.unit
def test_gate_rejects_full_auto_in_real_capital(tmp_path: Path) -> None:
    gate = TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl")
    gate._min_steve_labels_full_auto = 1
    gate._min_samples_full_auto = 1
    gate._min_agreement_full_auto = 0.0
    gate._max_fp_full_auto = 100.0
    gate._min_risk_flags_caught_full_auto = 0
    gate._require_constitution_100 = False

    evidence = TwinModePromotionEvidence(
        current_mode="assisted",
        target_mode="full_auto",
        samples=100,
        agreement_pct=99.0,
        false_positive_pct=0.0,
        constitution_adherence_pct=100.0,
        risk_flags_caught=10,
        constitution_violations=0,
        steve_label_samples=50,
        capital_mode="real",
    )
    decision = gate.evaluate(evidence)
    assert decision.promoted is False
    assert "capital_mode_safe" in decision.fail_reasons


@pytest.mark.unit
def test_controller_blocks_full_auto_when_capital_real(tmp_path: Path) -> None:
    from lumina_core.evolution.twin_metrics_store import TwinMetricsStore

    store = TwinMetricsStore(
        path=tmp_path / "metrics.jsonl",
        summary_path=tmp_path / "summary.json",
        audit_path=tmp_path / "audit_m.jsonl",
    )
    ctrl = TwinModeController(
        mode_state_path=tmp_path / "mode.json",
        gate=TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl"),
        metrics_store=store,
        initial_mode="assisted",
    )
    ctrl.force_set_mode("assisted", reason="test")
    ctrl.set_capital_mode_hint("real")
    result = ctrl.try_promote("full_auto")
    assert result["promoted"] is False
    assert "real" in str(result.get("reason", ""))


@pytest.mark.unit
def test_discipline_snapshot_shape() -> None:
    snap = discipline_snapshot(
        twin_mode="shadow",
        capital_mode="sim",
        metrics={"samples": 5, "agreement_pct": 50.0, "steve_label_samples": 2},
    )
    assert snap["schema"] == "twin_discipline_v1"
    assert snap["birth_sim_high_conf_primary"]["ready"] is False
    assert snap["policy"]["full_auto_forbidden_in_real_capital"] is True


@pytest.mark.unit
def test_primary_judgment_ssot_birth_sim_vs_real() -> None:
    """Track D: full_auto high-conf is primary only in birth/SIM, never REAL."""
    ok = twin_primary_judgment_for_decision(
        twin_mode="full_auto",
        twin_confidence=0.92,
        twin_raw_recommendation=True,
        twin_executable=True,
        twin_effective_recommendation=True,
        capital_mode="birth",
        constitution_violations=0,
    )
    assert ok["primary"] is True
    assert "constitution" in ok["never_bypasses"]

    real = twin_primary_judgment_for_decision(
        twin_mode="full_auto",
        twin_confidence=0.99,
        twin_raw_recommendation=True,
        twin_executable=True,
        twin_effective_recommendation=True,
        capital_mode="real",
    )
    assert real["primary"] is False
    assert any("real" in f for f in real["failures"])

    shadow = twin_primary_judgment_for_decision(
        twin_mode="shadow",
        twin_confidence=0.99,
        twin_raw_recommendation=True,
        twin_executable=False,
        twin_effective_recommendation=False,
        capital_mode="sim",
    )
    assert shadow["primary"] is False


@pytest.mark.unit
def test_apply_mode_authority_real_capital_floor() -> None:
    auth = apply_mode_authority(
        raw_recommendation=True,
        mode="full_auto",
        capital_mode="real",
    )
    assert auth["executable"] is False
    assert auth["effective_recommendation"] is False
    assert auth.get("real_capital_floor") is True

    sim = apply_mode_authority(
        raw_recommendation=True,
        mode="full_auto",
        capital_mode="sim",
    )
    assert sim["executable"] is True
    assert sim["effective_recommendation"] is True


@pytest.mark.unit
def test_config_cannot_seed_full_auto(tmp_path: Path) -> None:
    """Track D: missing state + full_auto seed → shadow (promote via gate only)."""
    ctrl = TwinModeController(
        mode_state_path=tmp_path / "missing_mode.json",
        gate=TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl"),
        initial_mode="full_auto",
    )
    assert ctrl.get_mode() == "shadow"
    status = ctrl.status()
    assert status["mode_ssot"]["config_is_seed_only"] is True
    assert status["mode_ssot"]["full_auto_requires_promotion_gate"] is True


@pytest.mark.unit
def test_high_conf_primary_not_ready_in_real_capital() -> None:
    out = birth_sim_high_conf_primary_ready(
        twin_mode="assisted",
        agreement_pct=95.0,
        samples=100,
        steve_label_samples=50,
        capital_mode="real",
    )
    assert out["ready"] is False
    assert any("real" in f for f in out["failures"])


@pytest.mark.unit
def test_twin_promote_ops_report_shape(tmp_path: Path) -> None:
    from lumina_core.evolution.twin_discipline import build_twin_promote_ops_report
    from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
    from lumina_core.evolution.twin_mode_controller import TwinModeController
    from lumina_core.evolution.twin_mode_promotion_gate_impl import TwinModePromotionGate

    store = TwinMetricsStore(
        path=tmp_path / "metrics.jsonl",
        summary_path=tmp_path / "summary.json",
        audit_path=tmp_path / "audit_m.jsonl",
    )
    ctrl = TwinModeController(
        mode_state_path=tmp_path / "mode.json",
        gate=TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl"),
        metrics_store=store,
        initial_mode="shadow",
    )
    ctrl.set_capital_mode_hint("sim")
    report = build_twin_promote_ops_report(controller=ctrl, capital_mode="sim")
    assert report["schema"] == "twin_promote_ops_v1"
    assert report["live_mode"] == "shadow"
    assert report["policy"]["promote_only_via_gate"] is True
    assert report["policy"]["full_auto_forbidden_in_real_capital"] is True
    assert report["readiness"]["full_auto"]["capital_allows"] is True
    assert "promote_assisted" in report["commands"]


@pytest.mark.unit
def test_twin_promote_ops_blocks_full_auto_capital_real(tmp_path: Path) -> None:
    from lumina_core.evolution.twin_discipline import build_twin_promote_ops_report
    from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
    from lumina_core.evolution.twin_mode_controller import TwinModeController
    from lumina_core.evolution.twin_mode_promotion_gate_impl import TwinModePromotionGate

    store = TwinMetricsStore(
        path=tmp_path / "m.jsonl",
        summary_path=tmp_path / "s.json",
        audit_path=tmp_path / "a.jsonl",
    )
    ctrl = TwinModeController(
        mode_state_path=tmp_path / "mode.json",
        gate=TwinModePromotionGate(audit_path=tmp_path / "audit.jsonl"),
        metrics_store=store,
        initial_mode="assisted",
    )
    ctrl.force_set_mode("assisted", reason="test")
    ctrl.set_capital_mode_hint("real")
    report = build_twin_promote_ops_report(controller=ctrl, capital_mode="real")
    assert report["readiness"]["full_auto"]["capital_allows"] is False
    assert report["live_mode"] == "assisted"
    # ladder item full_auto_not_in_real should pass (mode not full_auto under real)
    item = next(x for x in report["ladder"] if x["id"] == "full_auto_not_in_real")
    assert item["ok"] is True
