"""Organism autonomy value types (M5 extract)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from lumina_core.birth.death_spiral_guard import DeathSpiralState
from lumina_core.birth.phoenix_loop import PhoenixLoopState


class RecoveryDispatch(str, Enum):
    CONTINUE_LOOP = "continue_loop"
    PHOENIX_RESUME = "phoenix_resume"
    PROVISIONAL_GRADUATE = "provisional_graduate"
    TERMINAL_NOTIFY_ONLY = "terminal_notify_only"
    # Birth/SIM only: clear champion freeze by keeping best policy (never wipe).
    ACCEPT_CHAMPION_RESUME = "accept_champion_resume"


@dataclass(slots=True)
class AutonomyDecision:
    dispatch: RecoveryDispatch
    needs_attention: bool = False
    retryable: bool = True
    stall_reason: str = ""
    recommended_action: str = ""
    checkpoint_patch: dict[str, Any] | None = None
    autonomy_metrics: dict[str, Any] | None = None
    message: str = ""


@dataclass(slots=True)
class OrganismAutonomyState:
    phoenix: PhoenixLoopState
    death_spiral: DeathSpiralState
    last_recommended_action: str = ""
    autonomous_recovery_count: int = 0

    def to_metrics(self) -> dict[str, Any]:
        return {
            **self.phoenix.to_metrics(),
            **self.death_spiral.to_metrics(),
            "autonomous_recovery_count": int(self.autonomous_recovery_count),
            "last_recommended_action": str(self.last_recommended_action),
        }

    @classmethod
    def from_metrics(cls, metrics: dict[str, Any] | None) -> OrganismAutonomyState:
        if not isinstance(metrics, dict):
            return cls(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
        return cls(
            phoenix=PhoenixLoopState.from_metrics(metrics),
            death_spiral=DeathSpiralState.from_metrics(metrics),
            last_recommended_action=str(metrics.get("last_recommended_action", "") or ""),
            autonomous_recovery_count=int(metrics.get("autonomous_recovery_count", 0) or 0),
        )
