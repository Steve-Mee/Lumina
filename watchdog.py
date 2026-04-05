from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

HEARTBEAT_FILE = Path("/tmp/lumina_heartbeat")
PID_FILE = Path("/tmp/lumina_child.pid")


def _touch_heartbeat() -> None:
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.touch()


def _prepare_persistent_links() -> None:
    """Route file-based defaults into mounted volume paths without app code changes."""
    links = {
        Path("/app/lumina_sim_state.json"): Path(os.getenv("LUMINA_STATE_FILE", "/app/state/lumina_sim_state.json")),
        Path("/app/lumina_daytrading_bible.json"): Path(os.getenv("LUMINA_BIBLE_FILE", "/app/state/lumina_daytrading_bible.json")),
        Path("/app/lumina_thought_log.jsonl"): Path(os.getenv("LUMINA_THOUGHT_LOG", "/app/state/lumina_thought_log.jsonl")),
        Path("/app/lumina_full_log.csv"): Path(os.getenv("LUMINA_LOG_FILE", "/app/logs/lumina_full_log.csv")),
    }

    for src, dst in links.items():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists() and not src.is_symlink():
            # Keep existing non-symlink files as-is.
            continue
        if src.is_symlink() or src.exists():
            src.unlink(missing_ok=True)
        src.symlink_to(dst)


def _forward_shutdown(child: Optional[subprocess.Popen], signum: int) -> None:
    if child is None or child.poll() is not None:
        return

    # Ask child to gracefully flush state first.
    try:
        child.send_signal(signal.SIGINT)
    except Exception:
        pass

    deadline = time.time() + 30
    while time.time() < deadline and child.poll() is None:
        _touch_heartbeat()
        time.sleep(0.5)

    if child.poll() is None:
        try:
            child.terminate()
        except Exception:
            pass

    deadline = time.time() + 10
    while time.time() < deadline and child.poll() is None:
        _touch_heartbeat()
        time.sleep(0.5)

    if child.poll() is None:
        try:
            child.kill()
        except Exception:
            pass


def main() -> int:
    entrypoint = os.getenv("LUMINA_ENTRYPOINT", "lumina_v45.1.1.py")
    max_restarts = int(os.getenv("LUMINA_MAX_RESTARTS", "5"))

    _prepare_persistent_links()

    child: Optional[subprocess.Popen] = None
    shutting_down = {"value": False}

    def _handle_signal(signum: int, _frame) -> None:
        shutting_down["value"] = True
        _forward_shutdown(child, signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    restart_count = 0
    while True:
        if shutting_down["value"]:
            return 0

        _touch_heartbeat()
        cmd = [sys.executable, entrypoint]
        child = subprocess.Popen(cmd, cwd="/app")
        PID_FILE.write_text(str(child.pid), encoding="utf-8")

        while child.poll() is None and not shutting_down["value"]:
            _touch_heartbeat()
            time.sleep(2)

        if shutting_down["value"]:
            _forward_shutdown(child, signal.SIGTERM)
            return 0

        exit_code = child.returncode
        if exit_code == 0:
            return 0

        restart_count += 1
        if restart_count > max_restarts:
            print(f"[watchdog] max restarts exceeded ({max_restarts}); last exit={exit_code}", flush=True)
            return exit_code or 1

        backoff = min(5 * restart_count, 30)
        print(
            f"[watchdog] child crashed with exit={exit_code}; restart {restart_count}/{max_restarts} in {backoff}s",
            flush=True,
        )
        for _ in range(backoff):
            _touch_heartbeat()
            time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
