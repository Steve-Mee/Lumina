"""Slice B: Phase 2 audit JSONL + metrics + CLI payload."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
from lumina_core.birth.phase2_autonomy.metrics import (
    compute_phase2_metrics_snapshot,
    phase2_monitoring_path,
    phase2_status_payload,
    record_phase2_decision_monitoring,
)
from lumina_core.birth.phase2_autonomy.orchestrator import Phase2AutonomyOrchestrator


class _FakeTwin:
    def evaluate_dna_promotion(self, _dna: Any) -> dict[str, Any]:
        return {
            "confidence": 0.9,
            "recommendation": True,
            "executable": True,
            "effective_recommendation": True,
            "mode": "full_auto",
            "risk_flags": [],
        }


@pytest.fixture
def mon_ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.mark.unit
def test_record_and_snapshot(mon_ws: Path) -> None:
    record_phase2_decision_monitoring(
        pillar="dynamic_wall",
        allowed=True,
        reason="allowed",
        applied=True,
        apply_requested=True,
        correlation_id="c1",
        stage="STAGE1_TREND",
        twin_conf=0.9,
        mode="sim",
        proposal={"stall_wall_sec_multiplier": 1.1},
        recovery_tag="wall",
    )
    record_phase2_decision_monitoring(
        pillar="dynamic_wall",
        allowed=False,
        reason="twin_low_confidence",
        applied=False,
        apply_requested=True,
        correlation_id="c2",
        stage="STAGE1_TREND",
        recovery_tag="wall",
    )
    path = phase2_monitoring_path()
    assert path.is_file()
    assert "monitoring_phase2_autonomy.jsonl" in str(path)

    snap = compute_phase2_metrics_snapshot(window_hours=24)
    assert snap["phase2_proposals_total"] == 2
    assert snap["phase2_applied_total"] == 1
    assert snap["phase2_apply_rate_pct"] == pytest.approx(50.0)
    assert snap["phase2_gate_reject_by_reason"].get("twin_low_confidence") == 1
    assert "dynamic_wall" in snap["phase2_by_pillar"]
    assert snap["last_decision"]["correlation_id"] == "c2"
    assert snap["empty"] is False


@pytest.mark.unit
def test_orchestrator_writes_audit_when_enabled(mon_ws: Path) -> None:
    features = Phase2AutonomyFeatures(
        enabled=True,
        dynamic_wall_enabled=True,
        require_perfect_birth_flag=False,
        require_perfect_birth_evidence=False,
        require_twin_for_apply=True,
        allow_sim_scaffold=True,
        execution_mode="apply",
    )
    orch = Phase2AutonomyOrchestrator(
        features=features,
        cfg=BirthCurriculumConfig(),
        approval_twin=_FakeTwin(),
        mode="sim",
    )
    decision = orch.evaluate_dynamic_wall(
        correlation_id="aud1",
        stage="STAGE1_TREND",
        stage_trades=40,
        required=100,
        regime="RANGE",
        apply=True,
    )
    assert decision.applied is True
    snap = compute_phase2_metrics_snapshot(window_hours=24)
    assert snap["phase2_proposals_total"] >= 1
    assert snap["phase2_applied_total"] >= 1
    last = snap["last_decision"]
    assert last["pillar"] == "dynamic_wall"
    assert last["applied"] is True
    assert last["apply_requested"] is True
    assert last["proposal_hash"]


@pytest.mark.unit
def test_disabled_orchestrator_skips_audit(mon_ws: Path) -> None:
    orch = Phase2AutonomyOrchestrator(
        features=Phase2AutonomyFeatures(enabled=False),
        mode="sim",
    )
    orch.evaluate_dynamic_wall(stage="S1", apply=False)
    path = phase2_monitoring_path()
    assert not path.is_file() or path.read_text(encoding="utf-8").strip() == ""


@pytest.mark.unit
def test_status_payload_includes_features(mon_ws: Path) -> None:
    record_phase2_decision_monitoring(
        pillar="self_adaptive_params",
        allowed=False,
        reason="feature_disabled",
        applied=False,
    )
    features = Phase2AutonomyFeatures(enabled=False)
    payload = phase2_status_payload(window_hours=24, features=features)
    assert "metrics" in payload
    assert payload["features"]["enabled"] is False
    assert "operator_hint" in payload
