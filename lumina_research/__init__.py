"""Propose-only research layer. Never mutates Risk Core, Fabric, or live DNA."""

from __future__ import annotations

CHARTER_RELATIVE = "RESEARCH_CHARTER.md"
PROPOSE_ONLY = True
VALIDATION_GATE = "lumina_research.validation.gate.passes_validation_gate"

__all__ = ["CHARTER_RELATIVE", "PROPOSE_ONLY", "VALIDATION_GATE"]
