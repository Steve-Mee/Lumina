"""Full autonomous supervisor loop (daemon default, optional foreground)."""

from __future__ import annotations

import sys
from pathlib import Path

from lumina_launcher.runtime.spawn import DEFAULT_RUNTIME_ENTRY, start_runtime_daemon
from lumina_launcher.telemetry.hooks import emit_launcher_event


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_loop_daemon(mode: str, *, extra_argv: list[str] | None = None) -> int:
    """Start full supervisor loop as background daemon; print PID and exit."""
    root = repo_root()
    result = start_runtime_daemon(root, DEFAULT_RUNTIME_ENTRY, mode, extra_argv=extra_argv)
    if result.ok:
        print(f"LUMINA engine started: pid={result.pid} mode={result.mode}")
        emit_launcher_event("launcher.loop.started", pid=result.pid, mode=result.mode)
        return 0
    print(f"LUMINA engine start failed: {result.message}", file=sys.stderr)
    return 1


def run_loop_foreground(mode: str, *, extra_argv: list[str] | None = None) -> int:
    """Blocking full supervisor loop for debugging (Ctrl+C stops)."""
    from dotenv import load_dotenv
    from lumina_core.engine.runtime_entrypoint import run_with_mode

    root = repo_root()
    load_dotenv(root / ".env")
    argv = ["--mode", mode]
    if extra_argv:
        argv.extend(extra_argv)
    emit_launcher_event("launcher.loop.foreground_begin", mode=mode)
    exit_code = int(run_with_mode(mode, argv=argv))
    emit_launcher_event("launcher.loop.foreground_end", mode=mode, exit_code=exit_code)
    return exit_code
