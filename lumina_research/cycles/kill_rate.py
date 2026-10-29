"""Re-export kill-rate diagnostics for the research-cycle runner."""

from __future__ import annotations

from lumina_research.diagnostics import (
    KILL_RATE_ALL_DEAD,
    KILL_RATE_EXPECTATION,
    KILL_RATE_STRUCTURAL_LOW,
    KILL_RATE_WEAK,
    diagnose_kill_rate,
)

__all__ = [
    "KILL_RATE_ALL_DEAD",
    "KILL_RATE_EXPECTATION",
    "KILL_RATE_STRUCTURAL_LOW",
    "KILL_RATE_WEAK",
    "diagnose_kill_rate",
]
