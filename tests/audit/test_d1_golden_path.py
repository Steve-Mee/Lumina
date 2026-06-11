"""Phase 3 D1 golden path tests (genuine D4 campaign integration)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.audit.d1_golden_path import (
    load_genuine_d4_context_ids,
    run_d1_golden_path_verify,
    validate_artifact_contract,
    verify_d1_context,
)

ROOT = Path(__file__).resolve().parents[2]
AUDITS = ROOT / "state" / "audits"


@pytest.mark.unit
def test_validate_artifact_contract_accepts_minimal_shape():
    artifact = {
        "decision_context_id": "test-ctx",
        "generated_at": "2026-06-04T00:00:00Z",
        "summary": {},
        "constitution_checks": [],
        "risk_numbers": {},
        "agent_dna_lineage": {},
        "execution": {},
        "aperture_context": {},
        "lineage_chain": [],
        "raw_sources": {},
        "missing_data": [],
    }
    assert validate_artifact_contract(artifact, ctx="test-ctx") == []


@pytest.mark.unit
def test_load_genuine_d4_context_ids_from_repo():
    ctxs, meta = load_genuine_d4_context_ids(audits_dir=AUDITS)
    if not ctxs:
        pytest.skip("no d4_genuine_campaign_evidence_*.json in state/audits")
    assert len(ctxs) >= 8
    assert "evidence_path" in meta
    assert any("genuine_evo" in c for c in ctxs)


@pytest.mark.unit
def test_verify_d1_context_on_genuine_sample():
    ctxs, _ = load_genuine_d4_context_ids(audits_dir=AUDITS)
    if not ctxs:
        pytest.skip("no genuine D4 evidence")
    ctx = ctxs[0]
    result = verify_d1_context(ctx, export=False)
    assert result["ctx"] == ctx
    assert result["ok"] is True
    assert result["issues"] == []


@pytest.mark.unit
def test_run_d1_golden_path_verify_integration():
    if not list(AUDITS.glob("d4_genuine_campaign_evidence_*.json")):
        pytest.skip("no genuine D4 evidence bundle")
    result = run_d1_golden_path_verify(
        repo_root=ROOT,
        audits_dir=AUDITS,
        min_verified=3,
        sample_unsafe=2,
        export=False,
    )
    assert result["ok"] is True
    assert result["verified_count"] >= 3
    print("MANUAL_SMOKE_D1_GOLDEN_PATH_SUCCESS")
