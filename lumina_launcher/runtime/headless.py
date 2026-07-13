"""Headless one-shot runtime entry (CI/smoke/overnight)."""

from __future__ import annotations

import sys
from pathlib import Path

from lumina_launcher.telemetry.hooks import emit_launcher_event


def repo_root() -> Path:
    """Repository root (parent of the ``lumina_launcher`` package directory)."""
    return Path(__file__).resolve().parents[2]


def run_headless(argv: list[str] | None = None) -> int:
    """Run one-shot / stability-check headless runtime. Returns process exit code."""
    from dotenv import load_dotenv
    from lumina_core.engine.runtime_entrypoint import run_with_mode

    root = repo_root()
    load_dotenv(root / ".env")
    args = list(argv if argv is not None else sys.argv[1:])

    mode_hint = "sim"
    for arg in args:
        if arg.startswith("--mode="):
            mode_hint = arg.split("=", 1)[1].strip().lower() or "sim"
            break
        if arg == "--mode" and args.index(arg) + 1 < len(args):
            mode_hint = args[args.index(arg) + 1].strip().lower() or "sim"
            break

    emit_launcher_event("launcher.headless.begin", mode=mode_hint)
    try:
        exit_code = int(run_with_mode(mode_hint, argv=args))
    except Exception as exc:
        emit_launcher_event("launcher.headless.end", status="error", error=str(exc))
        raise
    emit_launcher_event("launcher.headless.end", status="ok", exit_code=exit_code)
    return exit_code
