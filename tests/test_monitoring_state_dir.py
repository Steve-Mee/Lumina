"""Workspace-aware monitoring state directory resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core import logging_utils


@pytest.mark.unit
def test_resolve_monitoring_state_dir_honors_workspace_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = tmp_path / "repo"
    (ws / "state").mkdir(parents=True)
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(ws))
    assert logging_utils.resolve_monitoring_state_dir() == (ws / "state").resolve()
