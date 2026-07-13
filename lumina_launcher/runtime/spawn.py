"""Single source of truth for runtime subprocess command building and daemon spawn."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from lumina_launcher.telemetry.events import log_event, timed_event
from lumina_launcher.telemetry.hooks import emit_launcher_event

logger = logging.getLogger(__name__)

DEFAULT_RUNTIME_ENTRY = Path("lumina_core/engine/runtime_entrypoint.py")
LOOP_DAEMON_MODES = frozenset({"sim", "paper", "auto"})
REAL_MODES = frozenset({"real", "sim_real_guard", "live"})


@dataclass(frozen=True, slots=True)
class SpawnResult:
    ok: bool
    pid: int
    mode: str
    command: list[str]
    message: str


def _python_has_module(python_cmd: str, module_name: str, *, cwd: Path) -> bool:
    try:
        result = subprocess.run(
            [python_cmd, "-c", f"import {module_name}"],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=4,
        )
        return result.returncode == 0
    except Exception:
        return False


def resolve_runtime_python(launcher_root: Path) -> str:
    """Select a Python interpreter that can start runtime_entrypoint safely."""
    env_python = os.getenv("LUMINA_PYTHON", "").strip()
    candidates: list[str] = []
    if env_python:
        candidates.append(env_python)
    candidates.append(sys.executable)
    venv_python = launcher_root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if venv_python.exists():
        candidates.append(str(venv_python))
    candidates.append("python")

    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        if _python_has_module(normalized, "dotenv", cwd=launcher_root):
            return normalized
    logger.warning("No Python interpreter with python-dotenv found; falling back to plain 'python'")
    return "python"


def validate_loop_mode(mode: str, *, extra_argv: list[str]) -> tuple[bool, str]:
    normalized = str(mode or "auto").strip().lower() or "auto"
    if normalized in REAL_MODES and "--real-safe" not in extra_argv:
        return (
            False,
            "CLI start for REAL/sim_real_guard requires --real-safe. Prefer Command Deck go-live flow.",
        )
    return True, ""


def build_runtime_command(
    launcher_root: Path,
    runtime_entry: Path,
    mode: str,
    *,
    headless: bool = False,
    smoke: bool = False,
    extra_argv: list[str] | None = None,
) -> list[str]:
    """Build argv for runtime_entrypoint (full loop, production headless, or smoke)."""
    normalized_mode = str(mode or "auto").strip().lower() or "auto"
    runtime_python = resolve_runtime_python(launcher_root)
    command = [runtime_python, str(launcher_root / runtime_entry), "--mode", normalized_mode]
    if smoke:
        command.append("--smoke")
    elif headless:
        command.append("--headless")
    if extra_argv:
        command.extend(extra_argv)
    emit_launcher_event(
        "launcher.spawn.build",
        mode=normalized_mode,
        headless=headless,
        smoke=smoke,
        command=" ".join(command),
    )
    return command


def _read_runtime_stderr_tail(launcher_root: Path, *, max_lines: int = 6) -> str:
    stderr_path = launcher_root / "logs" / "launcher_runtime_stderr.log"
    if not stderr_path.exists():
        return ""
    try:
        lines = stderr_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        return ""
    return " | ".join(non_empty[-max_lines:])


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            return str(pid) in (result.stdout or "")
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def save_process_state(
    launcher_root: Path,
    *,
    pid: int,
    command: list[str],
    mode: str,
    kind: str = "loop",
) -> None:
    path = launcher_root / "state" / "launcher_bot_process.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    payload: dict[str, Any] = {
        "pid": int(pid),
        "mode": str(mode),
        "kind": kind,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "command": command,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def start_runtime_daemon(
    launcher_root: Path,
    runtime_entry: Path,
    mode: str,
    *,
    extra_argv: list[str] | None = None,
    kind: str = "loop",
) -> SpawnResult:
    """Spawn full supervisor loop in background; returns PID without blocking."""
    entry = runtime_entry if runtime_entry.is_absolute() else launcher_root / runtime_entry
    if not entry.exists():
        return SpawnResult(False, 0, mode, [], f"Runtime entry not found: {entry}")

    extra = list(extra_argv or [])
    ok_mode, mode_msg = validate_loop_mode(mode, extra_argv=extra)
    if not ok_mode:
        return SpawnResult(False, 0, mode, [], mode_msg)

    normalized_mode = str(mode or "auto").strip().lower() or "auto"
    command = build_runtime_command(
        launcher_root,
        runtime_entry,
        normalized_mode,
        headless=False,
        extra_argv=extra,
    )
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    log_dir = launcher_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stderr_log_path = log_dir / "launcher_runtime_stderr.log"
    stderr_handle = open(stderr_log_path, "a", encoding="utf-8")
    try:
        with timed_event("launcher.loop.daemon_start", mode=normalized_mode, kind=kind):
            proc = subprocess.Popen(
                command,
                cwd=str(launcher_root),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=stderr_handle,
            )
        stderr_handle.flush()
        time.sleep(1.0)
        still_running = proc.poll() is None and _pid_is_alive(proc.pid)
        if not still_running:
            failure_tail = _read_runtime_stderr_tail(launcher_root)
            log_event(
                "launcher.loop.daemon_failed_fast",
                level=logging.ERROR,
                pid=proc.pid,
                mode=normalized_mode,
                tail=failure_tail,
            )
            detail = f" Runtime stderr: {failure_tail}" if failure_tail else " Check logs/launcher_runtime_stderr.log."
            return SpawnResult(False, proc.pid, normalized_mode, command, f"Runtime stopped immediately.{detail}")

        save_process_state(launcher_root, pid=proc.pid, command=command, mode=normalized_mode, kind=kind)
        emit_launcher_event(
            "launcher.loop.daemon_started",
            pid=proc.pid,
            mode=normalized_mode,
            kind=kind,
        )
        return SpawnResult(True, proc.pid, normalized_mode, command, f"Engine started (pid={proc.pid}, mode={normalized_mode})")
    except FileNotFoundError:
        return SpawnResult(False, 0, normalized_mode, command, "Python interpreter not found. Check LUMINA_PYTHON.")
    except Exception as exc:
        log_event("launcher.loop.daemon_failed", level=logging.ERROR, error=str(exc), mode=normalized_mode)
        return SpawnResult(False, 0, normalized_mode, command, f"Failed to start engine: {exc}")
    finally:
        stderr_handle.close()


def start_headless_daemon(
    launcher_root: Path,
    runtime_entry: Path,
    mode: str,
    *,
    duration_minutes: int | None = None,
    extra_argv: list[str] | None = None,
) -> SpawnResult:
    """Spawn headless one-shot runtime in background (overnight SIM / stability)."""
    extra = list(extra_argv or [])
    if duration_minutes is not None:
        extra.append(f"--duration={duration_minutes}")

    normalized_mode = str(mode or "sim").strip().lower() or "sim"
    command = build_runtime_command(
        launcher_root,
        runtime_entry,
        normalized_mode,
        smoke=True,
        extra_argv=extra,
    )
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    log_dir = launcher_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stderr_log_path = log_dir / "launcher_runtime_stderr.log"
    stderr_handle = open(stderr_log_path, "a", encoding="utf-8")
    try:
        with timed_event("launcher.headless.daemon_start", mode=normalized_mode):
            proc = subprocess.Popen(
                command,
                cwd=str(launcher_root),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=stderr_handle,
            )
        stderr_handle.flush()
        save_process_state(
            launcher_root,
            pid=proc.pid,
            command=command,
            mode=normalized_mode,
            kind="headless",
        )
        emit_launcher_event(
            "launcher.headless.daemon_started",
            pid=proc.pid,
            mode=normalized_mode,
        )
        return SpawnResult(
            True,
            proc.pid,
            normalized_mode,
            command,
            f"Headless runtime started (pid={proc.pid}, mode={normalized_mode})",
        )
    except Exception as exc:
        log_event("launcher.headless.daemon_failed", level=logging.ERROR, error=str(exc))
        return SpawnResult(False, 0, normalized_mode, command, f"Failed to start headless runtime: {exc}")
    finally:
        stderr_handle.close()
