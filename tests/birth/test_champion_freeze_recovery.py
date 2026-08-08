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
def test_expand_and_resume_birth_blocked_by_freeze(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = _mock_svc_with_progress({"policy_swarm_rejected_no_lift": True})
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
    assert expand_and_retry_stalled_stage(svc)["status"] == "rejected"
    assert resume_birth(svc)["status"] == "rejected"
    assert started == []


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
