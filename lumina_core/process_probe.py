"""Process checks that do not open a console window.

The SIM engine runs under pythonw, which has no console. ``tasklist.exe`` and
``powershell.exe`` are console programs, so each call allocates a new black
prompt and takes the keyboard. The Fabric health loop does that about every
two seconds while a session is up.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any


def no_console() -> dict[str, Any]:
    """Creation flags that keep a child console program invisible on Windows."""
    if os.name != "nt":
        return {}
    return {"creationflags": subprocess.CREATE_NO_WINDOW}


def pid_is_alive(pid: int) -> bool:
    """True when the PID is a live process. Never spawns a shell."""
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information, False, int(pid)
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def process_image_running(*names: str) -> bool | None:
    """True or False when the image probe worked. None when it could not run.

    A Fabric reconnect treats None as still alive so a probe glitch does not
    look like NinjaTrader exiting. A history fetch treats None as not seen.
    """
    wanted = {str(name).strip().lower() for name in names if str(name).strip()}
    if not wanted:
        return False
    if os.name != "nt":
        return None
    try:
        import psutil
    except Exception:
        return None
    try:
        for proc in psutil.process_iter(["name"]):
            image = str(proc.info.get("name") or "").lower()
            if image in wanted:
                return True
        return False
    except Exception:
        return None
