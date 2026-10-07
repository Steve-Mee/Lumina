"""Console-free process probes. A pythonw engine must not flash a prompt."""

from __future__ import annotations

import os
from pathlib import Path

from lumina_core.process_probe import no_console, pid_is_alive, process_image_running

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pid_is_alive_sees_this_process_and_rejects_zero() -> None:
    assert pid_is_alive(0) is False
    assert pid_is_alive(-1) is False
    assert pid_is_alive(os.getpid()) is True


def test_missing_image_is_not_running() -> None:
    seen = process_image_running("lumina-no-such-image.exe")
    if os.name != "nt":
        assert seen is None
    else:
        assert seen is False


def test_no_console_flag_is_windows_only() -> None:
    flags = no_console()
    if os.name == "nt":
        assert flags["creationflags"]
    else:
        assert flags == {}


def test_hot_paths_do_not_spawn_a_visible_console() -> None:
    supervisor = _read("lumina_core/broker/ninjatrader/fabric_link_supervisor.py")
    history = _read("lumina_core/engine/market_data_history_fetch.py")
    charts = _read("lumina_core/engine/visualization_charts.py")
    window = _read("lumina_core/engine/visualization_charts_window.py")
    manager = _read("lumina_launcher/core/process_manager.py")
    monitoring = _read("lumina_os/api/monitoring.py")

    assert '["tasklist"' not in supervisor
    assert '["tasklist"' not in history
    assert "powershell" not in manager
    assert "powershell" not in monitoring
    assert '-topmost", True' not in charts
    assert '-topmost", True' not in window
    assert "LUMINA Live Trader Screen Share" in window
