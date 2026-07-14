"""stage_training_loop - thin compatibility shim after decomposition.

ALL monolithic procedural orchestration has been DELETED from this file.

Orchestration now happens via event emissions on the central Event Bus.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import (
    BirthCurriculumStageAborted,
    BirthCurriculumStageCompleted,
    BirthCurriculumStageRequested,
)

# Support monkeypatch strings that expect these names on the module.
sys.modules[__name__ + ".time"] = time

from .stage_rollout_executor import run_stage_research_loop as _execute  # noqa: E402

# Re-export symbols that tests commonly monkeypatch on the old module path.
from lumina_core.birth.data_expansion import expand_birth_data  # noqa: E402
from lumina_core.birth.pattern_miner import mine_winning_patterns  # noqa: E402
from lumina_core.birth.sim_runner import run_policy_rollout  # noqa: E402

__all__ = ["run_stage_research_loop", "run_policy_rollout", "mine_winning_patterns", "expand_birth_data"]


def run_stage_research_loop(host: Any, **kwargs: Any) -> dict[str, Any] | None:
    """Thin entrypoint.

    Emits a stage request event to the central bus.
    Dedicated handlers perform the work.
    """
    bus: EventBus | None = getattr(host, "event_bus", None)
    stage = kwargs.get("stage")
    stage_index = kwargs.get("stage_index", 0)
    target = kwargs.get("target", 0)
    stage_progress_pct = kwargs.get("stage_progress_pct", 0.0)
    training_mode = kwargs.get("training_mode", "certified")
    prefer_real = kwargs.get("prefer_real", True)

    if bus is not None and stage is not None:
        try:
            req = BirthCurriculumStageRequested(
                stage=str(getattr(stage, "value", stage)),
                stage_index=int(stage_index),
                target=int(target or 0),
                stage_progress_pct=float(stage_progress_pct or 0.0),
                training_mode=str(training_mode),
                prefer_real=bool(prefer_real),
            )
            bus.publish_validated(
                topic="birth.curriculum.stage.requested",
                producer="stage_training_loop",
                payload=req.model_dump(mode="json"),
            )
        except Exception:
            pass

    # Propagate monkeypatches from this compat module into stage_loop_rollout
    # (where the loop body lives after the stage_rollout_executor split).
    try:
        import lumina_core.birth.stage_loop_rollout as _handler_mod
        import lumina_core.birth.stage_rollout_executor as _facade_mod

        _compat_mod = sys.modules[__name__]
        for _name in ("run_policy_rollout", "mine_winning_patterns", "expand_birth_data"):
            if hasattr(_compat_mod, _name):
                _fake = getattr(_compat_mod, _name)
                setattr(_handler_mod, _name, _fake)
                setattr(_facade_mod, _name, _fake)
        if hasattr(_compat_mod, "time"):
            _handler_mod.time = _compat_mod.time
            _facade_mod.time = _compat_mod.time
    except Exception:
        pass

    result = _execute(host, **kwargs)

    if bus is not None and stage is not None:
        try:
            if result is None:
                completed = BirthCurriculumStageCompleted(
                    stage=str(getattr(stage, "value", stage)),
                    passed=True,
                    trades=int(getattr(host, "cumulative_trades", 0)),
                    wins=0,
                    hold_ratio=0.0,
                    message="passed",
                )
                bus.publish_validated(
                    topic="birth.curriculum.stage.completed",
                    producer="stage_training_loop",
                    payload=completed.model_dump(mode="json"),
                )
            else:
                abort = BirthCurriculumStageAborted(
                    stage=str(getattr(stage, "value", stage)),
                    reason=str(
                        result.get("status", result.get("terminal_stall_reason", "stage_result"))
                        if isinstance(result, dict)
                        else "error"
                    ),
                    detail={"result": str(result)[:200] if result else ""},
                )
                bus.publish_validated(
                    topic="birth.curriculum.aborted",
                    producer="stage_training_loop",
                    payload=abort.model_dump(mode="json"),
                )
        except Exception:
            pass

    return result
