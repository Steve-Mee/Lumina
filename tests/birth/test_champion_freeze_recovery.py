"""Track A: champion freeze blocks silent service recovery (accept/wipe only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from lumina_core.birth.starship_swarm_gates import (
    champion_freeze_blocks_recovery_payload,
    is_champion_freeze_active,
    should_hard_stop_training_after_swarm_reject,
)
from lumina_launcher.services.birth_runner_recovery import (
    champion_freeze_active_for_svc,
    expand_and_retry_stalled_stage,
    reject_if_champion_freeze,
    resume_birth,
    resume_stalled_stage,
)


@pytest.mark.unit
def test_champion_freeze_verification_report_frozen() -> None:
    from lumina_core.birth.starship_swarm_gates import (
        build_champion_freeze_verification_report,
    )

    report = build_champion_freeze_verification_report(
        progress={
            "swarm_rejected_no_lift": True,
            "needs_attention": True,
            "phase": "swarm_reject_hard_stop",
            "attention_recommended_actions": ["accept_champion", "wipe_and_retry"],
        }
    )
    assert report["schema"] == "champion_freeze_verification_v1"
    assert report["freeze_active"] is True
    assert report["ok"] is True
    assert report["policy"]["no_silent_train_after_no_lift"] is True
    assert "resume_stalled_stage" in report["operator_paths"]["blocked"]


@pytest.mark.unit
def test_champion_freeze_verification_report_clear() -> None:
    from lumina_core.birth.starship_swarm_gates import (
        build_champion_freeze_verification_report,
    )

    report = build_champion_freeze_verification_report(progress={})
    assert report["freeze_active"] is False
    assert report["ok"] is True


@pytest.mark.unit
def test_is_champion_freeze_active_reject_without_accept() -> None:
    assert is_champion_freeze_active(swarm_rejected_no_lift=True) is True
    assert (
        is_champion_freeze_active(
            swarm_rejected_no_lift=True,
            swarm_champion_accepted=True,
        )
        is False
    )
    assert is_champion_freeze_active() is False


@pytest.mark.unit
def test_is_champion_freeze_active_progress_dual_keys() -> None:
    assert is_champion_freeze_active(
        progress={"policy_swarm_rejected_no_lift": True},
    ) is True
    assert is_champion_freeze_active(
        progress={
            "swarm_rejected_no_lift": True,
            "policy_swarm_champion_accepted": True,
        },
    ) is False
    assert is_champion_freeze_active(
        progress={"swarm_champion_accepted": True},
        checkpoint_metrics={"swarm_rejected_no_lift": True},
    ) is False


@pytest.mark.unit
def test_is_champion_freeze_active_checkpoint_metrics_fallback() -> None:
    assert is_champion_freeze_active(
        progress={},
        checkpoint_metrics={"swarm_rejected_no_lift": True},
    ) is True


@pytest.mark.unit
def test_hard_stop_predicate_unchanged_with_retearnament() -> None:
    """Training hard-stop still requires re-tournament; recovery freeze does not."""
    class _S:
        rejected_no_lift = True
        champion_accepted = False

    assert not should_hard_stop_training_after_swarm_reject(
        swarm_state=_S(),
        host_rejected_no_lift=True,
        retearnament_used=False,
    )
    assert should_hard_stop_training_after_swarm_reject(
        swarm_state=_S(),
        host_rejected_no_lift=True,
        retearnament_used=True,
    )
    # Recovery freeze is active regardless of re-tournament flag.
    assert is_champion_freeze_active(swarm_rejected_no_lift=True) is True


@pytest.mark.unit
def test_champion_freeze_blocks_recovery_payload_shape() -> None:
    payload = champion_freeze_blocks_recovery_payload()
    assert payload["status"] == "rejected"
    assert payload["reason_code"] == "champion_freeze_blocks_recovery"
    assert "accept champion" in payload["message"].lower()


def _mock_svc_with_progress(progress: dict[str, Any], metrics: dict[str, Any] | None = None) -> MagicMock:
    svc = MagicMock()
    svc._load_progress.return_value = dict(progress)
    svc.workspace_root = Path(".")
    return svc


@pytest.mark.unit
def test_reject_if_champion_freeze_from_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _mock_svc_with_progress({"swarm_rejected_no_lift": True})
    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_recovery._checkpoint_stage_metrics",
        lambda _svc: {},
    )
    blocked = reject_if_champion_freeze(svc)
    assert blocked is not None
    assert blocked["status"] == "rejected"
    assert blocked["reason_code"] == "champion_freeze_blocks_recovery"


@pytest.mark.unit
def test_resume_stalled_stage_blocked_by_freeze(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = _mock_svc_with_progress(
        {
            "stage": "stage_stalled",
            "phase": "swarm_reject_hard_stop",
            "swarm_rejected_no_lift": True,
            "needs_attention": True,
            "retryable": True,
        }
    )
    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_recovery._checkpoint_stage_metrics",
        lambda _svc: {},
    )
    started: list[bool] = []

    def _no_start(*_a: Any, **_k: Any) -> dict[str, str]:
        started.append(True)
        return {"status": "started"}

    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_start.start_birth",
        _no_start,
    )
    result = resume_stalled_stage(svc)
    assert result["status"] == "rejected"
    assert result["reason_code"] == "champion_freeze_blocks_recovery"
    assert started == []


@pytest.mark.unit
def test_expand_blocked_by_freeze_explicit_resume_accepts_champion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Silent expand stays freeze-blocked; Continue-from-checkpoint accepts champion."""
    svc = _mock_svc_with_progress({"policy_swarm_rejected_no_lift": True})
    svc.checkpoint_file = MagicMock()
    svc.checkpoint_file.exists.return_value = True
    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_recovery._checkpoint_stage_metrics",
        lambda _svc: {},
    )
    expand_starts: list[bool] = []

    def _no_start(*_a: Any, **_k: Any) -> dict[str, str]:
        expand_starts.append(True)
        return {"status": "started"}

    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_start.start_birth",
        _no_start,
    )
    assert expand_and_retry_stalled_stage(svc)["status"] == "rejected"
    assert expand_starts == []

    accept_calls: list[dict[str, Any]] = []

    def _accept(_svc: Any, **kwargs: Any) -> dict[str, str]:
        accept_calls.append(dict(kwargs))
        return {"status": "started", "message": "champion accepted — continuing"}

    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_recovery.accept_champion_birth",
        _accept,
    )
    result = resume_birth(svc, target_trades=25000)
    assert result["status"] == "started"
    assert accept_calls, "explicit resume must accept frozen champion"
    assert accept_calls[0].get("start") is True
    assert accept_calls[0].get("source") == "resume_checkpoint"


