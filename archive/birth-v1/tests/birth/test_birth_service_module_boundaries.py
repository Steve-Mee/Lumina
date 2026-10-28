"""Validate BirthService delegation chain and public API stability (phase 2B)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from lumina_launcher.services import birth_runner_start, birth_status_enricher, birth_status_mapper
from lumina_launcher.services.birth_service import BirthService, birth_service, resolve_terminal_birth_status

_DELEGATING_METHODS: dict[str, str] = {
    "get_status": "birth_status_mapper.get_birth_status",
    "start_birth": "birth_runner_start.start_birth",
    "stop_birth": "birth_runner_start.stop_birth",
    "retry_birth": "birth_runner_recovery.retry_birth",
    "resume_stalled_stage": "birth_runner_recovery.resume_stalled_stage",
    "wipe_all_birth_data": "birth_runner_wipe.wipe_all_birth_data",
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
def test_resolve_terminal_birth_status_error_phase() -> None:
    status, message = resolve_terminal_birth_status(
        {
            "stage": "error",
            "phase": "error",
            "last_error": "got multiple values for keyword argument 'curriculum_stage'",
            "message": "Birth failed",
        }
    )
    assert status == "error"
    assert "curriculum_stage" in message


@pytest.mark.unit
def test_resolve_terminal_birth_status_prefers_freeze_message_over_hollow_pass_reason() -> None:
    status, message = resolve_terminal_birth_status(
        {
            "stage": "stage_stalled",
            "phase": "stage_stalled",
            "pass_reason": "foundation_fail:median_loss_r=None missing_or_gt_1.5;replay_cap trades=2331 days=0",
            "message": "Terminal freeze: phoenix_cycle — Twin/operator next_action=accept_champion_or_wipe",
            "terminal_freeze": {
                "schema": "terminal_freeze_v1",
                "reason": "phoenix_cycle",
                "resolved": False,
                "next_action": "accept_champion_or_wipe",
            },
        }
    )
    assert status == "stage_stalled"
    assert "phoenix_cycle" in message
    assert "median_loss_r=None" not in message


@pytest.mark.unit
@pytest.mark.parametrize("method_name,target", list(_DELEGATING_METHODS.items()))
def test_birth_service_methods_delegate(method_name: str, target: str) -> None:
    source = inspect.getsource(getattr(BirthService, method_name))
    func_name = target.rsplit(".", 1)[-1]
    assert func_name in source, (
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
def test_birth_runner_submodules_export_start_birth() -> None:
    assert birth_runner_start.start_birth is not None
    assert birth_status_mapper.get_birth_status is not None
    assert birth_status_enricher.enrich_birth_status is not None
