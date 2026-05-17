"""BirthService workspace resolution — must not depend on process cwd."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_launcher.services.birth_service import (
    BirthService,
    configure_birth_workspace,
    resolve_birth_workspace_root,
)


@pytest.mark.unit
def test_resolve_birth_workspace_root_defaults_to_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUMINA_WORKSPACE_ROOT", raising=False)
    root = resolve_birth_workspace_root()
    assert (root / "lumina_launcher").is_dir()
    assert root == resolve_birth_workspace_root(None)


@pytest.mark.unit
def test_resolve_birth_workspace_root_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = tmp_path / "custom_ws"
    ws.mkdir()
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(ws))
    assert resolve_birth_workspace_root() == ws.resolve()


@pytest.mark.unit
def test_configure_birth_workspace_updates_paths(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    ws = tmp_path / "repo"
    (ws / "state").mkdir(parents=True)
    svc.configure_workspace(ws)
    assert svc.workspace_root == ws.resolve()
    assert svc.progress_file == ws / "state" / "lumina_birth_progress.json"
    assert svc.policy_path == ws / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_artifacts_ok_requires_flag_and_policy(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    assert svc.artifacts_ok() is False
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    svc.completed_flag.write_text("done", encoding="utf-8")
    assert svc.artifacts_ok() is False
    policy_dir = tmp_path / "lumina_agents" / "ppo"
    policy_dir.mkdir(parents=True)
    (policy_dir / "lumina_ppo_policy.zip").write_bytes(b"zip")
    assert svc.artifacts_ok() is True
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_configure_birth_workspace_module_helper(tmp_path: Path) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    out = configure_birth_workspace(tmp_path)
    assert out == tmp_path.resolve()
    BirthService._instance = None  # type: ignore[attr-defined]
