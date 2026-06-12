import logging
import os
from pathlib import Path
from typing import Callable, Optional

from lumina_core.birth.birth_certificate import policy_path, validate_certificate_artifacts
from lumina_core.birth.config import load_birth_v2_config
from lumina_core.engine.swarm_manager import SwarmManager

_log = logging.getLogger("lumina")


RuntimeWorker = Callable[[], None]
_WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _assert_birth_phase_completed(workspace_root: Path | None = None) -> None:
    root = workspace_root or _WORKSPACE_ROOT
    thresholds = load_birth_v2_config(root).certificate_thresholds
    ok, reason, _cert = validate_certificate_artifacts(root, thresholds=thresholds)
    if ok:
        return
    pol = policy_path(root)
    raise RuntimeError(
        "Birth Phase v2 certificate invalid or missing "
        f"({reason}); runtime services stay fail-closed until certified birth completes. "
        f"policy_exists={pol.is_file()}"
    )


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
    state_persist_daemon_fn: Optional[RuntimeWorker] = None,
    dna_rewrite_daemon_fn: RuntimeWorker,
    gap_recovery_daemon_fn: RuntimeWorker,
    pre_dream_daemon_fn: Optional[RuntimeWorker],
    auto_journal_daemon_fn: RuntimeWorker,
    auto_backtest_daemon_fn: RuntimeWorker,
    enforce_birth_guard: bool = False,
) -> None:
    """Start all runtime workers from a single engine-driven bootstrap call."""
    if enforce_birth_guard:
        _assert_birth_phase_completed()
    app = getattr(supervisor_loop_fn, "__self__", None)
    engine = getattr(app, "engine", None)
    container = getattr(app, "container", None)
    if engine is not None and container is not None:
        blackboard = getattr(container, "blackboard", None)
        if blackboard is not None:
            engine.bind_blackboard(blackboard)
            setattr(app, "blackboard", blackboard)

        meta_agent_orchestrator = getattr(container, "meta_agent_orchestrator", None)
        if meta_agent_orchestrator is not None:
            engine.meta_agent_orchestrator = meta_agent_orchestrator
            setattr(app, "meta_agent_orchestrator", meta_agent_orchestrator)

    if (
        engine is not None
        and getattr(engine, "swarm", None) is None
        and bool(getattr(engine.config, "swarm_enabled", True))
    ):
        engine.swarm = SwarmManager(engine)
        if app is not None and not hasattr(app, "swarm_manager"):
            setattr(app, "swarm_manager", engine.swarm)

    if screen_share_enabled:
        _log.info("LIVE_FEED_BOOT_STEP,runtime_bootstrap,screen_share_enabled=true,action=start_tk_window_fn")
        start_screen_share_window_fn()
    else:
        _log.info(
            "LIVE_FEED_BOOT_SKIP,runtime_bootstrap,screen_share_enabled=false,note=no_tk_thread_no_launcher_jsonl_from_runtime_bootstrap",
        )

    start_daemon_fn(thought_logger_thread_fn, name="thought-logger")
    start_daemon_fn(start_websocket_fn, name="websocket-listener")
    start_daemon_fn(start_trade_reconciler_fn, name="trade-reconciler")
    start_daemon_fn(auto_backtester_daemon_fn, name="auto-backtester-daemon")

    if dashboard_enabled:
        start_daemon_fn(start_dashboard_fn, name="dashboard")
    if voice_input_enabled:
        start_daemon_fn(voice_listener_thread_fn, name="voice-listener")

    start_daemon_fn(supervisor_loop_fn, name="supervisor-loop")
    if state_persist_daemon_fn is not None:
        start_daemon_fn(state_persist_daemon_fn, name="state-persist-daemon")
    start_daemon_fn(dna_rewrite_daemon_fn, name="dna-rewrite-daemon")
    start_daemon_fn(gap_recovery_daemon_fn, name="gap-recovery-daemon")
    if pre_dream_daemon_fn is not None:
        start_daemon_fn(pre_dream_daemon_fn, name="pre-dream-daemon")
    start_daemon_fn(auto_journal_daemon_fn, name="auto-journal-daemon")
    start_daemon_fn(auto_backtest_daemon_fn, name="auto-backtest-daemon")
