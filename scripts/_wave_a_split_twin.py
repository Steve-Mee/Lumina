"""Wave A PR5 — split approval_twin_agent into mixin modules + thin host."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVO = ROOT / "lumina_core" / "evolution"
SRC = EVO / "approval_twin_agent.py"


def extract(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

    backends = '''"""Approval Twin scoring backends (local heuristic + Ollama)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

from lumina_core.evolution.dna_registry import PolicyDNA


class ApprovalTwinBackend(Protocol):
    def score(self, *, dna: PolicyDNA, local_score: float, threshold: float) -> tuple[float | None, str]: ...


'''
    backends += extract(lines, 73, 119)
    (EVO / "approval_twin_backends.py").write_text(backends.rstrip() + "\n", encoding="utf-8")

    scoring = '''"""Approval Twin scoring / feature / calibration helpers."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.steve_values_registry import SteveValueRecord
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinScoringMixin:
'''
    scoring += extract(lines, 1278, 1420)
    (EVO / "approval_twin_scoring.py").write_text(scoring.rstrip() + "\n", encoding="utf-8")

    bus = '''"""Approval Twin EventBus bind / observe / publish helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import (
    TwinDecisionEvent,
    TwinModePromotionEvent,
    TwinShadowObservationEvent,
    TwinTrainingUpdateEvent,
)
from lumina_core.logging_utils import (
    get_logger,
    record_shadow_twin_alignment_monitoring,
    record_twin_steve_accuracy_monitoring,
)
from lumina_core.evolution.twin_mode_promotion_gate import apply_mode_authority

logger = get_logger("lumina.evolution.twin")

# Topics Twin subscribes to for non-blocking shadow observation (ADR-0001 / 0031 finish).
_TWIN_SUBSCRIBE_TOPICS: tuple[str, ...] = (
    "evolution.shadow.verdict",
    "evolution.promotion.decision",
    "evolution.proposal.created",
    "safety.constitution.audit",
    "safety.constitution.violation",
    "risk.policy.decision",
)


class ApprovalTwinBusMixin:
'''
    bus += extract(lines, 285, 705)
    (EVO / "approval_twin_bus.py").write_text(bus.rstrip() + "\n", encoding="utf-8")

    evaluators = '''"""Approval Twin DNA / code / shadow evaluation helpers."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.approval_twin_backends import (
    ApprovalTwinBackend,
    LocalHeuristicBackend,
    OllamaTwinBackend,
)
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.logging_utils import (
    classify_twin_decision_outcome,
    correlation_id,
    get_logger,
    log_twin_decision,
    record_shadow_twin_alignment_monitoring,
    record_twin_decision_monitoring,
)

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinEvaluatorsMixin:
'''
    evaluators += extract(lines, 735, 1152)
    (EVO / "approval_twin_evaluators.py").write_text(evaluators.rstrip() + "\n", encoding="utf-8")

    training = '''"""Approval Twin RLHF / fine-tune / Steve agreement helpers."""
from __future__ import annotations

from typing import Any

from lumina_core.evolution.steve_values_registry import SteveValueRecord
from lumina_core.logging_utils import (
    get_logger,
    record_twin_steve_accuracy_monitoring,
    record_twin_training_metrics_monitoring,
)

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinTrainingMixin:
'''
    training += extract(lines, 707, 733)
    training += "\n"
    training += extract(lines, 1154, 1276)
    (EVO / "approval_twin_training.py").write_text(training.rstrip() + "\n", encoding="utf-8")

    facade = '''"""Approval Twin agent — thin host + re-exports (Wave A PR5).

Bounded modules:
``approval_twin_backends``, ``approval_twin_bus``, ``approval_twin_scoring``,
``approval_twin_evaluators``, ``approval_twin_training``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.approval_twin_backends import (  # noqa: F401
    ApprovalTwinBackend,
    LocalHeuristicBackend,
    OllamaTwinBackend,
)
from lumina_core.evolution.approval_twin_bus import ApprovalTwinBusMixin
from lumina_core.evolution.approval_twin_evaluators import ApprovalTwinEvaluatorsMixin
from lumina_core.evolution.approval_twin_scoring import ApprovalTwinScoringMixin
from lumina_core.evolution.approval_twin_training import ApprovalTwinTrainingMixin
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.steve_values_registry import SteveValueRecord, SteveValuesRegistry
from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
from lumina_core.evolution.twin_mode_promotion_gate import (
    TwinModeController,
    apply_mode_authority,
    canonicalize_twin_mode,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.evolution.twin")

# Canonical: shadow | assisted | full_auto (legacy advisory→assisted, active→full_auto)
_VALID_TWIN_MODES = frozenset({"shadow", "assisted", "full_auto", "advisory", "active"})


@dataclass(slots=True)
class ApprovalTwinState:
    intercept: float
    weights: dict[str, float]
    threshold: float
    training_steps: int
    # last_avg_error used for simple confidence calibration
    last_avg_error: float = 0.15


class ApprovalTwinAgent(
    ApprovalTwinBusMixin,
    ApprovalTwinEvaluatorsMixin,
    ApprovalTwinTrainingMixin,
    ApprovalTwinScoringMixin,
):
    """Small local approval model trained only on Steve's answers.

    This is the core of LUMINA's Approval Twin: a user-trained mimic that
    replaces human approval gates so the organism can evolve 24/7.
    """

'''
    facade += extract(lines, 146, 283)
    facade += "\n"
    facade += extract(lines, 1422, 1448)
    facade += '''

__all__ = [
    "ApprovalTwinAgent",
    "ApprovalTwinBackend",
    "ApprovalTwinState",
    "LocalHeuristicBackend",
    "OllamaTwinBackend",
]
'''
    SRC.write_text(facade.rstrip() + "\n", encoding="utf-8")
    print("twin split done")
    for name in (
        "approval_twin_agent.py",
        "approval_twin_backends.py",
        "approval_twin_bus.py",
        "approval_twin_scoring.py",
        "approval_twin_evaluators.py",
        "approval_twin_training.py",
    ):
        n = len((EVO / name).read_text(encoding="utf-8").splitlines())
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()
