"""Supervisor phase tick ops (Wave G split)."""
from __future__ import annotations

from datetime import datetime

from lumina_core.engine.supervisor_tick_ctx import SupervisorTickCtx
from lumina_core.engine.supervisor_tick_preflight import run_tick_preflight
from lumina_core.engine.supervisor_tick_signal import run_tick_signal_gate
from lumina_core.engine.supervisor_tick_exec import run_tick_exec
from lumina_core.engine.supervisor_tick_post import run_tick_post_monitor
from lumina_core.reasoning.agent_contracts import (  # noqa: F401 — re-export for tests/monkeypatch
    apply_agent_policy_gateway,
)
from lumina_core.runtime_trade_gates import (  # noqa: F401 — re-export for tests/monkeypatch
    apply_hard_risk_controller_to_signal,
)

__all__ = [
    "SupervisorTickCtx",
    "run_tick_preflight",
    "run_tick_signal_gate",
    "run_tick_exec",
    "run_tick_post_monitor",
    "datetime",
    "apply_agent_policy_gateway",
    "apply_hard_risk_controller_to_signal",
]
