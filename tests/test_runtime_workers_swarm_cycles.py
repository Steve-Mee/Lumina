"""Isolated swarm-boundary cycle test.

Coverage Report runs without xdist. The previous version in
test_runtime_workers.py counted process-wide time.sleep calls and
flaked (assert 1 == 2) when leftover daemons slept during the suite.
"""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from lumina_core import runtime_workers


def _patch_supervisor_phase_state_machine(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake_datetime: type | None = None,
) -> None:
    from lumina_core.engine import supervisor_phase_state_machine as sp_sm
    from lumina_core.engine import supervisor_phase_tick_ops as tick_ops
    from lumina_core.engine import supervisor_tick_signal as tick_signal

    if fake_datetime is not None:
        monkeypatch.setattr(sp_sm, "datetime", fake_datetime)
        monkeypatch.setattr(tick_ops, "datetime", fake_datetime)

    def _risk(**kwargs: Any) -> tuple[str, bool, str]:
        return (str(kwargs.get("signal", "HOLD")), True, "ok")

    def _gate(**kwargs: Any) -> dict[str, Any]:
        return {"signal": str(kwargs.get("signal", "HOLD")), "approved": True, "reason": "ok"}

    for mod in (sp_sm, tick_ops, tick_signal):
        monkeypatch.setattr(mod, "apply_hard_risk_controller_to_signal", _risk)
        monkeypatch.setattr(mod, "apply_agent_policy_gateway", _gate)


@pytest.mark.unit
def test_supervisor_loop_runs_swarm_once_per_boundary_across_multiple_cycles(monkeypatch):
    class SwarmSpy:
        def __init__(self) -> None:
            self.run_calls = 0
            self.apply_calls = 0

        def run_swarm_cycle(self):
            self.run_calls += 1
            return {"global_regime": "TRENDING", "allocation": {"MES JUN26": 1.0}}

        def apply_to_primary_dream(self):
            self.apply_calls += 1

        def generate_dashboard_plot(self):
            return None

    class FakeDateTime:
        _ticks = [
            datetime(2026, 4, 4, 12, 10, 1),
            datetime(2026, 4, 4, 12, 10, 30),
            datetime(2026, 4, 4, 12, 11, 1),
            datetime(2026, 4, 4, 12, 15, 1),
        ]
        _i = 0

        @classmethod
        def now(cls):
            if cls._i >= len(cls._ticks):
                raise StopIteration()
            value = cls._ticks[cls._i]
            cls._i += 1
            return value

        @staticmethod
        def fromtimestamp(timestamp, tz=None):
            from datetime import datetime as _dt

            return _dt.fromtimestamp(timestamp, tz)

    swarm = SwarmSpy()
    recorded_updates: list[dict[str, Any]] = []

    def _sleep(*_args: Any, **_kwargs: Any) -> None:
        return None

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"close": [5000.0]}),
        fetch_account_balance=lambda: None,
        account_equity=50000.0,
        account_balance=50000.0,
        save_state=lambda: None,
        get_current_dream_snapshot=lambda: {
            "signal": "HOLD",
            "confluence_score": 0.8,
            "regime": "NEUTRAL",
            "stop": 4990.0,
            "target": 5010.0,
        },
        set_current_dream_fields=lambda updates: recorded_updates.append(dict(updates)),
        set_current_dream_value=lambda *_a, **_k: None,
        is_market_open=lambda: False,
        sim_position_qty=0,
        sim_entry_price=0.0,
        open_pnl=0.0,
        realized_pnl_today=0.0,
        calculate_adaptive_risk_and_qty=lambda *_a, **_k: 1,
        place_order=lambda *_a, **_k: False,
        pnl_history=[],
        equity_curve=[50000.0],
        logger=SimpleNamespace(
            info=lambda *_a, **_k: None,
            error=lambda *_a, **_k: None,
            debug=lambda *_a, **_k: None,
        ),
        engine=SimpleNamespace(
            config=SimpleNamespace(
                trade_mode="paper",
                drawdown_kill_percent=8.0,
                status_print_interval_sec=999999.0,
                min_confluence=0.75,
                instrument="MES JUN26",
            ),
            emotional_twin=None,
            infinite_simulator=None,
            rl_env=None,
            ppo_trainer=None,
            swarm=swarm,
        ),
        swarm_manager=swarm,
        np=np,
    )

    monkeypatch.setattr(runtime_workers, "datetime", FakeDateTime)
    _patch_supervisor_phase_state_machine(monkeypatch, fake_datetime=FakeDateTime)
    monkeypatch.setattr(runtime_workers.time, "sleep", _sleep)
    from lumina_core.engine import runtime_workers_facade as _facade

    monkeypatch.setattr(_facade.time, "sleep", _sleep)

    with pytest.raises(StopIteration):
        runtime_workers.supervisor_loop(cast(Any, app))

    assert swarm.run_calls == 2
    assert swarm.apply_calls == 2
    assert len([u for u in recorded_updates if u.get("swarm_regime") == "TRENDING"]) == 2
