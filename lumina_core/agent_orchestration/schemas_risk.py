"""Typed EventBus / Blackboard payload contracts (risk).

Canonical re-export surface: ``lumina_core.agent_orchestration.schemas``.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lumina_core.risk.schemas import ArbitrationResult

class RiskVerdict(BaseModel):
    """Contract for risk decision and gating payloads."""

    model_config = ConfigDict(extra="forbid")

    approved: bool | None = None
    reason: str | None = None
    limit: str | None = None
    value: float | None = None
    risk_adjustment: float | None = None
    max_risk_percent_multiplier: float | None = Field(default=None, ge=0.0)
    rl_confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class FinalArbitrationResult(ArbitrationResult):
    """Event-bus alias for canonical risk arbitration result contract."""
class ShadowResult(BaseModel):
    """Contract for shadow deployment verdict payloads."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["pass", "fail", "pending"]
    dna_hash: str | None = None
    sample_size: int | None = Field(default=None, ge=0)
    pnl: float | None = None


class RiskConfigMutationProposal(BaseModel):
    """Strict typed contract for risk config mutations (max_risk_percent, drawdown_kill_percent)
    originating from evolution hyperparam_suggestion paths (e.g. ProposalGenerator + meta wrappers).

    First small slice of Phase 3 D2 god decomp/firewall on meta_agent_core (SPF-003 per
    2026-05-31 analysis + MC D2 Red/highest-leverage post D4 scale). extra=forbid + required
    decision_context_id + source/dna/shadow ref enforce typed aperture, auditability, and
    tie to prior shadow (addresses D5 residual _apply_candidate gap at meta:1044-1047).

    Used by central apply fn in evolution_risk_proposal.py; optional bus publish under
    "evolution.risk_config.mutation" (with payload_model for contract).
    """

    model_config = ConfigDict(extra="forbid")

    decision_context_id: str = Field(min_length=1)  # e.g. from nightly/AB or upstream ctx
    source: str = Field(min_length=1)  # e.g. "meta_agent_core._apply_candidate" or "proposal_generator"
    dna_hash: str | None = None
    shadow_result_ref: str | None = None  # experiment_id from prior validate_risk_proposal_in_shadow (D5)
    proposed_values: dict[str, float] = Field(default_factory=dict)  # only the risk keys (max_risk_percent, drawdown_kill_percent)

class GateEntryPayload(BaseModel):
    """Minimal root event marking that an order intent has entered the authoritative admission chain."""

    model_config = ConfigDict(extra="forbid")

    decision_context_id: str
    symbol: str
    proposed_risk: float
    mode: str
    order_side: str | None = None

