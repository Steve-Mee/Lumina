"""PlateauHandler — single responsibility owner of plateau detection and escalation.

All plateau logic (enter, evolution ladder, best snapshot, quarantine, terminal)
lives here or is delegated to plateau_escalator.py.

In the event-driven world the handler subscribes to rollout metrics and
publishes "birth.plateau.entered" and evolution step facts. The orchestrator
only observes.
"""

from __future__ import annotations

import logging

from lumina_core.birth.plateau_escalator import (
    PlateauState,
    should_enter_plateau,
    enter_plateau,
    should_trigger_plateau_evolution_step,
    # ... other focused functions remain the source of truth
)

logger = logging.getLogger("lumina.birth.plateau_handler")

# Future: subscribe to rollout events or stage metrics and emit:
#   bus.publish("birth.plateau.entered", ...)
#   bus.publish("birth.plateau.evolution.step", ...)

__all__ = ["PlateauState", "should_enter_plateau", "enter_plateau", "should_trigger_plateau_evolution_step"]
