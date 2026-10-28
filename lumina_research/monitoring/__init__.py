"""Phase 4 continuity: live monitoring, decay staging, capacity, guardian, replenishment."""

from __future__ import annotations

from lumina_research.monitoring.cli import main
from lumina_research.monitoring.config import ContinuityConfig, load_default_config
from lumina_research.monitoring.loop import ContinuityRuntime, run_phase4_detection
from lumina_research.monitoring.types import ContinuityRefused

__all__ = [
    "ContinuityConfig",
    "ContinuityRefused",
    "ContinuityRuntime",
    "load_default_config",
    "main",
    "run_phase4_detection",
]