@pytest.mark.unit
def test_resume_stalled_allowed_without_freeze(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = _mock_svc_with_progress(
        {
            "stage": "stage_stalled",
            "phase": "stage_stalled",
            "retryable": True,
        }
    )
    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_recovery._checkpoint_stage_metrics",
        lambda _svc: {},
    )
    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_recovery.is_stage_stalled_recovery_eligible",
        lambda _svc: True,
    )
    monkeypatch.setattr(
        "lumina_core.birth.checkpoint.reset_adaptation_budget_for_manual_resume",
        lambda _ws: None,
    )
    calls: list[bool] = []

    def _start(*_a: Any, **_k: Any) -> dict[str, str]:
        calls.append(True)
        return {"status": "started"}

    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_start.start_birth",
        _start,
    )
    result = resume_stalled_stage(svc)
    assert result["status"] == "started"
    assert calls == [True]


@pytest.mark.unit
def test_champion_freeze_active_for_svc_checkpoint_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = _mock_svc_with_progress({"stage": "stage_stalled"})
    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_recovery._checkpoint_stage_metrics",
        lambda _svc: {"swarm_rejected_no_lift": True},
    )
    assert champion_freeze_active_for_svc(svc) is True


@pytest.mark.unit
def test_accept_champion_resolves_terminal_freeze(tmp_path: Path) -> None:
    from lumina_core.birth.checkpoint import read_checkpoint_payload, write_checkpoint_payload
    from lumina_core.birth.terminal_freeze import (
        build_terminal_freeze,
        extract_terminal_freeze,
        freeze_blocks_curriculum_grind,
    )
    from lumina_launcher.services.birth_runner_recovery import accept_champion_birth

    freeze = build_terminal_freeze(
        reason="phoenix_cycle",
        curriculum_stage="stage1_trend",
        stages_passed=[],
        swarm_rejected_no_lift=True,
        next_action="accept_champion_or_wipe",
        stage_trades=1300,
        stage_wins=364,
    )
    assert freeze_blocks_curriculum_grind(freeze) is True
    write_checkpoint_payload(
        tmp_path,
        {
            "phase": "phoenix_cycle",
            "curriculum_stage": "stage1_trend",
            "stage_metrics": {"terminal_freeze": freeze, "stage_trades": 1300},
        },
    )
    svc = MagicMock()
    svc.workspace_root = tmp_path
    svc._load_progress.return_value = {
        "stage": "paused",
        "phase": "paused",
        "swarm_rejected_no_lift": True,
        "terminal_freeze": freeze,
        "curriculum_stage": "stage1_trend",
        "cumulative_trades": 1300,
        "target_trades": 25000,
    }
    svc.checkpoint_resumable.return_value = True
    result = accept_champion_birth(svc, target_trades=25000, start=False, source="test")
    assert result["status"] == "champion_accepted"
    payload = read_checkpoint_payload(tmp_path) or {}
    restored = extract_terminal_freeze(payload)
    assert restored is not None
    assert freeze_blocks_curriculum_grind(restored) is False
    assert restored.get("resolved_action") == "accept_champion"


