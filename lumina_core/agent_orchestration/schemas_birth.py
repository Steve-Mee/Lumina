"""Typed EventBus / Blackboard payload contracts (birth).

Canonical re-export surface: ``lumina_core.agent_orchestration.schemas``.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

class BirthCurriculumStarted(BaseModel):
    """Payload when a birth curriculum run begins."""

    model_config = ConfigDict(extra="forbid")

    curriculum_id: str = Field(min_length=1)
    stages: list[str]
    target_trades_cap: int = Field(ge=0)
    practice_mode: bool = False
    timestamp: str | None = None


class BirthCurriculumStageRequested(BaseModel):
    """Command-like fact: orchestrator requests a stage to begin execution."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    stage_index: int = Field(ge=0)
    target: int = Field(ge=0)
    stage_progress_pct: float = 0.0
    training_mode: str
    prefer_real: bool


class BirthCurriculumStageStarted(BaseModel):
    """Stage execution has begun (handler confirmed)."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    stage_index: int
    required_trades: int
    timestamp: str | None = None


class BirthCurriculumStageCompleted(BaseModel):
    """Stage finished. Pass/fail + receipt details. Strict for gate integrity."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    passed: bool
    trades: int = Field(ge=0)
    wins: int = Field(ge=0)
    hold_ratio: float
    provisional: bool = False
    message: str = ""
    receipt: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class BirthCurriculumStageAborted(BaseModel):
    """Terminal abort of curriculum or stage (fail-closed)."""

    model_config = ConfigDict(extra="forbid")

    stage: str | None = None
    reason: str  # e.g. "constitution_violation", "terminal_stall", "evolution_exhausted"
    detail: dict[str, Any] = Field(default_factory=dict)
    violations: int = 0


class BirthPlateauEntered(BaseModel):
    """Plateau escalation signal."""

    model_config = ConfigDict(extra="allow")

    stage: str
    winrate: float
    trades_at_detection: int
    evolution_step: int = 0


class BirthPhoenixCycle(BaseModel):
    """Phoenix loop cycle marker."""

    model_config = ConfigDict(extra="allow")

    cycle: int
    reason: str
    action: str | None = None
    preserve_cache: bool = True
    checkpoint_patch: dict[str, Any] | None = None


class BirthStageRolloutSnapshot(BaseModel):
    """Rollout tick signal consumed by birth SRP handlers."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = Field(min_length=1)
    signal: str = Field(min_length=1)
    stage: str
    context: dict[str, Any] = Field(default_factory=dict)


class BirthMetaPlan(BaseModel):
    """Meta-controller decision plan for a correlated rollout signal."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = Field(min_length=1)
    trigger: str = ""
    plan: dict[str, Any] = Field(default_factory=dict)


class BirthPlateauEvolutionStep(BaseModel):
    """Plateau evolution ladder step applied or requested."""

    model_config = ConfigDict(extra="allow")

    correlation_id: str = ""
    stage: str
    evolution_step: int = Field(ge=0)
    action: str
    detail: str = ""
    entered: bool = False


class BirthPlateauTrapDetected(BaseModel):
    """Over-trading trap fact for meta-controller consumption."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str
    detected: bool
    range_flat_ratio: float = 0.0
    range_round_trips: int = 0


class BirthStallRemediationCycle(BaseModel):
    """Stall remediation cycle started."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    cycle: int = Field(ge=1)
    max_cycles: int = Field(ge=1)
    winrate_at_start: float = 0.0


class BirthStallRemediationStep(BaseModel):
    """Stall remediation step advanced."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    cycle: int = Field(ge=1)
    step: int = Field(ge=1)
    max_steps: int = Field(ge=1)
    action: str | None = None
    detail: str = ""


class BirthAutonomyDecision(BaseModel):
    """Organism autonomy recovery dispatch."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    dispatch: str
    needs_attention: bool = False
    retryable: bool = True
    stall_reason: str = ""
    recommended_action: str = ""
    checkpoint_patch: dict[str, Any] | None = None
    autonomy_metrics: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


class BirthCertificateRemediationRequested(BaseModel):
    """Certificate fast-path remediation gate signal."""

    model_config = ConfigDict(extra="forbid")

    progress_snapshot: dict[str, Any] = Field(default_factory=dict)
    checkpoint_state: dict[str, Any] = Field(default_factory=dict)
    fast_path_eligible: bool = False


class BirthWallTriggered(BaseModel):
    """Wall or stall trigger detected during certified birth research."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str
    trigger_type: str
    failure_key: str
    elapsed_stage_sec: float = 0.0
    constitution_violations: int = 0
    context: dict[str, Any] = Field(default_factory=dict)


class BirthAdaptationApplied(BaseModel):
    """Autonomous adaptation recovery applied after a wall trigger."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str
    reason: str
    adaptation_tier: int = 0
    retries_this_stage: int = 0
    chunk_target: int = 0
    escalation_level: int = 0
    parameter_patch: dict[str, Any] = Field(default_factory=dict)
    dispatch: str = "continue_loop"
    autonomous: bool = True
    recovery_kind: str = ""


class BirthAutonomyRecoveryMetrics(BaseModel):
    """Rolling autonomous recovery success metrics for birth stage."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str
    wall_triggers_total: int = 0
    recovery_attempts: int = 0
    recovery_successes: int = 0
    autonomous_recovery_rate_pct: float = 0.0


class BirthPhase2WallProposal(BaseModel):
    """Phase 2 dynamic wall threshold proposal (ADR-0034)."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str = ""
    proposal: dict[str, Any] = Field(default_factory=dict)


class BirthPhase2ParamProposal(BaseModel):
    """Phase 2 self-adaptive birth param proposal (ADR-0034)."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str = ""
    proposal: dict[str, Any] = Field(default_factory=dict)


class BirthPhase2InstanceProposal(BaseModel):
    """Phase 2 in-process instance adapt proposal (ADR-0034)."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str = ""
    proposal: dict[str, Any] = Field(default_factory=dict)


class BirthPhase2GateResult(BaseModel):
    """Phase 2 multi-gate evaluation result (ADR-0034)."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str = ""
    allowed: bool = False
    reason: str = ""
    pillar: str = ""
    message: str = ""
    twin_confidence: float = 0.0
    twin_mode: str = ""
    details: dict[str, Any] = Field(default_factory=dict)

