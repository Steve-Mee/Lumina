"""Fail-closed honesty branches for REAL readiness evidence (SC-3/SC-5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lumina_core.risk.capital_aperture_coverage import aperture_coverage_ready_for_real
from lumina_core.risk.real_multi_gate import real_dna_promotion_allowed
from lumina_core.risk.real_multi_gate_evidence import (
    aperture_readiness_blockers,
    evaluate_dna_human_chain,
    evaluate_final_arbitration_gate,
    evaluate_workspace_recon,
)


def _skip_human(*_a: object, **_k: object) -> tuple[bool, str]:
    return True, "ok_proceed_to_approval_chain"


@pytest.mark.unit
def test_unreadable_workspace_yaml_fail_closed(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("{unclosed: [1, 2", encoding="utf-8")
    recon = evaluate_workspace_recon(tmp_path)
    assert recon["ok"] is False
    assert any(
        str(f).startswith("workspace_config_yaml_unreadable:") for f in recon["failures"]
    )


@pytest.mark.unit
def test_non_mapping_workspace_yaml_fail_closed(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("- not-a-mapping\n", encoding="utf-8")
    recon = evaluate_workspace_recon(tmp_path)
    assert recon["ok"] is False
    assert "workspace_config_yaml_not_mapping" in recon["failures"]


@pytest.mark.unit
def test_recon_gate_exception_fail_closed(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("reconcile_fills: true\n", encoding="utf-8")
    with patch(
        "lumina_core.risk.real_multi_gate_evidence.evaluate_real_broker_recon_gate",
        side_effect=RuntimeError("recon evaluator crashed"),
    ):
        recon = evaluate_workspace_recon(tmp_path)
    assert recon["ok"] is False
    assert any("recon_gate_error:" in str(f) for f in recon["failures"])
    assert "fail-closed" in str(recon["message"]).lower()


@pytest.mark.unit
def test_incomplete_coverage_payload_not_certified_blocker() -> None:
    """Unexpected coverage payload (not empty/thin/hard_fail) still fail-closes."""
    blockers = aperture_readiness_blockers(
        {"reason": "unknown_status", "sample_size": 12, "certified": False},
        ready=False,
    )
    assert blockers == ["aperture_coverage_not_certified:unknown_status"]


@pytest.mark.unit
def test_fa_recon_not_ok_without_failures_fail_closed() -> None:
    aperture = {
        "certified": True,
        "sample_size": 10,
        "min_sample_size": 10,
        "snapshot": {"final_arbitration_sample_size": 10},
    }
    gate = evaluate_final_arbitration_gate(aperture=aperture, recon={"ok": False})
    assert gate["ok"] is False
    assert "broker_recon_not_ok" in gate["blockers"]
    assert gate["coverage_certified"] is True


@pytest.mark.unit
def test_dna_chain_fail_closed_when_promotion_skips_human(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "real:\n  approval_required: true\n",
        encoding="utf-8",
    )
    dna = evaluate_dna_human_chain(tmp_path, promotion_allowed=_skip_human)
    assert dna["ok"] is False
    assert "real_dna_promotion_skips_human" in dna["blockers"]
    assert dna["invariant_blocks_without_human"] is False


@pytest.mark.unit
def test_dna_chain_fail_closed_when_approval_required_missing(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("reconcile_fills: true\n", encoding="utf-8")
    dna = evaluate_dna_human_chain(tmp_path, promotion_allowed=real_dna_promotion_allowed)
    assert dna["ok"] is False
    assert "real.approval_required_not_true" in dna["blockers"]
    assert dna["invariant_blocks_without_human"] is True


@pytest.mark.unit
def test_coverage_ready_fail_closed_on_missing_or_empty_gate() -> None:
    assert aperture_coverage_ready_for_real(None) is False
    assert aperture_coverage_ready_for_real({"sample_size": 0, "ok": True}) is False
    assert aperture_coverage_ready_for_real({"sample_size": 12, "ok": False}) is False
