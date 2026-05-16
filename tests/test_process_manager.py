"""
High-quality unit tests for ProcessManager.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lumina_launcher.core.process_manager import ProcessManager


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
    mock_popen.return_value = MagicMock(pid=4242)
    with patch.object(pm, "is_process_alive", return_value=False):
        success, _ = pm.start_bot(mode="sim_real_guard")
    assert success is True
    args, kwargs = mock_popen.call_args
    assert "--mode" in args[0]
    assert "sim_real_guard" in args[0]
    assert kwargs["cwd"] == str(root)
