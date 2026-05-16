"""
LUMINA Core - Process Manager
Handles starting, stopping, and monitoring the Lumina runtime process.
Extracted from the original monolithic launcher (now `lumina_launcher/` + `streamlit_launcher.py`).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import psutil  # type: ignore[import]

from lumina_launcher.observability import log_event, timed_event

logger = logging.getLogger(__name__)


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


class ProcessManager:
    def __init__(self, launcher_root: Path, runtime_entry: Path):
        self.launcher_root = launcher_root
        self.runtime_entry = runtime_entry
        self.process_state_path = launcher_root / "state" / "launcher_bot_process.json"
        self._alive_cache: tuple[float, bool] | None = None

    def _normalize_process_cmdline(self, text: str) -> str:
        return text.lower().replace("\\\\", "/").replace("\\", "/")

    def _command_line_matches_lumina_runtime(self, cmdline_raw: str) -> bool:
        if not cmdline_raw:
            return False
        norm = self._normalize_process_cmdline(cmdline_raw)
        if "lumina_runtime.py" in norm:
            return True
        marker = (self.launcher_root / self.runtime_entry).resolve().as_posix().lower()
        return marker in norm or "runtime_entrypoint.py" in norm and "lumina_core" in norm

    def _pid_is_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
                    check=False, capture_output=True, text=True
                )
                return str(pid) in (result.stdout or "")
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _enumerate_lumina_runtime_pids(self) -> list[int]:
        collected: list[int] = []
        try:
            for proc in psutil.process_iter(["pid", "cmdline"]):
                try:
                    raw_cmd = proc.info.get("cmdline") or ()
                    blob = " ".join(str(arg) for arg in raw_cmd)
                    if self._command_line_matches_lumina_runtime(blob):
                        pid_val = proc.info.get("pid")
                        if pid_val:
                            collected.append(int(pid_val))
                except Exception:
                    continue
        except Exception:
            pass
        return list(dict.fromkeys(p for p in collected if p > 0))

    def _find_external_runtime_pid(self) -> int:
        pids = self._enumerate_lumina_runtime_pids()
        return pids[0] if pids else 0

    def _command_line_matches_backend(self, cmdline_raw: str) -> bool:
        if not cmdline_raw:
            return False
        norm = self._normalize_process_cmdline(cmdline_raw)
        return (
            "backend.app:app" in norm
            or "lumina_os/run_backend.ps1" in norm
            or ("uvicorn" in norm and "port 8000" in norm)
        )

    def _command_line_matches_launcher_worker(self, cmdline_raw: str) -> bool:
        if not cmdline_raw:
            return False
        norm = self._normalize_process_cmdline(cmdline_raw)
        return "python -m lumina_launcher --headless" in norm or "python -m lumina_launcher --stability-check" in norm

    def _enumerate_backend_pids(self) -> list[int]:
        collected: list[int] = []
        try:
            for proc in psutil.process_iter(["pid", "cmdline"]):
                try:
                    raw_cmd = proc.info.get("cmdline") or ()
                    blob = " ".join(str(arg) for arg in raw_cmd)
                    if self._command_line_matches_backend(blob):
                        pid_val = proc.info.get("pid")
                        if pid_val:
                            collected.append(int(pid_val))
                except Exception:
                    continue
        except Exception:
            pass
        return list(dict.fromkeys(p for p in collected if p > 0))

    def _enumerate_launcher_worker_pids(self) -> list[int]:
        collected: list[int] = []
        try:
            for proc in psutil.process_iter(["pid", "cmdline"]):
                try:
                    raw_cmd = proc.info.get("cmdline") or ()
                    blob = " ".join(str(arg) for arg in raw_cmd)
                    if self._command_line_matches_launcher_worker(blob):
                        pid_val = proc.info.get("pid")
                        if pid_val:
                            collected.append(int(pid_val))
                except Exception:
                    continue
        except Exception:
            pass
        return list(dict.fromkeys(p for p in collected if p > 0))

    def _load_process_state(self) -> dict[str, Any]:
        if not self.process_state_path.exists():
            return {}
        try:
            import json
            return json.loads(self.process_state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_process_state(self, pid: int, command: list[str]) -> None:
        self.process_state_path.parent.mkdir(parents=True, exist_ok=True)
        import json
        payload = {
            "pid": int(pid),
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "command": command,
        }
        self.process_state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _clear_process_state(self) -> None:
        try:
            self.process_state_path.unlink(missing_ok=True)
        except Exception:
            pass

    def _read_runtime_stderr_tail(self, *, max_lines: int = 6) -> str:
        stderr_path = self.launcher_root / "logs" / "launcher_runtime_stderr.log"
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

    def _reconcile_stale_process_state(self) -> None:
        """Drop launcher_bot_process.json when the recorded PID is no longer running."""
        state = self._load_process_state()
        pid = int(state.get("pid", 0) or 0)
        if pid <= 0:
            return
        if self._pid_is_alive(pid):
            return
        external = self._find_external_runtime_pid()
        if external > 0 and self._pid_is_alive(external):
            return
        self._clear_process_state()

    def is_process_alive(self) -> bool:
        now = time.monotonic()
        if self._alive_cache and (now - self._alive_cache[0]) < 2.0:
            return self._alive_cache[1]
        self._reconcile_stale_process_state()
        state = self._load_process_state()
        pid = int(state.get("pid", 0) or 0)
        result = False
        with timed_event("launcher.proc.check", pid=pid):
            if pid > 0 and self._pid_is_alive(pid):
                result = True
            else:
                external = self._find_external_runtime_pid()
                result = external > 0 and self._pid_is_alive(external)
        self._alive_cache = (now, result)
        return result

    def start_bot(self, mode: str = "auto") -> tuple[bool, str]:
        if not self.runtime_entry.exists():
            return False, f"Runtime entry not found: {self.runtime_entry}"
        if self.is_process_alive():
            return True, "Bot is already running"

        normalized_mode = str(mode or "auto").strip().lower() or "auto"
        runtime_python = resolve_runtime_python(self.launcher_root)
        command = [runtime_python, str(self.runtime_entry), "--mode", normalized_mode]
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        log_dir = self.launcher_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stderr_log_path = log_dir / "launcher_runtime_stderr.log"
        stderr_handle = open(stderr_log_path, "a", encoding="utf-8")
        try:
            with timed_event("launcher.proc.start", mode=normalized_mode):
                proc = subprocess.Popen(
                    command,
                    cwd=str(self.launcher_root),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_handle,
                )
            self._save_process_state(proc.pid, command)
            stderr_handle.flush()
            time.sleep(1.0)
            self._alive_cache = None
            still_running = proc.poll() is None and self._pid_is_alive(proc.pid)
            if not still_running:
                self._clear_process_state()
                failure_tail = self._read_runtime_stderr_tail()
                log_event(
                    "launcher.proc.start_failed_fast",
                    level=logging.ERROR,
                    pid=proc.pid,
                    mode=normalized_mode,
                    tail=failure_tail,
                )
                detail = f" Runtime stderr: {failure_tail}" if failure_tail else " Check logs/launcher_runtime_stderr.log."
                return False, f"Runtime stopped immediately after start.{detail}"
            log_event("launcher.proc.started", pid=proc.pid, mode=normalized_mode, python=runtime_python)
            return True, f"Bot started (pid={proc.pid})"
        except FileNotFoundError:
            return False, "Python interpreter not found. Check LUMINA_PYTHON env var."
        except Exception as exc:
            log_event("launcher.proc.start_failed", level=logging.ERROR, error=str(exc), mode=normalized_mode)
            return False, f"Failed to start bot: {exc}"
        finally:
            stderr_handle.close()

    def stop_bot(self) -> tuple[bool, str]:
        target_pids = []
        state = self._load_process_state()
        pid = int(state.get("pid", 0) or 0)
        if pid > 0:
            target_pids.append(pid)

        external = self._find_external_runtime_pid()
        if external > 0:
            target_pids.append(external)

        target_pids = list(dict.fromkeys([p for p in target_pids if p > 0]))
        if not target_pids:
            self._clear_process_state()
            return True, "Bot process already stopped"

        try:
            with timed_event("launcher.proc.stop", target_count=len(target_pids)):
                for pid in target_pids:
                    try:
                        if os.name == "nt":
                            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
                        else:
                            os.kill(pid, 15)
                            time.sleep(0.3)
                            os.kill(pid, 9)
                    except ProcessLookupError:
                        pass

            self._clear_process_state()
            self._alive_cache = None
            log_event("launcher.proc.stopped", pids=",".join(str(pid) for pid in target_pids))
            return True, "Bot stopped"
        except Exception as exc:
            log_event("launcher.proc.stop_failed", level=logging.ERROR, error=str(exc))
            return False, f"Failed to stop bot: {exc}"

    def stop_all_activities(self) -> tuple[bool, str]:
        ok_rt, rt_msg = self.stop_bot()
        backend_pids = self._enumerate_backend_pids()
        worker_pids = self._enumerate_launcher_worker_pids()
        backend_stopped = 0
        backend_errors = 0
        worker_stopped = 0
        worker_errors = 0
        for pid in backend_pids:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
                else:
                    os.kill(pid, 15)
                    time.sleep(0.2)
                    os.kill(pid, 9)
                backend_stopped += 1
            except Exception:
                backend_errors += 1
        for pid in worker_pids:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
                else:
                    os.kill(pid, 15)
                    time.sleep(0.2)
                    os.kill(pid, 9)
                worker_stopped += 1
            except Exception:
                worker_errors += 1
        all_ok = ok_rt and backend_errors == 0 and worker_errors == 0
        summary = (
            f"{rt_msg}. Backend stopped={backend_stopped}. Workers stopped={worker_stopped}"
            if all_ok
            else f"{rt_msg}. Backend stop errors={backend_errors}. Worker stop errors={worker_errors}"
        )
        return all_ok, summary

    def pause_trading_safely(
        self,
        *,
        emergency_action: Callable[[], dict[str, Any]] | None = None,
        require_emergency_success: bool = True,
    ) -> tuple[bool, str]:
        emergency_result: dict[str, Any] = {"ok": False, "error": "No emergency action configured"}
        if emergency_action is not None:
            try:
                emergency_result = emergency_action()
            except Exception as exc:
                emergency_result = {"ok": False, "error": f"Emergency action failed: {exc}"}
        ok_stop, msg_stop = self.stop_bot()
        pause_state = {
            "paused_by_user": True,
            "timestamp": datetime.now().isoformat(),
            "runtime_stopped": bool(ok_stop),
            "emergency_result": emergency_result,
        }
        state_path = self.launcher_root / "state" / "paused_by_user.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(pause_state, indent=2), encoding="utf-8")
        emergency_ok = bool(emergency_result.get("ok"))
        ok = ok_stop and (emergency_ok if require_emergency_success else True)
        if ok:
            if require_emergency_success:
                return True, "Trading gepauzeerd: orders gesloten/geannuleerd en runtime gestopt."
            return True, "Training gepauzeerd: runtime stop bevestigd."
        return False, f"Pauze met waarschuwing: {msg_stop}; emergency={emergency_result.get('error', 'failed')}"
