"""Fail-closed PPO binding for birth policy minting."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from lumina_core.birth.engine import BirthPhaseEngineV2


@pytest.mark.unit
def test_create_birth_policy_uses_injected_trainer(tmp_path: Path) -> None:
    sentinel = object()

    class Trainer:
        def create_fresh_birth_policy(self, *, allow_load_existing: bool = True, force_reinit: bool = False):
            return sentinel

    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=Trainer(),
        workspace_root=tmp_path,
    )
    assert engine._create_birth_policy(allow_load_existing=False) is sentinel


@pytest.mark.unit
def test_create_birth_policy_resolves_runtime_trainer_when_unbound(tmp_path: Path) -> None:
    sentinel = object()

    class Trainer:
        def create_fresh_birth_policy(self, *, allow_load_existing: bool = True, force_reinit: bool = False):
            return sentinel

    runtime = SimpleNamespace(ppo_trainer=Trainer())
    engine = BirthPhaseEngineV2(
        runtime=runtime,
        ppo_trainer=None,
        workspace_root=tmp_path,
    )
    assert engine.ppo_trainer is runtime.ppo_trainer
    assert engine._create_birth_policy(allow_load_existing=False) is sentinel


@pytest.mark.unit
def test_create_birth_policy_fail_closed_when_missing(tmp_path: Path) -> None:
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=None,
        workspace_root=tmp_path,
    )
    with pytest.raises(RuntimeError, match="create_fresh_birth_policy"):
        engine._create_birth_policy(allow_load_existing=False)


@pytest.mark.unit
def test_create_birth_policy_fail_closed_when_incompatible(tmp_path: Path) -> None:
    engine = BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),  # no create_fresh_birth_policy
        workspace_root=tmp_path,
    )
    with pytest.raises(RuntimeError, match="unbound or incompatible"):
        engine._create_birth_policy(allow_load_existing=False)


@pytest.mark.unit
def test_birth_runner_start_wires_ppo_trainer() -> None:
    """Source contract: launcher path must inject container.ppo_trainer (UI birth)."""
    source = Path("lumina_launcher/services/birth_runner_start.py").read_text(encoding="utf-8")
    assert "ppo_trainer=ppo_trainer" in source or "ppo_trainer=container.ppo_trainer" in source
    assert "create_fresh_birth_policy" in source
    assert "LuminaBirthEngine(" in source
