# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import logging
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from collections import deque
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path(__file__).resolve().parent
TEMP_DIR = Path(tempfile.gettempdir())
HEARTBEAT_FILE = WORKSPACE_ROOT / "state" / "lumina_heartbeat"
PID_FILE = TEMP_DIR / "lumina_child.pid"
SAFE_RESTART_EXIT_CODE = 42
PREFLIGHT_FAIL_EXIT_CODE = 2
_HOURLY_WINDOW_S = 3600.0


def _load_max_restarts_per_hour() -> int:
    env_val = os.getenv("LUMINA_MAX_RESTARTS_PER_HOUR", "").strip()
    if env_val:
        try:
            return max(1, int(env_val))
        except ValueError:
            pass
    try:
        import yaml

        config_path = os.getenv("LUMINA_CONFIG", str(WORKSPACE_ROOT / "config.yaml"))
        with open(config_path, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        headless = cfg.get("headless") if isinstance(cfg.get("headless"), dict) else {}
        production = headless.get("production") if isinstance(headless.get("production"), dict) else {}
        return max(1, int(production.get("max_process_restarts_per_hour", 6) or 6))
    except Exception:
        logger.debug("watchdog failed to load max_process_restarts_per_hour", exc_info=True)
        return 6


def _start_watchdog_observability():
    """Load config and start the ObservabilityService if monitoring is enabled.

    Wrapped in a broad try/except so any import or config error can never crash
    the watchdog itself.
    """
    try:
        import yaml
        from lumina_core.monitoring import ObservabilityService

        config_path = os.getenv("LUMINA_CONFIG", str(WORKSPACE_ROOT / "config.yaml"))
        with open(config_path, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}

        obs = ObservabilityService.from_config(cfg)
        obs.start()
        return obs
    except Exception:
        logging.exception("Unhandled broad exception fallback in watchdog.py:42")
        return None


def _touch_heartbeat() -> None:
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.touch()


def _read_last_runtime_status() -> str:
    path = WORKSPACE_ROOT / "state" / "headless_runtime_status.json"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")[:500]
    except Exception:
        return ""


def _prepare_persistent_links() -> None:
    """Route file-based defaults into mounted volume paths without app code changes."""
    state_root = Path(os.getenv("LUMINA_STATE_DIR", str(WORKSPACE_ROOT / "state")))
    logs_root = Path(os.getenv("LUMINA_LOGS_DIR", str(WORKSPACE_ROOT / "logs")))
    links = {
        WORKSPACE_ROOT / "lumina_sim_state.json": Path(
            os.getenv("LUMINA_STATE_FILE", str(state_root / "lumina_sim_state.json"))
        ),
        WORKSPACE_ROOT / "lumina_daytrading_bible.json": Path(
            os.getenv("LUMINA_BIBLE_FILE", str(state_root / "lumina_daytrading_bible.json"))
        ),
        WORKSPACE_ROOT / "thought_log.jsonl": Path(
            os.getenv("LUMINA_THOUGHT_LOG", str(state_root / "thought_log.jsonl"))
        ),
        WORKSPACE_ROOT / "lumina_full_log.csv": Path(
            os.getenv("LUMINA_LOG_FILE", str(logs_root / "lumina_full_log.csv"))
        ),
    }

    for src, dst in links.items():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists() and not src.is_symlink():
            continue
        if src.is_symlink() or src.exists():
            src.unlink(missing_ok=True)
        try:
            src.symlink_to(dst)
        except OSError:
            logger.debug("watchdog symlink skipped for %s", src)


def _forward_shutdown(child: Optional[subprocess.Popen], signum: int) -> None:
    if child is None or child.poll() is not None:
        return

    try:
        child.send_signal(signal.SIGINT)
    except Exception:
        logger.exception("watchdog failed to send SIGINT to child process")

    deadline = time.time() + 30
    while time.time() < deadline and child.poll() is None:
        _touch_heartbeat()
        time.sleep(0.5)

    if child.poll() is None:
        try:
            child.terminate()
        except Exception:
            logger.exception("watchdog failed to terminate child process")

    deadline = time.time() + 10
    while time.time() < deadline and child.poll() is None:
        _touch_heartbeat()
        time.sleep(0.5)

    if child.poll() is None:
        try:
            child.kill()
        except Exception:
            logger.exception("watchdog failed to kill child process")


def main() -> int:
    entrypoint = os.getenv(
        "LUMINA_ENTRYPOINT",
        str(WORKSPACE_ROOT / "lumina_core" / "engine" / "runtime_entrypoint.py"),
    )
    entrypoint_args = shlex.split(os.getenv("LUMINA_ENTRYPOINT_ARGS", "--mode auto"))
    max_restarts = int(os.getenv("LUMINA_MAX_RESTARTS", "5"))
    max_restarts_per_hour = _load_max_restarts_per_hour()
    cwd = Path(os.getenv("LUMINA_WORKSPACE", str(WORKSPACE_ROOT)))

    _prepare_persistent_links()

    obs = _start_watchdog_observability()

    child: Optional[subprocess.Popen] = None
    shutting_down = {"value": False}

    def _handle_signal(signum: int, _frame) -> None:
        shutting_down["value"] = True
        _forward_shutdown(child, signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    restart_count = 0
    crash_timestamps: deque[float] = deque()
    while True:
        if shutting_down["value"]:
            if obs is not None:
                obs.stop()
            return 0

        _touch_heartbeat()
        cmd = [sys.executable, entrypoint, *entrypoint_args]
        child = subprocess.Popen(cmd, cwd=str(cwd))
        PID_FILE.write_text(str(child.pid), encoding="utf-8")

        while child.poll() is None and not shutting_down["value"]:
            _touch_heartbeat()
            time.sleep(2)

        if shutting_down["value"]:
            _forward_shutdown(child, signal.SIGTERM)
            if obs is not None:
                obs.stop()
            return 0

        exit_code = child.returncode if child.returncode is not None else 1

        if exit_code == 0:
            if obs is not None:
                obs.stop()
            return 0

        if exit_code == PREFLIGHT_FAIL_EXIT_CODE:
            status_snippet = _read_last_runtime_status()
            print(
                f"[watchdog] preflight/config failure (exit={exit_code}); not restarting. "
                f"status={status_snippet}",
                flush=True,
            )
            if obs is not None:
                obs.stop()
            return exit_code

        if exit_code == SAFE_RESTART_EXIT_CODE:
            restart_count = 0
            print("[watchdog] safe-boundary restart requested; restarting immediately", flush=True)
            if obs is not None:
                try:
                    obs.record_process_restart()
                except Exception:
                    logger.exception("watchdog failed to record safe restart metric")
            continue

        restart_count += 1
        now = time.time()
        crash_timestamps.append(now)
        while crash_timestamps and (now - crash_timestamps[0]) > _HOURLY_WINDOW_S:
            crash_timestamps.popleft()

        if obs is not None:
            try:
                obs.record_process_restart()
            except Exception:
                logger.exception("watchdog failed to record process restart metric")

        if len(crash_timestamps) > max_restarts_per_hour:
            status_snippet = _read_last_runtime_status()
            msg = (
                f"[watchdog] hourly restart cap exceeded ({max_restarts_per_hour}/hour); "
                f"last exit={exit_code} status={status_snippet}"
            )
            print(msg, flush=True)
            if obs is not None:
                try:
                    obs.send_alert(
                        "watchdog_restart_cap",
                        msg,
                        data={"exit_code": exit_code, "hourly_count": len(crash_timestamps)},
                    )
                except Exception:
                    logger.exception("watchdog failed to send hourly cap alert")
                obs.stop()
            return exit_code or 1

        if restart_count > max_restarts:
            status_snippet = _read_last_runtime_status()
            print(
                f"[watchdog] max restarts exceeded ({max_restarts}); last exit={exit_code} "
                f"status={status_snippet}",
                flush=True,
            )
            if obs is not None:
                obs.stop()
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
