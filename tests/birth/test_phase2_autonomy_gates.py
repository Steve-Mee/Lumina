"""Fail-closed multi-gate tests for Phase 2 Autonomy."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.phase2_autonomy.contracts import (
    Phase2GateReason,
    Phase2InstanceAdaptProposal,
    Phase2ParamAdjustmentProposal,
    Phase2Pillar,
    Phase2WallAdjustmentProposal,
)
from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
from lumina_core.birth.phase2_autonomy.gates import evaluate_phase2_gate


def _features(**kwargs: Any) -> Phase2AutonomyFeatures:
    base = dict(
        enabled=True,
        dynamic_wall_enabled=True,
        self_adaptive_params_enabled=True,
        instance_adapt_enabled=True,
        require_perfect_birth_flag=True,
        allow_sim_scaffold=False,
        require_twin_for_apply=True,
        require_perfect_birth_evidence=False,
        execution_mode="apply",
    )
    base.update(kwargs)
    return Phase2AutonomyFeatures(**base)


class _FakeTwin:
    def __init__(
        self,
        *,
        confidence: float = 0.9,
        recommendation: bool = True,
        executable: bool = True,
        effective: bool = True,
        mode: str = "full_auto",
    ) -> None:
        self.mode = mode
        self._confidence = confidence
        self._recommendation = recommendation
        self._executable = executable
        self._effective = effective

    def evaluate_dna_promotion(self, _dna: Any) -> dict[str, Any]:
        return {
            "confidence": self._confidence,
            "recommendation": self._recommendation,
            "executable": self._executable,
            "effective_recommendation": self._effective,
            "mode": self.mode,
            "risk_flags": [],
        }


@pytest.mark.unit
def test_master_flag_off_rejects() -> None:
    res = evaluate_phase2_gate(
        features=_features(enabled=False),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        require_apply_path=False,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.FEATURE_DISABLED.value


@pytest.mark.unit
def test_pillar_flag_off_rejects() -> None:
    res = evaluate_phase2_gate(
        features=_features(dynamic_wall_enabled=False),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        require_apply_path=False,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.PILLAR_DISABLED.value


@pytest.mark.unit
def test_perfect_birth_required_without_flag(tmp_path: Path) -> None:
    flag = tmp_path / "missing.flag"
    res = evaluate_phase2_gate(
        features=_features(perfect_birth_flag_path=str(flag)),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        mode="sim",
        require_apply_path=False,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.PERFECT_BIRTH_REQUIRED.value


@pytest.mark.unit
def test_sim_scaffold_bypasses_perfect_birth(tmp_path: Path) -> None:
    flag = tmp_path / "missing.flag"
    res = evaluate_phase2_gate(
        features=_features(
            perfect_birth_flag_path=str(flag),
            allow_sim_scaffold=True,
            require_twin_for_apply=False,
        ),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        mode="sim",
        require_apply_path=True,
        constitution_violations=0,
    )
    assert res.allowed is True
    assert res.reason == Phase2GateReason.ALLOWED.value


@pytest.mark.unit
def test_constitution_blocks_apply() -> None:
    res = evaluate_phase2_gate(
        features=_features(require_perfect_birth_flag=False, require_twin_for_apply=False),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        constitution_violations=2,
        require_apply_path=True,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.CONSTITUTION_BLOCKED.value


@pytest.mark.unit
def test_twin_required_when_missing() -> None:
    res = evaluate_phase2_gate(
        features=_features(require_perfect_birth_flag=False, require_twin_for_apply=True),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        approval_twin=None,
        require_apply_path=True,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.TWIN_REQUIRED.value


@pytest.mark.unit
def test_twin_low_confidence_rejects() -> None:
    twin = _FakeTwin(confidence=0.5, recommendation=True)
    res = evaluate_phase2_gate(
        features=_features(require_perfect_birth_flag=False),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        approval_twin=twin,
        require_apply_path=True,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.TWIN_LOW_CONFIDENCE.value


@pytest.mark.unit
def test_twin_high_conf_veto_rejects() -> None:
    twin = _FakeTwin(confidence=0.95, recommendation=False)
    res = evaluate_phase2_gate(
        features=_features(require_perfect_birth_flag=False),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        approval_twin=twin,
        require_apply_path=True,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.TWIN_VETO.value


@pytest.mark.unit
def test_twin_not_executable_rejects() -> None:
    twin = _FakeTwin(confidence=0.9, executable=False, effective=False, mode="shadow")
    res = evaluate_phase2_gate(
        features=_features(require_perfect_birth_flag=False),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        approval_twin=twin,
        require_apply_path=True,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.TWIN_NOT_EXECUTABLE.value


@pytest.mark.unit
def test_forbidden_param_rejects() -> None:
    prop = Phase2ParamAdjustmentProposal(
        changes={"max_risk_percent": 0.05},
        rationale="bad",
    )
    res = evaluate_phase2_gate(
        features=_features(require_perfect_birth_flag=False, require_twin_for_apply=False),
        pillar=Phase2Pillar.SELF_ADAPTIVE_PARAMS,
        proposal=prop,
        require_apply_path=True,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.FORBIDDEN_PARAM.value


@pytest.mark.unit
def test_wall_multiplier_out_of_bounds_rejects() -> None:
    prop = Phase2WallAdjustmentProposal(stall_wall_sec_multiplier=2.0)
    res = evaluate_phase2_gate(
        features=_features(require_perfect_birth_flag=False, require_twin_for_apply=False),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        proposal=prop,
        require_apply_path=False,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.OUT_OF_BOUNDS.value


@pytest.mark.unit
def test_instance_risk_surface_rejects() -> None:
    prop = Phase2InstanceAdaptProposal(action="broker_spawn", risk_touching=False)
    res = evaluate_phase2_gate(
        features=_features(require_perfect_birth_flag=False, require_twin_for_apply=False),
        pillar=Phase2Pillar.INSTANCE_ADAPT,
        proposal=prop,
        require_apply_path=False,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.RISK_SURFACE.value


@pytest.mark.unit
def test_allowed_with_perfect_birth_flag_and_twin(tmp_path: Path) -> None:
    flag = tmp_path / "perfect_birth_complete.flag"
    flag.write_text("2026-07-20T00:00:00+00:00\n", encoding="utf-8")
    twin = _FakeTwin()
    prop = Phase2WallAdjustmentProposal(
        stall_wall_sec_multiplier=1.1,
        stagnation_rollouts_delta=1,
        rationale="test",
    )
    res = evaluate_phase2_gate(
        features=_features(
            perfect_birth_flag_path=str(flag),
            require_perfect_birth_evidence=False,
        ),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        approval_twin=twin,
        proposal=prop,
        require_apply_path=True,
        constitution_violations=0,
    )
    assert res.allowed is True
    assert res.reason == Phase2GateReason.ALLOWED.value


@pytest.mark.unit
def test_hollow_flag_rejected_when_evidence_required(tmp_path: Path) -> None:
    flag = tmp_path / "perfect_birth_complete.flag"
    flag.write_text("2026-07-20T00:00:00+00:00\n", encoding="utf-8")
    res = evaluate_phase2_gate(
        features=_features(
            perfect_birth_flag_path=str(flag),
            require_perfect_birth_evidence=True,
            require_twin_for_apply=False,
        ),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        require_apply_path=False,
        mode="sim",
    )
    assert res.allowed is False
    assert res.reason in {
        Phase2GateReason.PERFECT_BIRTH_EVIDENCE.value,
        Phase2GateReason.PERFECT_BIRTH_REQUIRED.value,
    }
