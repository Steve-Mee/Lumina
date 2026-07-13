"""Daemon SIM/Paper loop CLI tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lumina_launcher.runtime.spawn import SpawnResult, build_runtime_command, save_process_state, start_runtime_daemon


@pytest.mark.unit
def test_build_runtime_command_includes_mode() -> None:
    root = Path(__file__).resolve().parents[1]
    cmd = build_runtime_command(root, Path("lumina_core/engine/runtime_entrypoint.py"), "paper")
    assert "--mode" in cmd
    assert "paper" in cmd
    assert "--headless" not in cmd


@pytest.mark.unit
def test_process_state_includes_mode(tmp_path: Path) -> None:
    save_process_state(
        tmp_path,
        pid=12345,
        command=["python", "runtime_entrypoint.py", "--mode", "sim"],
        mode="sim",
    )
    payload = json.loads((tmp_path / "state" / "launcher_bot_process.json").read_text(encoding="utf-8"))
    assert payload["mode"] == "sim"
    assert payload["pid"] == 12345


@pytest.mark.unit
def test_loop_daemon_dispatch_prints_pid(capsys: pytest.CaptureFixture[str]) -> None:
    from lumina_launcher.cli import dispatch

    with patch.object(dispatch, "run_loop_daemon", return_value=0) as mock_run:
        code = dispatch.main(["--mode", "sim"])
    assert code == 0
    mock_run.assert_called_once_with("sim", extra_argv=[])


@pytest.mark.unit
def test_loop_daemon_module_starts_engine(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from lumina_launcher.runtime import loop

    fake = SpawnResult(True, 4242, "sim", ["python", "rt.py"], "Engine started")
    with patch.object(loop, "repo_root", return_value=tmp_path):
        with patch.object(loop, "start_runtime_daemon", return_value=fake):
            code = loop.run_loop_daemon("sim")
    assert code == 0
    captured = capsys.readouterr()
    assert "pid=4242" in captured.out


@pytest.mark.unit
def test_real_mode_daemon_refused_without_real_safe() -> None:
    root = Path(__file__).resolve().parents[1]
    result = start_runtime_daemon(root, Path("lumina_core/engine/runtime_entrypoint.py"), "real")
    assert result.ok is False
    assert "real-safe" in result.message.lower()
