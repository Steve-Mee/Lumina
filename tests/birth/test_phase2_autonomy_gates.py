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
        require_perfect_birth_evidence=True,
        execution_mode="apply",
    )
    base.update(kwargs)
    return Phase2AutonomyFeatures(**base)


def _apply_lab_features(**kwargs: Any) -> Phase2AutonomyFeatures:
    """SIM scaffold lab features — for gates other than Perfect Birth."""
    return _features(
        allow_sim_scaffold=True,
        require_twin_for_apply=False,
        **kwargs,
    )


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
        features=_apply_lab_features(),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        mode="sim",
        constitution_violations=2,
        require_apply_path=True,
    )
    assert res.allowed is False
    assert res.reason == Phase2GateReason.CONSTITUTION_BLOCKED.value


@pytest.mark.unit
def test_explore_pass_sim_twin_preference_not_required() -> None:
    """ADR-0038: pure SIM Phase2 is explore_pass — Twin preference is not a rem."""
    res = evaluate_phase2_gate(
        features=_features(allow_sim_scaffold=True, require_twin_for_apply=True),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        mode="sim",
        approval_twin=None,
        require_apply_path=True,
    )
    assert res.allowed is True
    assert res.reason == Phase2GateReason.ALLOWED.value


@pytest.mark.unit
def test_explore_pass_sim_ignores_twin_low_confidence_and_veto() -> None:
    twin = _FakeTwin(confidence=0.5, recommendation=False, executable=False, mode="shadow")
    res = evaluate_phase2_gate(
        features=_features(allow_sim_scaffold=True),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        mode="sim",
        approval_twin=twin,
        require_apply_path=True,
    )
    assert res.allowed is True
    assert res.reason == Phase2GateReason.ALLOWED.value


@pytest.mark.unit
def test_sim_real_guard_phase2_apply_still_mode_blocked() -> None:
    """Dress rehearsal / REAL-like modes cannot use Phase2 apply path (existing SSOT)."""
    twin = _FakeTwin(confidence=0.95, recommendation=True)
    res = evaluate_phase2_gate(
        features=_features(allow_sim_scaffold=True),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        mode="sim_real_guard",
        approval_twin=twin,
        require_apply_path=True,
    )
    assert res.allowed is False
    # Mode gate fires before twin preference (SIM/birth only for Phase2 apply)
    assert res.allowed is False


@pytest.mark.unit
def test_forbidden_param_rejects() -> None:
    prop = Phase2ParamAdjustmentProposal(
        changes={"max_risk_percent": 0.05},
        rationale="bad",
    )
    res = evaluate_phase2_gate(
        features=_apply_lab_features(),
        pillar=Phase2Pillar.SELF_ADAPTIVE_PARAMS,
        mode="sim",
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
def test_allowed_with_perfect_birth_evidence_and_twin(tmp_path: Path) -> None:
    from lumina_core.birth.perfect_birth_gate import PerfectBirthKpis, declare_perfect_birth

    kpis = PerfectBirthKpis(
        certificate_valid=True,
        constitution_violations=0,
        twin_steve_agreement_pct=85.0,
        twin_samples=40,
        autonomous_recovery_rate_pct=90.0,
        autonomous_recovery_attempts=12,
        auto_approved_pct=70.0,
        auto_approved_decisions=30,
        shadow_twin_alignment_pct=80.0,
        shadow_samples=10,
        terminal_notify_recent=0,
    )
    declared = declare_perfect_birth(
        tmp_path, kpis=kpis, force=False, record_maturity=False
    )
    flag = Path(declared["flag_path"])
    twin = _FakeTwin()
    prop = Phase2WallAdjustmentProposal(
        stall_wall_sec_multiplier=1.1,
        stagnation_rollouts_delta=1,
        rationale="test",
    )
    res = evaluate_phase2_gate(
        features=_features(perfect_birth_flag_path=str(flag)),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        approval_twin=twin,
        proposal=prop,
        require_apply_path=True,
        constitution_violations=0,
        mode="sim",
    )
    assert res.allowed is True
    assert res.reason == Phase2GateReason.ALLOWED.value


@pytest.mark.unit
def test_apply_path_rejects_hollow_flag_even_if_evidence_flag_disabled(
    tmp_path: Path,
) -> None:
    """Track B: apply cannot use hollow flag when yaml would disable evidence."""
    flag = tmp_path / "perfect_birth_complete.flag"
    flag.write_text("2026-07-20T00:00:00+00:00\n", encoding="utf-8")
    res = evaluate_phase2_gate(
        features=_features(
            perfect_birth_flag_path=str(flag),
            require_perfect_birth_evidence=False,
            require_twin_for_apply=False,
        ),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        require_apply_path=True,
        mode="sim",
        constitution_violations=0,
    )
    assert res.allowed is False
    assert res.reason in {
        Phase2GateReason.PERFECT_BIRTH_EVIDENCE.value,
        Phase2GateReason.PERFECT_BIRTH_REQUIRED.value,
    }


@pytest.mark.unit
def test_apply_path_ignores_require_flag_false_without_scaffold(tmp_path: Path) -> None:
    """Track B: require_perfect_birth_flag=False does not unlock apply without scaffold."""
    res = evaluate_phase2_gate(
        features=_features(
            require_perfect_birth_flag=False,
            require_twin_for_apply=False,
            perfect_birth_flag_path=str(tmp_path / "missing.flag"),
        ),
        pillar=Phase2Pillar.DYNAMIC_WALL,
        require_apply_path=True,
        mode="sim",
        constitution_violations=0,
    )
    assert res.allowed is False
    assert res.reason in {
        Phase2GateReason.PERFECT_BIRTH_EVIDENCE.value,
        Phase2GateReason.PERFECT_BIRTH_REQUIRED.value,
    }


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
