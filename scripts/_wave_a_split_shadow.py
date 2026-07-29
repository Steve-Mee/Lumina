"""Wave A PR6 — split shadow.py into types/registry/mixins + thin façade."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RISK = ROOT / "lumina_core" / "risk"
SRC = RISK / "shadow.py"


def extract(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

    types = '''"""Shadow risk evaluation typed data contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision, ShadowResult


'''
    types += extract(lines, 40, 67)
    (RISK / "shadow_types.py").write_text(types.rstrip() + "\n", encoding="utf-8")

    registry = '''"""Shadow experiment run registry (in-memory + optional JSONL)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lumina_core.logging_utils import get_logger
from lumina_core.risk.shadow_types import ShadowExperimentResult

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision

logger = get_logger("lumina.risk.shadow")


'''
    registry += extract(lines, 70, 188)
    (RISK / "shadow_registry.py").write_text(registry.rstrip() + "\n", encoding="utf-8")

    isolation = '''"""Shadow isolation / isolated orchestrator helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.risk.orchestration import RiskOrchestrator
from lumina_core.risk.shadow_registry import ShadowRunRegistry

logger = get_logger("lumina.risk.shadow")


class ShadowIsolationMixin:
'''

    # methods: with_persistent_registry (264-289), _get_isolated (291-311), _enforce (313-324)
    # Also __init__ parts stay on host. Extract these three method blocks.
    isolation += extract(lines, 264, 324)
    (RISK / "shadow_isolation.py").write_text(isolation.rstrip() + "\n", encoding="utf-8")

    assessment = '''"""Shadow risk assessment + decision-trace comparison."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from lumina_core.logging_utils import get_logger
from lumina_core.risk.shadow_types import ShadowContext

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import ShadowResult

logger = get_logger("lumina.risk.shadow")


class ShadowAssessmentMixin:
'''

    # _publish_event 238-262, evaluate 326-377, _publish_shadow_result 379-408,
    # run_isolated 410-514, compare 516-579
    assessment += extract(lines, 238, 262)
    assessment += "\n"
    assessment += extract(lines, 326, 579)
    (RISK / "shadow_assessment.py").write_text(assessment.rstrip() + "\n", encoding="utf-8")

    experiment = '''"""Shadow experiment run / execute helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lumina_core.logging_utils import get_logger
from lumina_core.risk.shadow_registry import ShadowRunRegistry
from lumina_core.risk.shadow_types import ShadowContext, ShadowExperimentResult

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision, ShadowResult

logger = get_logger("lumina.risk.shadow")


class ShadowExperimentMixin:
'''

    experiment += extract(lines, 739, 989)
    (RISK / "shadow_experiment.py").write_text(experiment.rstrip() + "\n", encoding="utf-8")

    human = '''"""Shadow human-approval + experiment history helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lumina_core.logging_utils import get_logger
from lumina_core.risk.shadow_registry import ShadowRunRegistry
from lumina_core.risk.shadow_types import ShadowContext

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision

logger = get_logger("lumina.risk.shadow")


class ShadowHumanApprovalMixin:
'''

    # recommend 581-623, create 625-698, prepare 700-737, list+history+submit 991-end
    human += extract(lines, 581, 737)
    human += "\n"
    human += extract(lines, 991, 1244)
    (RISK / "shadow_human_approval.py").write_text(human.rstrip() + "\n", encoding="utf-8")

    # façade
    facade = '''"""
Shadow Aperture Evaluator for Risk Logic Experiments.

Bounded modules: ``shadow_types``, ``shadow_registry``, ``shadow_isolation``,
``shadow_assessment``, ``shadow_experiment``, ``shadow_human_approval``.

This module remains the public façade (``ShadowRiskEvaluator`` + re-exports).
NO verdict logic changes in Wave A.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from lumina_core.logging_utils import get_logger
from lumina_core.risk.orchestration import RiskOrchestrator
from lumina_core.risk.shadow_assessment import ShadowAssessmentMixin
from lumina_core.risk.shadow_experiment import ShadowExperimentMixin
from lumina_core.risk.shadow_human_approval import ShadowHumanApprovalMixin
from lumina_core.risk.shadow_isolation import ShadowIsolationMixin
from lumina_core.risk.shadow_registry import ShadowRunRegistry  # noqa: F401
from lumina_core.risk.shadow_types import ShadowContext, ShadowExperimentResult  # noqa: F401

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision, ShadowResult

logger = get_logger("lumina.risk.shadow")


class ShadowRiskEvaluator(
    ShadowIsolationMixin,
    ShadowAssessmentMixin,
    ShadowExperimentMixin,
    ShadowHumanApprovalMixin,
):
    """
    Evaluates risk decisions in a fully isolated shadow aperture.

    Guarantees:
    - Never touches live broker or mutates production state.
    - Uses a dedicated RiskOrchestrator instance (no shared mutable state).
    - All decision_context_ids are forced to start with "shadow-".
    - Emits ShadowResult events for downstream observation.
    """

'''
    # __init__ only from original (213-236)
    facade += extract(lines, 213, 236)
    facade += '''

__all__ = [
    "ShadowContext",
    "ShadowExperimentResult",
    "ShadowRiskEvaluator",
    "ShadowRunRegistry",
]
'''
    SRC.write_text(facade.rstrip() + "\n", encoding="utf-8")
    print("shadow split done")
    for name in (
        "shadow.py",
        "shadow_types.py",
        "shadow_registry.py",
        "shadow_isolation.py",
        "shadow_assessment.py",
        "shadow_experiment.py",
        "shadow_human_approval.py",
    ):
        n = len((RISK / name).read_text(encoding="utf-8").splitlines())
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()
