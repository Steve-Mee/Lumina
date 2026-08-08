from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any


logger = logging.getLogger(__name__)


_CONTRACT_MONTHS = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}
_MONTH_NAMES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


@dataclass(slots=True)
class AdaptiveRegimePolicy:
    fast_path_weight: float
    agent_route: tuple[str, ...]
    risk_multiplier: float
    emotional_twin_sensitivity: float
    cooldown_minutes: int
    high_risk: bool
    nightly_evolution_focus: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["agent_route"] = list(self.agent_route)
        return payload


@dataclass(slots=True)
class RegimeSnapshot:
    label: str
    confidence: float
    risk_state: str
    evidence: list[str] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)
    adaptive_policy: AdaptiveRegimePolicy = field(
        default_factory=lambda: AdaptiveRegimePolicy(
            fast_path_weight=0.5,
            agent_route=("risk", "scalper", "swing"),
            risk_multiplier=1.0,
            emotional_twin_sensitivity=1.0,
            cooldown_minutes=30,
            high_risk=False,
            nightly_evolution_focus="balanced",
        )
    )
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": round(float(self.confidence), 4),
            "risk_state": self.risk_state,
            "evidence": list(self.evidence),
            "features": {k: round(float(v), 6) for k, v in self.features.items()},
            "adaptive_policy": self.adaptive_policy.to_dict(),
            "timestamp": self.timestamp,
        }



__all__ = ['AdaptiveRegimePolicy', 'RegimeSnapshot']
