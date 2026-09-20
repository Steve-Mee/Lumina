"""H2: REAL multi-gate non-bypassable; Twin judgment inside gates only."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lumina_core.maturity.maturation_progress import (
    REAL_ELIGIBILITY_MILESTONES,
    load_maturation_progress,
    record_maturation_milestone,
)
from lumina_core.risk.capital_aperture_lineage import append_lineage_audit_record
from lumina_core.risk.real_multi_gate import (
    assert_twin_cannot_authorize_real_mode,
    evaluate_real_capital_readiness,
    real_dna_promotion_allowed,
    real_mode_switch_allowed,
    run_real_multi_gate_dry_run,
    twin_judgment_subordinate_to_real_gates,
)

_REAL_READY_YAML = """
reconcile_fills: true
reconciliation_method: websocket
reconciliation_timeout_seconds: 15
real:
  approval_required: true
broker:
  live_provider: ninjatrader
  ninjatrader:
    enabled: true
"""

_NO_BIRTH_SYNC = patch(
    "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
    side_effect=lambda root: None,
)
_NO_STABILITY = patch(
    "lumina_core.maturity.maturation_progress.sync_stability_milestone",
)
_LOAD_PROGRESS_ONLY = patch(
    "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
    side_effect=lambda root: load_maturation_progress(root),
)


def _write_decision_log(
    root: Path,
    n: int,
    *,
    with_ctx: bool = True,
    stage: str = "final_arbitration",
) -> None:
    for i in range(n):
        record: dict[str, str] = {"stage": stage}
        if with_ctx:
            record["decision_context_id"] = f"ctx-{i}"
        append_lineage_audit_record(root, record)


def _record_real_eligibility(root: Path, *, human: bool) -> None:
    for mid in REAL_ELIGIBILITY_MILESTONES:
        record_maturation_milestone(root, mid)
    if human:
        record_maturation_milestone(root, "human_real_approval")


@pytest.mark.unit
def test_twin_full_auto_cannot_authorize_real_capital() -> None:
    result = twin_judgment_subordinate_to_real_gates(
        twin_recommendation=True,
        twin_executable=True,
        twin_mode="full_auto",
        capital_mode="real",
    )
    assert result["executable"] is False
    assert result["effective_recommendation"] is False
    assert result["real_capital_floor"] is True
    assert_twin_cannot_authorize_real_mode(twin_full_auto=True, twin_recommendation=True)


@pytest.mark.unit
def test_twin_full_auto_can_execute_judgment_in_sim() -> None:
    result = twin_judgment_subordinate_to_real_gates(
        twin_recommendation=True,
        twin_executable=True,
        twin_mode="full_auto",
        capital_mode="sim",
    )
    assert result["effective_recommendation"] is True
    assert result["executable"] is True
    assert result["real_capital_floor"] is False


@pytest.mark.unit
def test_real_dna_promotion_requires_human() -> None:
    ok, reason = real_dna_promotion_allowed(
        mode="real",
        require_human_approval=False,
        explicit_human_approval=True,
        base_promoted=True,
        has_approval_signatures=True,
    )
    assert ok is False
    assert reason == "real_human_approval_mandatory"

    ok2, reason2 = real_dna_promotion_allowed(
        mode="real",
        require_human_approval=True,
        explicit_human_approval=False,
        base_promoted=True,
        has_approval_signatures=False,
    )
    assert ok2 is False
    assert "explicit_human" in reason2 or "signatures" in reason2

    ok3, reason3 = real_dna_promotion_allowed(
        mode="real",
        require_human_approval=True,
        explicit_human_approval=False,
        base_promoted=True,
        has_approval_signatures=True,
    )
    assert ok3 is True
    assert "approval_chain" in reason3


@pytest.mark.unit
def test_real_mode_switch_requires_human_and_maturation(tmp_path: Path) -> None:
    with _NO_BIRTH_SYNC, _NO_STABILITY:
        ok, blockers = real_mode_switch_allowed(tmp_path)
    assert ok is False
    assert any("approval" in b.lower() or "Birth" in b or "Evolution" in b for b in blockers)

    _record_real_eligibility(tmp_path, human=False)
    with _LOAD_PROGRESS_ONLY, _NO_STABILITY:
        ok2, blockers2 = real_mode_switch_allowed(tmp_path)
        assert ok2 is False
        assert any("approval" in b.lower() for b in blockers2)

        record_maturation_milestone(tmp_path, "human_real_approval")
        ok3, blockers3 = real_mode_switch_allowed(tmp_path)
        assert ok3 is False
        assert any(
            "empty_decision_log" in b or "final_arbitration" in b or "aperture" in b
            for b in blockers3
        )


@pytest.mark.unit
def test_empty_decision_log_not_ready_for_real_capital(tmp_path: Path) -> None:
    _record_real_eligibility(tmp_path, human=True)
    (tmp_path / "config.yaml").write_text(_REAL_READY_YAML, encoding="utf-8")
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "decision_log.jsonl").write_text("", encoding="utf-8")
    with _LOAD_PROGRESS_ONLY, _NO_STABILITY:
        snap = evaluate_real_capital_readiness(tmp_path)
    assert snap["ready_for_real_capital"] is False
    aperture = snap["gates"]["capital_aperture_lineage"]
    assert aperture["ok"] is False
    assert aperture["soft_pass"] is True
    assert aperture["certified"] is False
    assert aperture["ops_status"] == "yellow"
    assert snap["gates"]["final_arbitration"]["ok"] is False
    assert "empty_decision_log_not_ready" in snap["blockers"]


@pytest.mark.unit
def test_soft_pass_thin_samples_not_ready_for_real(tmp_path: Path) -> None:
    _record_real_eligibility(tmp_path, human=True)
    (tmp_path / "config.yaml").write_text(_REAL_READY_YAML, encoding="utf-8")
    _write_decision_log(tmp_path, 3)
    with _LOAD_PROGRESS_ONLY, _NO_STABILITY:
        snap = evaluate_real_capital_readiness(tmp_path)
    assert snap["ready_for_real_capital"] is False
    aperture = snap["gates"]["capital_aperture_lineage"]
    assert aperture["ok"] is False
    assert aperture["soft_pass"] is True
    assert aperture["ops_status"] == "yellow"
    assert any("soft_pass" in b for b in snap["blockers"])


@pytest.mark.unit
def test_certified_coverage_recon_and_human_can_ready(tmp_path: Path) -> None:
    _record_real_eligibility(tmp_path, human=True)
    (tmp_path / "config.yaml").write_text(_REAL_READY_YAML, encoding="utf-8")
    _write_decision_log(tmp_path, 10)
    with _LOAD_PROGRESS_ONLY, _NO_STABILITY:
        snap = evaluate_real_capital_readiness(tmp_path)
    assert snap["ready_for_real_capital"] is True
    assert snap["blockers"] == []
    gates = snap["gates"]
    assert gates["maturation_eligible"]["ok"] is True
    assert gates["human_real_approval"]["ok"] is True
    assert gates["capital_aperture_lineage"]["ok"] is True
    assert gates["capital_aperture_lineage"]["soft_pass"] is False
    assert gates["capital_aperture_lineage"]["certified"] is True
    assert gates["final_arbitration"]["ok"] is True
    assert gates["real_dna_human_approval_chain"]["ok"] is True
    assert snap["broker_recon"]["ok"] is True


@pytest.mark.unit
def test_readiness_snapshot_does_not_hardcode_aperture_fa_dna_ok(tmp_path: Path) -> None:
    with _NO_BIRTH_SYNC, _NO_STABILITY:
        snap = evaluate_real_capital_readiness(tmp_path)
    assert snap["twin_can_bypass"] is False
    assert snap["policy"]["human_required_for_real_mode"] is True
    assert snap["policy"]["soft_pass_is_ops_yellow_not_real_green"] is True
    assert snap["ready_for_real_capital"] is False
    gates = snap["gates"]
    assert gates["capital_aperture_lineage"]["ok"] is False
    assert gates["final_arbitration"]["ok"] is False
    assert gates["real_dna_human_approval_chain"]["ok"] is False


@pytest.mark.unit
def test_readiness_snapshot_flags_twin_cannot_bypass(tmp_path: Path) -> None:
    with _NO_BIRTH_SYNC, _NO_STABILITY:
        snap = evaluate_real_capital_readiness(tmp_path)
    assert snap["twin_can_bypass"] is False
    assert snap["policy"]["human_required_for_real_mode"] is True
    assert snap["ready_for_real_capital"] is False


@pytest.mark.unit
def test_real_multi_gate_dry_run_invariants(tmp_path: Path) -> None:
    with _NO_BIRTH_SYNC, _NO_STABILITY:
        dry = run_real_multi_gate_dry_run(tmp_path)
    assert dry["schema"] == "real_multi_gate_dry_run_v1"
    assert dry["ok"] is True  # invariants hold
    assert dry["ready_for_real_capital"] is False  # empty workspace not ready
    assert dry["invariants"]["twin_cannot_authorize_real"] is True
    assert dry["invariants"]["real_dna_requires_human"] is True
    assert dry["invariants"]["recon_evaluated"] is True
    assert dry["policy"]["never_arms_real"] is True
    assert dry["twin_floor"]["real_capital_floor"] is True
    assert dry["aperture_coverage"]["certified"] is False
    assert dry["aperture_coverage"]["soft_pass"] is True
    assert dry["broker_recon"]["ok"] is False


@pytest.mark.unit
def test_below_target_coverage_not_ready_for_real(tmp_path: Path) -> None:
    """N≥min with coverage below target is hard-fail, never REAL-green."""
    _record_real_eligibility(tmp_path, human=True)
    (tmp_path / "config.yaml").write_text(_REAL_READY_YAML, encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir(parents=True)
    rows = [json.dumps({"decision_context_id": f"c{i}", "stage": "x"}) for i in range(8)]
    rows.extend(json.dumps({"stage": "no_ctx"}) for _ in range(4))
    (state / "decision_log.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    with _LOAD_PROGRESS_ONLY, _NO_STABILITY:
        snap = evaluate_real_capital_readiness(tmp_path)
    assert snap["ready_for_real_capital"] is False
    aperture = snap["gates"]["capital_aperture_lineage"]
    assert aperture["ok"] is False
    assert aperture["certified"] is False
    assert snap["aperture_coverage"]["hard_fail"] is True
    assert any("aperture_coverage_below_target" in b for b in snap["blockers"])


@pytest.mark.unit
def test_reconcile_fills_not_declared_fail_closed(tmp_path: Path) -> None:
    """Missing reconcile_fills must not be treated as REAL recon-ready."""
    _record_real_eligibility(tmp_path, human=True)
    (tmp_path / "config.yaml").write_text(
        "real:\n  approval_required: true\n",
        encoding="utf-8",
    )
    with _LOAD_PROGRESS_ONLY, _NO_STABILITY:
        snap = evaluate_real_capital_readiness(tmp_path)
    assert snap["ready_for_real_capital"] is False
    recon = snap["broker_recon"]
    assert recon["ok"] is False
    assert "reconcile_fills_not_declared" in recon["failures"]
    assert any("broker_recon:reconcile_fills_not_declared" in b for b in snap["blockers"])


@pytest.mark.unit
def test_approval_required_not_true_blocks_dna_gate(tmp_path: Path) -> None:
    """Workspace real.approval_required must be true — false is not REAL-green."""
    _record_real_eligibility(tmp_path, human=True)
    yaml_text = _REAL_READY_YAML.replace("approval_required: true", "approval_required: false")
    (tmp_path / "config.yaml").write_text(yaml_text, encoding="utf-8")
    _write_decision_log(tmp_path, 10)
    with _LOAD_PROGRESS_ONLY, _NO_STABILITY:
        snap = evaluate_real_capital_readiness(tmp_path)
    assert snap["ready_for_real_capital"] is False
    dna = snap["gates"]["real_dna_human_approval_chain"]
    assert dna["ok"] is False
    assert "real.approval_required_not_true" in dna["blockers"]
    assert snap["gates"]["capital_aperture_lineage"]["ok"] is True
    assert snap["gates"]["final_arbitration"]["ok"] is True


@pytest.mark.unit
def test_dry_run_fail_closed_when_aperture_or_recon_not_dict(tmp_path: Path) -> None:
    """Malformed readiness evidence must not crash or count as recon-ok."""
    malformed = {
        "ready_for_real_capital": False,
        "blockers": ["malformed_readiness_evidence"],
        "twin_can_bypass": False,
        "aperture_coverage": None,
        "broker_recon": None,
    }
    with (
        _NO_BIRTH_SYNC,
        _NO_STABILITY,
        patch(
            "lumina_core.risk.real_multi_gate.evaluate_real_capital_readiness",
            return_value=malformed,
        ),
    ):
        dry = run_real_multi_gate_dry_run(tmp_path)
    assert dry["ready_for_real_capital"] is False
    assert dry["aperture_coverage"]["certified"] is None
    assert dry["broker_recon"]["ok"] is False
    assert "recon_not_evaluated" in dry["broker_recon"]["failures"]
    assert dry["invariants"]["recon_evaluated"] is True
