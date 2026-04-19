from types import SimpleNamespace
from typing import Any, cast

import lumina_core.runtime_bootstrap as runtime_bootstrap
from lumina_core.runtime_bootstrap import start_runtime_services


def test_start_runtime_services_skips_swarm_when_disabled(monkeypatch):
    created = []

    class SwarmStub:
        def __init__(self, engine):
            created.append(engine)

    monkeypatch.setattr(runtime_bootstrap, "SwarmManager", SwarmStub)

    class App:
        def __init__(self):
            self.engine = SimpleNamespace(config=SimpleNamespace(swarm_enabled=False), swarm=None)

        def supervisor_loop(self):
            return None

    app = App()

    def _start_daemon(_fn, name=None):
        return name

    def _fn(name):
        def _inner():
            return None

        _inner.__name__ = name
        return _inner

    start_runtime_services(
        start_daemon_fn=_start_daemon,
        screen_share_enabled=False,
        dashboard_enabled=False,
        voice_input_enabled=False,
        start_screen_share_window_fn=_fn("screen"),
        thought_logger_thread_fn=_fn("thought_logger_thread"),
        start_websocket_fn=_fn("start_websocket"),
        start_trade_reconciler_fn=_fn("start_trade_reconciler"),
        auto_backtester_daemon_fn=_fn("auto_backtester_daemon"),
        start_dashboard_fn=_fn("start_dashboard"),
        voice_listener_thread_fn=_fn("voice_listener_thread"),
        supervisor_loop_fn=app.supervisor_loop,
        dna_rewrite_daemon_fn=_fn("dna_rewrite_daemon"),
        gap_recovery_daemon_fn=_fn("gap_recovery_daemon"),
        pre_dream_daemon_fn=_fn("pre_dream_daemon"),
        auto_journal_daemon_fn=_fn("auto_journal_daemon"),
        auto_backtest_daemon_fn=_fn("auto_backtest_daemon"),
    )

    assert created == []
    assert app.engine.swarm is None


def test_start_runtime_services_orchestration():
    started = []
    flags = {"screen": False}

    def _start_daemon(fn, name=None):
        started.append((fn.__name__, name))

    def _screen():
        flags["screen"] = True

    def _fn(name):
        def _inner():
            return None

        _inner.__name__ = name
        return _inner

    start_runtime_services(
        start_daemon_fn=_start_daemon,
        screen_share_enabled=True,
        dashboard_enabled=True,
        voice_input_enabled=False,
        start_screen_share_window_fn=_screen,
        thought_logger_thread_fn=_fn("thought_logger_thread"),
        start_websocket_fn=_fn("start_websocket"),
        start_trade_reconciler_fn=_fn("start_trade_reconciler"),
        auto_backtester_daemon_fn=_fn("auto_backtester_daemon"),
        start_dashboard_fn=_fn("start_dashboard"),
        voice_listener_thread_fn=_fn("voice_listener_thread"),
        supervisor_loop_fn=_fn("supervisor_loop"),
        dna_rewrite_daemon_fn=_fn("dna_rewrite_daemon"),
        gap_recovery_daemon_fn=_fn("gap_recovery_daemon"),
        pre_dream_daemon_fn=_fn("pre_dream_daemon"),
        auto_journal_daemon_fn=_fn("auto_journal_daemon"),
        auto_backtest_daemon_fn=_fn("auto_backtest_daemon"),
    )

    assert flags["screen"] is True
    names = [n for _, n in started]
    assert "dashboard" in names
    assert "voice-listener" not in names
    assert "supervisor-loop" in names
    assert len(started) == 11


def test_start_runtime_services_initializes_swarm_from_bound_supervisor(monkeypatch):
    created = []

    class SwarmStub:
        def __init__(self, engine):
            self.engine = engine
            created.append(engine)

    monkeypatch.setattr(runtime_bootstrap, "SwarmManager", SwarmStub)

    class App:
        def __init__(self):
            self.engine = SimpleNamespace(config=SimpleNamespace(swarm_enabled=True), swarm=None)

        def supervisor_loop(self):
            return None

    app = App()
    started = []

    def _start_daemon(fn, name=None):
        started.append((fn.__name__, name))

    def _fn(name):
        def _inner():
            return None

        _inner.__name__ = name
        return _inner

    start_runtime_services(
        start_daemon_fn=_start_daemon,
        screen_share_enabled=False,
        dashboard_enabled=False,
        voice_input_enabled=False,
        start_screen_share_window_fn=_fn("screen"),
        thought_logger_thread_fn=_fn("thought_logger_thread"),
        start_websocket_fn=_fn("start_websocket"),
        start_trade_reconciler_fn=_fn("start_trade_reconciler"),
        auto_backtester_daemon_fn=_fn("auto_backtester_daemon"),
        start_dashboard_fn=_fn("start_dashboard"),
        voice_listener_thread_fn=_fn("voice_listener_thread"),
        supervisor_loop_fn=app.supervisor_loop,
        dna_rewrite_daemon_fn=_fn("dna_rewrite_daemon"),
        gap_recovery_daemon_fn=_fn("gap_recovery_daemon"),
        pre_dream_daemon_fn=_fn("pre_dream_daemon"),
        auto_journal_daemon_fn=_fn("auto_journal_daemon"),
        auto_backtest_daemon_fn=_fn("auto_backtest_daemon"),
    )

    assert created == [app.engine]
    assert app.engine.swarm is not None


def test_start_runtime_services_injects_blackboard_and_meta_orchestrator():
    class Engine:
        def __init__(self):
            self.config = SimpleNamespace(swarm_enabled=False)
            self.swarm = None
            self.bound = 0
            self.meta_agent_orchestrator = None

        def bind_blackboard(self, blackboard):
            self.bound += 1
            self.blackboard = blackboard

    class App:
        def __init__(self):
            self.engine = Engine()
            self.container = SimpleNamespace(
                blackboard=object(),
                meta_agent_orchestrator=object(),
            )

        def supervisor_loop(self):
            return None

    app = App()

    def _start_daemon(_fn, name=None):
        return name

    def _fn(name):
        def _inner():
            return None

        _inner.__name__ = name
        return _inner

    start_runtime_services(
        start_daemon_fn=_start_daemon,
        screen_share_enabled=False,
        dashboard_enabled=False,
        voice_input_enabled=False,
        start_screen_share_window_fn=_fn("screen"),
        thought_logger_thread_fn=_fn("thought_logger_thread"),
        start_websocket_fn=_fn("start_websocket"),
        start_trade_reconciler_fn=_fn("start_trade_reconciler"),
        auto_backtester_daemon_fn=_fn("auto_backtester_daemon"),
        start_dashboard_fn=_fn("start_dashboard"),
        voice_listener_thread_fn=_fn("voice_listener_thread"),
        supervisor_loop_fn=app.supervisor_loop,
        dna_rewrite_daemon_fn=_fn("dna_rewrite_daemon"),
        gap_recovery_daemon_fn=_fn("gap_recovery_daemon"),
        pre_dream_daemon_fn=_fn("pre_dream_daemon"),
        auto_journal_daemon_fn=_fn("auto_journal_daemon"),
        auto_backtest_daemon_fn=_fn("auto_backtest_daemon"),
    )

    assert app.engine.bound == 1
    assert app.engine.meta_agent_orchestrator is app.container.meta_agent_orchestrator
    assert cast(Any, app).blackboard is app.container.blackboard
