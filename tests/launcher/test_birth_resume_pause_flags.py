"""Resume must clear pause flags and preserve checkpoint for user-paused runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_launcher.services import birth_runner_recovery as recovery_mod
from lumina_launcher.services import birth_runner_start as start_mod
from lumina_launcher.services.birth_service import BirthService


@pytest.mark.unit
def test_clear_birth_pause_flags_removes_stale_pause(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    primary = state / "first_boot_pause_requested"
    legacy = state / "birth_pause.flag"
    primary.write_text("abort:paused", encoding="utf-8")
    legacy.write_text("old", encoding="utf-8")

    class _Svc:
        workspace_root = tmp_path
        pause_flag_path = primary

    cleared = start_mod.clear_birth_pause_flags(_Svc())
    assert primary.exists() is False
    assert legacy.exists() is False
    assert len(cleared) >= 2


@pytest.mark.unit
def test_retry_birth_paused_preserves_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "stage": "paused",
                "phase": "paused",
                "user_initiated_stop": True,
                "message": "Birth Phase gepauzeerd door gebruiker.",
            }
        ),
        encoding="utf-8",
    )
    (state / "lumina_birth_checkpoint.json").write_text(
        json.dumps(
            {
                "phase": "curriculum_learning",
                "curriculum_stage": "stage2_range",
                "version": 3,
                "ppo_steps": 1000,
                "cumulative_trades": 712,
            }
        ),
        encoding="utf-8",
    )
    (state / "first_boot_pause_requested").write_text("abort:paused", encoding="utf-8")

    svc = BirthService()
    svc.configure_workspace(tmp_path)
    calls: list[dict[str, object]] = []

    def _fake_start(_svc: BirthService, **kwargs: object) -> dict[str, str]:
        calls.append(dict(kwargs))
        # Simulate real start_birth clearing flags
        start_mod.clear_birth_pause_flags(_svc)
        return {"status": "started", "message": "ok"}

    monkeypatch.setattr(start_mod, "start_birth", _fake_start)
    # Also patch recovery's import target used after local import
    monkeypatch.setattr(recovery_mod, "start_birth", _fake_start, raising=False)

    result = recovery_mod.retry_birth(svc, target_trades=25000, wipe=False)

    assert result["status"] == "started"
    assert calls, "start_birth must be invoked"
    assert calls[0].get("continue_training") is True
    assert calls[0].get("force") is False
    assert calls[0].get("reuse_data") is True
    # Checkpoint must NOT be wiped by clear_stale_for_certified_retry
    assert (tmp_path / "state" / "lumina_birth_checkpoint.json").is_file()
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_resume_birth_rejects_without_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    (tmp_path / "state").mkdir()
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    result = recovery_mod.resume_birth(svc, target_trades=25000)
    assert result["status"] == "rejected"
    assert "checkpoint" in str(result.get("message", "")).lower()
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_resume_birth_clears_pause_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_birth_checkpoint.json").write_text(
        json.dumps({"phase": "curriculum_learning", "version": 3}),
        encoding="utf-8",
    )
    pause = state / "first_boot_pause_requested"
    pause.write_text("abort:paused", encoding="utf-8")
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    calls: list[dict[str, object]] = []

    def _fake_start(_svc: BirthService, **kwargs: object) -> dict[str, str]:
        calls.append(dict(kwargs))
        return {"status": "started", "message": "ok"}

    monkeypatch.setattr(start_mod, "start_birth", _fake_start)

    result = recovery_mod.resume_birth(svc, target_trades=25000)
    assert result["status"] == "started"
    assert pause.exists() is False
    assert calls[0]["continue_training"] is True
    assert calls[0]["reuse_data"] is True
    BirthService._instance = None  # type: ignore[attr-defined]
