"""Validate BirthService delegation chain and public API stability (phase 2B)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from lumina_launcher.services import (
    birth_runner,
    birth_status_enricher,
    birth_status_mapper,
)
from lumina_launcher.services.birth_service import BirthService, birth_service, resolve_terminal_birth_status

_DELEGATING_METHODS: dict[str, str] = {
    "get_status": "birth_status_mapper.get_birth_status",
    "start_birth": "birth_runner.start_birth",
    "stop_birth": "birth_runner.stop_birth",
    "retry_birth": "birth_runner.retry_birth",
    "resume_stalled_stage": "birth_runner.resume_stalled_stage",
    "wipe_all_birth_data": "birth_runner.wipe_all_birth_data",
    "_enrich_birth_status": "birth_status_enricher.enrich_birth_status",
    "_sanitize_running_progress": "birth_status_mapper.sanitize_running_progress",
}


@pytest.mark.unit
def test_birth_service_singleton_configured() -> None:
    assert isinstance(birth_service, BirthService)
    assert birth_service.workspace_root.exists()


@pytest.mark.unit
def test_resolve_terminal_birth_status_reexported() -> None:
    assert resolve_terminal_birth_status({"phase": "stage_stalled"}) is not None


@pytest.mark.unit
@pytest.mark.parametrize("method_name,target", list(_DELEGATING_METHODS.items()))
def test_birth_service_methods_delegate(method_name: str, target: str) -> None:
    source = inspect.getsource(getattr(BirthService, method_name))
    module_hint = target.split(".", 1)[0]
    assert module_hint in source, (
        f"BirthService.{method_name} should delegate via {target}, got:\n{source}"
    )


@pytest.mark.unit
def test_birth_runner_submodules_exist() -> None:
    root = Path(__file__).resolve().parents[2] / "lumina_launcher" / "services"
    for name in (
        "birth_runner_lock.py",
        "birth_runner_start.py",
        "birth_runner_wipe.py",
        "birth_runner_recovery.py",
    ):
        assert (root / name).is_file(), f"missing runner submodule {name}"


@pytest.mark.unit
def test_birth_runner_facade_exports_start_birth() -> None:
    assert birth_runner.start_birth is not None
    assert birth_status_mapper.get_birth_status is not None
    assert birth_status_enricher.enrich_birth_status is not None