@pytest.mark.unit
def test_explicit_resume_resolves_terminal_freeze_when_swarm_already_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lumina_core.birth.checkpoint import read_checkpoint_payload, write_checkpoint_payload
    from lumina_core.birth.terminal_freeze import (
        build_terminal_freeze,
        extract_terminal_freeze,
        freeze_blocks_curriculum_grind,
    )
    from lumina_launcher.services.birth_runner_recovery import resume_birth

    freeze = build_terminal_freeze(
        reason="phoenix_cycle",
        curriculum_stage="stage1_trend",
        stages_passed=[],
        swarm_rejected_no_lift=False,
        swarm_champion_accepted=True,
        next_action="accept_champion_or_wipe",
        stage_trades=1300,
        stage_wins=364,
    )
    write_checkpoint_payload(
        tmp_path,
        {
            "phase": "phoenix_cycle",
            "curriculum_stage": "stage1_trend",
            "stage_metrics": {
                "terminal_freeze": freeze,
                "swarm_champion_accepted": True,
            },
        },
    )
    svc = MagicMock()
    svc.workspace_root = tmp_path
    svc.checkpoint_file = tmp_path / "state" / "lumina_birth_checkpoint.json"
    svc._load_progress.return_value = {
        "stage": "paused",
        "phase": "paused",
        "swarm_rejected_no_lift": False,
        "swarm_champion_accepted": True,
        "terminal_freeze": freeze,
        "curriculum_stage": "stage1_trend",
    }
    started: list[bool] = []

    def _start(*_a: Any, **_k: Any) -> dict[str, str]:
        started.append(True)
        payload = read_checkpoint_payload(tmp_path) or {}
        restored = extract_terminal_freeze(payload)
        assert restored is not None
        assert freeze_blocks_curriculum_grind(restored) is False
        return {"status": "started"}

    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_start.clear_birth_pause_flags",
        lambda _svc: None,
    )
    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_start.start_birth",
        _start,
    )
    result = resume_birth(svc, target_trades=25000)
    assert result["status"] == "started"
    assert started == [True]
