"""C1: monitoring observability soft-fails — never FATAL supervisor loop."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from lumina_core.engine.runtime_monitoring_service import RuntimeMonitoringService
from lumina_core.engine.supervisor_phase_state_machine import SupervisorPhaseStateMachine
from lumina_core.engine.supervisor_tick_ctx import SupervisorTickCtx
from lumina_core.engine.supervisor_tick_post import run_tick_post_monitor


@pytest.mark.unit
def test_publish_snapshot_soft_fails_when_writer_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given write_runtime_monitoring_snapshot raises, when publish_snapshot, then no exception."""

    def boom(_payload: dict[str, Any]) -> None:
        raise RuntimeError("injected snapshot failure")

    monkeypatch.setattr(
        "lumina_core.engine.runtime_monitoring_service.write_runtime_monitoring_snapshot",
        boom,
    )
    rc_state = SimpleNamespace(mc_drawdown_worst_pct=1.0)
    risk_controller = SimpleNamespace(consecutive_losses=0, state=rc_state)
    engine = SimpleNamespace(
        risk_controller=risk_controller,
        live_position_qty=0,
        config=SimpleNamespace(trade_mode="paper", drawdown_kill_percent=8.0),
    )
    app = SimpleNamespace(
        np=np,
        engine=engine,
        pnl_history=[1.0],
        equity_curve=[100.0],
        account_balance=1000.0,
        account_equity=1000.0,
        realized_pnl_today=0.0,
        open_pnl=0.0,
        pending_trade_reconciliations=[],
        trade_log=[],
    )
    # when / then — must not raise
    RuntimeMonitoringService(app=app).publish_snapshot()


@pytest.mark.unit
def test_write_snapshot_soft_fails_on_io_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Given state path write fails, when write_runtime_monitoring_snapshot, then soft-fail."""
    from lumina_core import logging_monitoring

    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(tmp_path))

    def boom(*_a: Any, **_k: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(logging_monitoring, "_write_json", boom)
    # when / then
    logging_monitoring.write_runtime_monitoring_snapshot({"mode": "paper", "daily_pnl": 1.0})


@pytest.mark.unit
def test_post_monitor_survives_publish_raise_and_broken_logger() -> None:
    """Given publish raises and sm._logger lacks warning, when run_tick_post_monitor, then no crash."""

    def boom_publish(_app: Any) -> None:
        raise NameError("time")  # historical crash shape from 2026-08-08 audit

    sm = SimpleNamespace(
        app=SimpleNamespace(
            account_equity=1000.0,
            open_pnl=0.0,
            realized_pnl_today=0.0,
            pnl_history=[],
            save_state=lambda: None,
        ),
        engine=SimpleNamespace(infinite_simulator=None),
        _swarm_last_dashboard=0.0,
        _last_status_print=1e18,  # skip status
        _last_infinite_sim_status=1e18,
        _last_oracle=1e18,
        _last_save=1e18,
        _last_monitoring_snapshot=0.0,  # force monitoring path
        _logger=SimpleNamespace(),  # no warning/info/error — historical AttributeError
    )
    ctx = SupervisorTickCtx(
        price=100.0,
        dream_snapshot={},
        now=datetime.now(),
        trade_mode="paper",
        rl_action=None,
        cfg=SimpleNamespace(status_print_interval_sec=99999),
        swarm_manager=None,
        compute_session_kpis=None,
        publish_runtime_monitoring_snapshot=boom_publish,
    )
    # when / then — AttributeError on logger.warning must not escape
    run_tick_post_monitor(sm, ctx)
    assert sm._last_monitoring_snapshot > 0.0


@pytest.mark.unit
def test_phase_state_machine_rejects_simple_namespace_logger() -> None:
    """Given app.logger is SimpleNamespace without levels, when SM init, then module logger used."""
    app = SimpleNamespace(logger=SimpleNamespace(name="fake"), engine=SimpleNamespace(last_validation=None))
    sm = SupervisorPhaseStateMachine(app=app)
    assert callable(getattr(sm._logger, "warning", None))
    assert callable(getattr(sm._logger, "error", None))
    sm._logger.warning("probe-ok")
