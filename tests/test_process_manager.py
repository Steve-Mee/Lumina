"""
High-quality unit tests for ProcessManager.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lumina_launcher.core.process_manager import ProcessManager, resolve_runtime_python


@pytest.fixture
def temp_dirs():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        runtime_entry = root / "runtime_entrypoint.py"
        runtime_entry.touch()
        yield root, runtime_entry


def test_process_manager_initialization(temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, runtime)
    assert pm.launcher_root == root
    assert pm.runtime_entry == runtime


def test_pid_is_alive_false_for_zero():
    pm = ProcessManager(Path("."), Path("dummy.py"))
    assert pm._pid_is_alive(0) is False
    assert pm._pid_is_alive(-5) is False


@patch("lumina_launcher.core.process_manager.os.name", "nt")
@patch("lumina_launcher.core.process_manager.subprocess.run")
def test_pid_is_alive_windows(mock_run, temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, runtime)

    mock_run.return_value = MagicMock(stdout="1234\n")
    assert pm._pid_is_alive(1234) is True

    mock_run.return_value = MagicMock(stdout="")
    assert pm._pid_is_alive(9999) is False


def test_is_process_alive_no_state(temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, runtime)

    # Forceer dat er geen extern proces gevonden wordt
    with patch.object(pm, "_find_external_runtime_pid", return_value=0):
        assert pm.is_process_alive() is False


def test_is_process_alive_clears_stale_state_file(temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, runtime)
    pm._save_process_state(44320, ["python", "runtime_entrypoint.py", "--mode", "auto"])
    assert pm.process_state_path.exists()

    with patch.object(pm, "_pid_is_alive", return_value=False):
        with patch.object(pm, "_find_external_runtime_pid", return_value=0):
            assert pm.is_process_alive() is False
    assert not pm.process_state_path.exists()


def test_start_bot_entry_not_found(temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, Path("nonexistent.py"))
    success, msg = pm.start_bot()
    assert success is False
    assert "not found" in msg.lower()


def test_stop_bot_no_process(temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, runtime)
    success, msg = pm.stop_bot()
    assert success is True
    assert "already stopped" in msg.lower() or "stopped" in msg.lower()


@patch("lumina_launcher.core.process_manager.subprocess.Popen")
def test_start_bot_uses_passed_mode(mock_popen, temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, runtime)
    proc = MagicMock(pid=4242)
    proc.poll.return_value = None
    mock_popen.return_value = proc
    with patch("lumina_launcher.core.process_manager.resolve_runtime_python", return_value="python"):
        with patch.object(pm, "_pid_is_alive", return_value=True):
            with patch.object(pm, "is_process_alive", return_value=False):
                with patch("lumina_launcher.core.process_manager.time.sleep", return_value=None):
                    success, _ = pm.start_bot(mode="sim_real_guard")
    assert success is True
    args, kwargs = mock_popen.call_args
    assert "--mode" in args[0]
    assert "sim_real_guard" in args[0]
    assert kwargs["cwd"] == str(root)


def test_resolve_runtime_python_prefers_sys_executable(temp_dirs):
    root, _ = temp_dirs
    with patch("lumina_launcher.core.process_manager.os.getenv", return_value=""):
        with patch("lumina_launcher.core.process_manager._python_has_module") as mock_has_module:
            def _check(candidate: str, module_name: str, *, cwd: Path) -> bool:
                return candidate == "C:/venv/python.exe" and module_name == "dotenv"

            mock_has_module.side_effect = _check
            with patch("lumina_launcher.core.process_manager.sys.executable", "C:/venv/python.exe"):
                resolved = resolve_runtime_python(root)
    assert resolved == "C:/venv/python.exe"


@patch("lumina_launcher.core.process_manager.subprocess.Popen")
def test_start_bot_fails_when_process_exits_immediately(mock_popen, temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, runtime)
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "launcher_runtime_stderr.log").write_text("ModuleNotFoundError: No module named 'dotenv'\n", encoding="utf-8")
    proc = MagicMock(pid=9876)
    proc.poll.return_value = 1
    mock_popen.return_value = proc
    with patch("lumina_launcher.core.process_manager.resolve_runtime_python", return_value="python"):
        with patch.object(pm, "is_process_alive", return_value=False):
            with patch("lumina_launcher.core.process_manager.time.sleep", return_value=None):
                success, msg = pm.start_bot(mode="auto")
    assert success is False
    assert "stopped immediately" in msg.lower()
    assert "dotenv" in msg
    assert not pm.process_state_path.exists()


@patch("lumina_launcher.core.process_manager.os.name", "nt")
@patch("lumina_launcher.core.process_manager.subprocess.run")
def test_stop_all_activities_stops_backend_and_runtime(mock_run, temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, runtime)
    with patch.object(pm, "stop_bot", return_value=(True, "Bot stopped")):
        with patch.object(pm, "_enumerate_backend_pids", return_value=[123, 456]):
            with patch.object(pm, "_enumerate_launcher_worker_pids", return_value=[]):
                ok, msg = pm.stop_all_activities()
    assert ok is True
    assert "Backend stopped=2" in msg
    assert mock_run.call_count >= 2


def test_pause_trading_safely_writes_marker_and_stops(temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, runtime)
    with patch.object(pm, "stop_bot", return_value=(True, "Bot stopped")):
        ok, msg = pm.pause_trading_safely(emergency_action=lambda: {"ok": True})
    marker = root / "state" / "paused_by_user.json"
    assert marker.exists()
    assert ok is True
    assert "orders gesloten/geannuleerd" in msg.lower()


def test_pause_trading_safely_reports_emergency_failure(temp_dirs):
    root, runtime = temp_dirs
    pm = ProcessManager(root, runtime)
    with patch.object(pm, "stop_bot", return_value=(True, "Bot stopped")):
        ok, msg = pm.pause_trading_safely(emergency_action=lambda: {"ok": False, "error": "unsupported"})
    assert ok is False
    assert "unsupported" in msg
