from types import SimpleNamespace
from contextlib import nullcontext
from datetime import datetime
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from lumina_core import runtime_workers
from lumina_core.engine import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.risk.final_arbitration import FinalArbitration
from lumina_core.risk.risk_policy import RiskPolicy
from lumina_core.runtime_context import RuntimeContext


def _patch_supervisor_phase_state_machine(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake_datetime: type | None = None,
) -> None:
    """Post Sub11 remediation: orchestration lives in supervisor_phase_state_machine.

    Wave B3 moved capital gates into supervisor_phase_tick_ops — patch both surfaces.
    """
    from lumina_core.engine import supervisor_phase_state_machine as sp_sm
    from lumina_core.engine import supervisor_phase_tick_ops as tick_ops
    from lumina_core.engine import supervisor_tick_signal as tick_signal

    if fake_datetime is not None:
        monkeypatch.setattr(sp_sm, "datetime", fake_datetime)
        monkeypatch.setattr(tick_ops, "datetime", fake_datetime)

    def _risk(**kwargs: Any) -> tuple[str, bool, str]:
        return (str(kwargs.get("signal", "HOLD")), True, "ok")

    def _gate(**kwargs: Any) -> dict[str, Any]:
        return {
            "signal": str(kwargs.get("signal", "HOLD")),
            "approved": True,
            "reason": "ok",
        }

    for mod in (sp_sm, tick_ops, tick_signal):
        monkeypatch.setattr(mod, "apply_hard_risk_controller_to_signal", _risk)
        monkeypatch.setattr(mod, "apply_agent_policy_gateway", _gate)
