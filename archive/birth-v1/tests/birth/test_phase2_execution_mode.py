"""Slice D: observe / shadow / apply execution modes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.phase2_autonomy.execution_mode import (
    Phase2ExecutionMode,
    evaluate_pillar_promotion,
    execution_mode_rank,
    max_execution_mode,
    normalize_execution_mode,
)
from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
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


def _features(mode: str) -> Phase2AutonomyFeatures:
    return Phase2AutonomyFeatures(
        enabled=True,
        dynamic_wall_enabled=True,
        self_adaptive_params_enabled=True,
        instance_adapt_enabled=True,
        require_perfect_birth_flag=False,
        require_perfect_birth_evidence=False,
        # SIM lab path: apply/shadow still require unlock unless scaffold allowed.
        allow_sim_scaffold=True,
        require_twin_for_apply=True,
        execution_mode=mode,
    )


@pytest.mark.unit
def test_normalize_execution_mode() -> None:
    assert normalize_execution_mode("observe") == Phase2ExecutionMode.OBSERVE
    assert normalize_execution_mode("shadow") == Phase2ExecutionMode.SHADOW
    assert normalize_execution_mode("apply") == Phase2ExecutionMode.APPLY
    assert normalize_execution_mode("bogus") == Phase2ExecutionMode.OBSERVE


@pytest.mark.unit
def test_max_execution_mode_is_monotonic() -> None:
    assert max_execution_mode("observe", "shadow") == Phase2ExecutionMode.SHADOW
    assert max_execution_mode("apply", "observe") == Phase2ExecutionMode.APPLY
    assert max_execution_mode("shadow", "shadow") == Phase2ExecutionMode.SHADOW
    assert execution_mode_rank("apply") > execution_mode_rank("shadow") > execution_mode_rank(
        "observe"
    )


@pytest.mark.unit
def test_observe_never_mutates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    orch = Phase2AutonomyOrchestrator(
        features=_features("observe"),
        cfg=BirthCurriculumConfig(),
        approval_twin=_FakeTwin(),
        mode="sim",
    )
    d = orch.evaluate_dynamic_wall(
        stage="STAGE1_TREND",
        stage_trades=40,
        required=100,
        regime="RANGE",
        apply=True,
    )
    assert d.gate is not None
    # observe: no twin path required; gate may allow without twin
    assert d.applied is False
    assert not d.apply_payload


@pytest.mark.unit
def test_shadow_counterfactual_no_mutate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    orch = Phase2AutonomyOrchestrator(
        features=_features("shadow"),
        cfg=BirthCurriculumConfig(),
        approval_twin=_FakeTwin(),
        mode="sim",
    )
    d = orch.evaluate_dynamic_wall(
        stage="STAGE1_TREND",
        stage_trades=40,
        required=100,
        regime="RANGE",
        apply=True,
    )
    assert d.gate is not None
    assert d.gate.allowed is True
    assert d.applied is False
    assert d.apply_payload  # counterfactual thresholds present
    assert int(d.apply_payload.get("effective_stall_wall_sec", 0)) >= 300


@pytest.mark.unit
def test_apply_mutates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    orch = Phase2AutonomyOrchestrator(
        features=_features("apply"),
        cfg=BirthCurriculumConfig(),
        approval_twin=_FakeTwin(),
        mode="sim",
    )
    d = orch.evaluate_dynamic_wall(
        stage="STAGE1_TREND",
        stage_trades=40,
        required=100,
        regime="RANGE",
        apply=True,
    )
    assert d.applied is True
    assert d.apply_payload


@pytest.mark.unit
def test_pillar_promotion_helper() -> None:
    ok = evaluate_pillar_promotion(
        shadow_samples=10,
        shadow_would_apply=5,
        min_shadow_samples=8,
        min_shadow_would_apply_rate_pct=30.0,
    )
    assert ok["promote_to_apply"] is True

    bad = evaluate_pillar_promotion(
        shadow_samples=2,
        shadow_would_apply=2,
        min_shadow_samples=8,
    )
    assert bad["promote_to_apply"] is False
