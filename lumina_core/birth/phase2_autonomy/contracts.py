"""Typed proposal and gate contracts for Phase 2 Autonomy (fail-closed)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Phase2Pillar(str, Enum):
    DYNAMIC_WALL = "dynamic_wall"
    SELF_ADAPTIVE_PARAMS = "self_adaptive_params"
    INSTANCE_ADAPT = "instance_adapt"


class Phase2GateReason(str, Enum):
    ALLOWED = "allowed"
    FEATURE_DISABLED = "feature_disabled"
    PILLAR_DISABLED = "pillar_disabled"
    PERFECT_BIRTH_REQUIRED = "perfect_birth_required"
    CONSTITUTION_BLOCKED = "constitution_blocked"
    TWIN_REQUIRED = "twin_required"
    TWIN_VETO = "twin_veto"
    TWIN_LOW_CONFIDENCE = "twin_low_confidence"
    TWIN_NOT_EXECUTABLE = "twin_not_executable"
    FORBIDDEN_PARAM = "forbidden_param"
    OUT_OF_BOUNDS = "out_of_bounds"
    RISK_SURFACE = "risk_surface"
    INVALID_PROPOSAL = "invalid_proposal"
    SHADOW_REQUIRED = "shadow_required"


@dataclass(frozen=True, slots=True)
class Phase2WallAdjustmentProposal:
    """Clamped wall-threshold adjustments for existing evaluate_wall_trigger inputs."""

    stall_wall_sec_multiplier: float = 1.0
    stagnation_rollouts_delta: int = 0
    regime: str = "UNKNOWN"
    progress_ratio: float = 0.0
    rationale: str = ""
    risk_touching: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Phase2ParamAdjustmentProposal:
    """Bounded birth recovery parameter patch (never risk/capital keys)."""

    changes: dict[str, float | int] = field(default_factory=dict)
    rationale: str = ""
    risk_touching: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "changes": dict(self.changes),
            "rationale": self.rationale,
            "risk_touching": self.risk_touching,
        }


@dataclass(frozen=True, slots=True)
class Phase2InstanceAdaptProposal:
    """In-process instance adaptation (no OS process spawn)."""

    action: str = ""
    refresh_handler_cfg: bool = False
    spawn_plateau: bool = False
    spawn_phoenix_reset: bool = False
    rationale: str = ""
    risk_touching: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Phase2GateResult:
    allowed: bool
    reason: str
    pillar: str
    message: str = ""
    twin_confidence: float = 0.0
    twin_mode: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "pillar": self.pillar,
            "message": self.message,
            "twin_confidence": self.twin_confidence,
            "twin_mode": self.twin_mode,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class Phase2OrchestratorDecision:
    """Thin orchestrator outcome for one pillar evaluation cycle."""

    pillar: str
    proposal: dict[str, Any] = field(default_factory=dict)
    gate: Phase2GateResult | None = None
    applied: bool = False
    apply_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pillar": self.pillar,
            "proposal": dict(self.proposal),
            "gate": self.gate.to_dict() if self.gate else None,
            "applied": self.applied,
            "apply_payload": dict(self.apply_payload),
        }


__all__ = [
    "Phase2GateReason",
    "Phase2GateResult",
    "Phase2InstanceAdaptProposal",
    "Phase2OrchestratorDecision",
    "Phase2ParamAdjustmentProposal",
    "Phase2Pillar",
    "Phase2WallAdjustmentProposal",
]
