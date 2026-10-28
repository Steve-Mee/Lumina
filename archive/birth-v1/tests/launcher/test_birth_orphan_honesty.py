"""Orphan reconcile must not impersonate a user stop or clobber a terminal freeze."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.birth.terminal_freeze import TERMINAL_FREEZE_SCHEMA
from lumina_launcher.services.birth_runner_lock import (
    reconcile_orphaned_birth_progress,
    write_start_inflight,
)
from lumina_launcher.services.birth_service import BirthService


def _write_progress(root: Path, payload: dict) -> None:
    path = root / "state" / "lumina_birth_progress.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


@pytest.mark.unit
def test_reconcile_skips_unresolved_terminal_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    freeze = {
        "schema": TERMINAL_FREEZE_SCHEMA,
        "reason": "phoenix_cycle",
        "curriculum_stage": "stage5_probe_handoff",
        "stages_passed": ["stage1_trend", "stage2_range"],
        "next_action": "expand_data_or_wipe_birth",
        "resolved": False,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
    }
    svc = BirthService()
    monkeypatch.setattr(svc, "_maybe_execute_autonomous_recovery", lambda: None)
    monkeypatch.setattr(svc, "_maybe_auto_resume_stalled_birth", lambda: None)
    svc.configure_workspace(tmp_path)
    _write_progress(
        tmp_path,
        {
            "stage": "stage_stalled",
            "phase": "stage_stalled",
            "terminal_stall_reason": "phoenix_cycle",
            "terminal_freeze": freeze,
            "trades_done": 2155,
            "autonomous_recovery_pending": True,
        },
    )
    assert reconcile_orphaned_birth_progress(svc) is False
    kept = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert kept.get("stage") == "stage_stalled"
    assert kept.get("user_initiated_stop") is not True
    assert kept.get("terminal_freeze", {}).get("reason") == "phoenix_cycle"
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_reconcile_skips_start_inflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    monkeypatch.setattr(svc, "_maybe_execute_autonomous_recovery", lambda: None)
    monkeypatch.setattr(svc, "_maybe_auto_resume_stalled_birth", lambda: None)
    svc.configure_workspace(tmp_path)
    _write_progress(
        tmp_path,
        {
            "stage": "pipeline_boot",
            "phase": "holdout_preflight",
            "trades_done": 0,
        },
    )
    write_start_inflight(svc)
    assert reconcile_orphaned_birth_progress(svc) is False
    kept = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert kept.get("stage") == "pipeline_boot"
    assert kept.get("user_initiated_stop") is not True
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_execute_autonomous_recovery_respects_user_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    monkeypatch.setattr(svc, "_maybe_execute_autonomous_recovery", lambda: None)
    monkeypatch.setattr(svc, "_maybe_auto_resume_stalled_birth", lambda: None)
    svc.configure_workspace(tmp_path)
    _write_progress(
        tmp_path,
        {
            "stage": "paused",
            "phase": "paused",
            "user_initiated_stop": True,
            "autonomous_recovery_pending": True,
            "recommended_recovery_action": "resume_stalled_stage",
            "terminal_stall_reason": "phoenix_cycle",
        },
    )

    def _boom(*_a: object, **_k: object) -> dict:
        raise AssertionError("start_birth must not run after operator stop")

    monkeypatch.setattr(svc, "resume_stalled_stage", _boom)
    result = svc.execute_autonomous_recovery()
    assert result.get("status") == "rejected"
    assert "operator stop" in str(result.get("message") or "").lower()
    BirthService._instance = None  # type: ignore[attr-defined]
