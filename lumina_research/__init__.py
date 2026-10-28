"""Propose-only research layer. Never mutates Risk Core, Fabric, or live DNA."""

from __future__ import annotations

CHARTER_RELATIVE = "RESEARCH_CHARTER.md"
PROPOSE_ONLY = True
VALIDATION_GATE = "lumina_research.validation.gate.passes_validation_gate"
PROPOSE_PATH = "lumina_research.propose.propose_research_order"

__all__ = ["CHARTER_RELATIVE", "PROPOSE_ONLY", "PROPOSE_PATH", "VALIDATION_GATE"]
