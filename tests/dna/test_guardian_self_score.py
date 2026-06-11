"""Phase 3 D6: Guardian self-score tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dna_guardian"))

from guardian_self_score import (  # noqa: E402
    collect_phase3_aperture_panel,
    enrich_report_with_phase3_panel,
    score_guardian_aperture_self_consistency,
)


@pytest.mark.unit
def test_score_clean_report_high():
    report = {
        "overall_status": "PASS",
        "summary": {"failed": 0},
        "aperture_integrity": {"score": 10.0, "fatal_count": 0},
        "d5_capital_aperture": {"ok": True, "scan": {"scanned_files": 100}},
        "phase3_aperture_panel": {
            "d3_violations": [],
            "d1_ctx_count": 3,
            "d4_bundle_present": True,
        },
    }
    result = score_guardian_aperture_self_consistency(report)
    assert result["overall_score"] >= 9.0
    assert result["status"] == "GREEN"
    assert result["d3_violation_count"] == 0


@pytest.mark.unit
def test_score_degraded_d5_and_d3():
    report = {
        "overall_status": "PASS",
        "summary": {"failed": 0},
        "aperture_integrity": {"score": 10.0},
        "d5_capital_aperture": {"ok": False},
        "phase3_aperture_panel": {
            "d3_violations": ["missing fill lineage ctx=x"],
            "d1_ctx_count": 0,
            "d4_bundle_present": False,
        },
    }
    result = score_guardian_aperture_self_consistency(report)
    assert result["overall_score"] < 8.0
    assert result["d3_violation_count"] == 1


@pytest.mark.unit
def test_collect_panel_on_repo():
    panel = collect_phase3_aperture_panel(repo_root=ROOT)
    assert "d3_violations" in panel
    assert "d1_ctx_count" in panel
    if list((ROOT / "state" / "audits").glob("d4_genuine_campaign_evidence_*.md")):
        assert panel.get("d4_bundle_present") is True


@pytest.mark.unit
def test_enrich_report_integration():
    report = {
        "overall_status": "PASS",
        "summary": {"failed": 0},
        "aperture_integrity": {"score": 10.0, "fatal_count": 0},
        "d5_capital_aperture": {"ok": True},
    }
    enrich_report_with_phase3_panel(report, repo_root=ROOT, d1_audits=True)
    assert "phase3_aperture_panel" in report
    assert "guardian_self_score" in report
    assert "overall_score" in report["guardian_self_score"]
    print("MANUAL_SMOKE_D6_SELF_SCORE_SUCCESS")
