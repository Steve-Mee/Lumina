"""Bounded context: Risk — capital protection, position sizing, session guards.

Re-exports from canonical engine-level modules (ADR-002 migration pending).

Current members:
    HardRiskController  — fail-closed risk enforcement (daily loss cap, VaR, ES)
    RiskAllocatorMixin  — position sizing and regime-aware allocation
    RiskGatesMixin      — pre-trade risk gate checks
    SessionGuard        — trading session time and calendar enforcement
    ConstitutionalChecker — runtime AGI safety principle enforcement (v53)
"""

from __future__ import annotations

from lumina_core.engine.risk_controller import HardRiskController
from lumina_core.engine.risk_gates import RiskGatesMixin
from lumina_core.engine.session_guard import SessionGuard
from lumina_core.engine.constitutional_principles import ConstitutionalChecker

__all__ = [
    "HardRiskController",
    "RiskGatesMixin",
    "SessionGuard",
    "ConstitutionalChecker",
]
