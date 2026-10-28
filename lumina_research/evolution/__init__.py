"""Phase 3 bounded self-evolution. Propose-only. Never writes live Risk Core or PromotionGate."""

from __future__ import annotations

from lumina_research.evolution.birth import BirthPhase, BirthRefused
from lumina_research.evolution.governance import GovernanceGate, ReviewAuthority
from lumina_research.evolution.loop import EvolutionRuntime, run_multiseed_evolution, run_phase3_evolution
from lumina_research.evolution.reflector import ReflectorAgent, ReflectorRefused
from lumina_research.evolution.regime import RegimePolicy, RegimePolicyError

__all__ = [
    "BirthPhase",
    "BirthRefused",
    "EvolutionRuntime",
    "GovernanceGate",
    "ReflectorAgent",
    "ReflectorRefused",
    "RegimePolicy",
    "RegimePolicyError",
    "ReviewAuthority",
    "run_multiseed_evolution",
    "run_phase3_evolution",
]
