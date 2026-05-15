"""
LUMINA Core - Process Manager
Handles starting, stopping, and monitoring the Lumina runtime process.
Extracted from the original God file (lumina_launcher.py).
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil  # type: ignore[import]

logger = logging.getLogger(__name__)


class ProcessManager:
    def __init__(self, launcher_root: Path, runtime_entry: Path):
        self.launcher_root = launcher_root
        self.runtime_entry = runtime_entry
        self.process_state_path = launcher_root / "state" / "launcher_bot_process.json"

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

    def is_process_alive(self) -> bool:
        state = self._load_process_state()
        pid = int(state.get("pid", 0) or 0)
        if pid > 0 and self._pid_is_alive(pid):
            return True
        external = self._find_external_runtime_pid()
        return external > 0 and self._pid_is_alive(external)

    def start_bot(self) -> tuple[bool, str]:
        if not self.runtime_entry.exists():
            return False, f"Runtime entry not found: {self.runtime_entry}"
        if self.is_process_alive():
            return True, "Bot is already running"

        command = [os.getenv("LUMINA_PYTHON", "python"), str(self.runtime_entry), "--mode", "auto"]
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        try:
            proc = subprocess.Popen(
                command,
                cwd=str(self.launcher_root),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._save_process_state(proc.pid, command)
            return True, f"Bot started (pid={proc.pid})"
        except FileNotFoundError:
            return False, "Python interpreter not found. Check LUMINA_PYTHON env var."
        except Exception as exc:
            return False, f"Failed to start bot: {exc}"

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
            return True, "Bot stopped"
        except Exception as exc:
            return False, f"Failed to stop bot: {exc}"
