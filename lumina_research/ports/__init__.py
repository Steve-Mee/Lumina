"""Research-side Execution Fabric ports. Interfaces only. No NT8 coupling, no orders."""

from __future__ import annotations

from lumina_research.ports.fail_closed import FailClosedDecision, decide_failure
from lumina_research.ports.fills import FillSink, PortRefused
from lumina_research.ports.shadow import ShadowBook
from lumina_research.ports.sim_safety import SimSafetyConfig, SimSafetyGate, SimSafetyRefused

__all__ = [
    "FailClosedDecision",
    "FillSink",
    "PortRefused",
    "ShadowBook",
    "SimSafetyConfig",
    "SimSafetyGate",
    "SimSafetyRefused",
    "decide_failure",
]
