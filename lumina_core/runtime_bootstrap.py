from typing import Callable, Optional

from lumina_core.engine.swarm_manager import SwarmManager


RuntimeWorker = Callable[[], None]


def start_runtime_services(
    *,
    start_daemon_fn: Callable,
    screen_share_enabled: bool,
    dashboard_enabled: bool,
    voice_input_enabled: bool,
    start_screen_share_window_fn: RuntimeWorker,
    thought_logger_thread_fn: RuntimeWorker,
    start_websocket_fn: RuntimeWorker,
    start_trade_reconciler_fn: RuntimeWorker,
    auto_backtester_daemon_fn: RuntimeWorker,
    start_dashboard_fn: RuntimeWorker,
    voice_listener_thread_fn: RuntimeWorker,
    supervisor_loop_fn: RuntimeWorker,
    dna_rewrite_daemon_fn: RuntimeWorker,
    gap_recovery_daemon_fn: RuntimeWorker,
    pre_dream_daemon_fn: Optional[RuntimeWorker],
    auto_journal_daemon_fn: RuntimeWorker,
    auto_backtest_daemon_fn: RuntimeWorker,
) -> None:
    """Start all runtime workers from a single engine-driven bootstrap call."""
    app = getattr(supervisor_loop_fn, "__self__", None)
    engine = getattr(app, "engine", None)
    if engine is not None and getattr(engine, "swarm", None) is None and bool(getattr(engine.config, "swarm_enabled", True)):
        engine.swarm = SwarmManager(engine)
        if app is not None and not hasattr(app, "swarm_manager"):
            setattr(app, "swarm_manager", engine.swarm)

    if screen_share_enabled:
        start_screen_share_window_fn()

    start_daemon_fn(thought_logger_thread_fn, name="thought-logger")
    start_daemon_fn(start_websocket_fn, name="websocket-listener")
    start_daemon_fn(start_trade_reconciler_fn, name="trade-reconciler")
    start_daemon_fn(auto_backtester_daemon_fn, name="auto-backtester-daemon")

    if dashboard_enabled:
        start_daemon_fn(start_dashboard_fn, name="dashboard")
    if voice_input_enabled:
        start_daemon_fn(voice_listener_thread_fn, name="voice-listener")

    start_daemon_fn(supervisor_loop_fn, name="supervisor-loop")
    start_daemon_fn(dna_rewrite_daemon_fn, name="dna-rewrite-daemon")
    start_daemon_fn(gap_recovery_daemon_fn, name="gap-recovery-daemon")
    if pre_dream_daemon_fn is not None:
        start_daemon_fn(pre_dream_daemon_fn, name="pre-dream-daemon")
    start_daemon_fn(auto_journal_daemon_fn, name="auto-journal-daemon")
    start_daemon_fn(auto_backtest_daemon_fn, name="auto-backtest-daemon")
