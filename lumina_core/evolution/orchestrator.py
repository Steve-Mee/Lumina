"""Backward-compatible export for the split evolution orchestrator core."""

from __future__ import annotations

from .orchestrator_core import EvolutionOrchestrator, GenerationResult

__all__ = ["EvolutionOrchestrator", "GenerationResult"]
