"""Occupancy exam settle + fencepost freeze (live 0.24996 chatter)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.foundation_occupancy_envelope import (
    EXAM_RECOVERY_SETTLE,
    exam_empty_settle_lo,
    occupancy_fencepost_blocks_expand,
    occupancy_under_exam_fencepost,
)
from lumina_core.birth.stage_sample_reset import reset_current_stage_sample
from lumina_core.birth.terminal_freeze import (
    build_terminal_freeze,
    freeze_attention_fields,
)


@pytest.mark.unit
def test_exam_empty_settle_is_two_pp() -> None:
    assert EXAM_RECOVERY_SETTLE == pytest.approx(0.02)
    assert exam_empty_settle_lo(0.25, 0.0) == pytest.approx(0.27)
    assert exam_empty_settle_lo(0.25, 0.04) == pytest.approx(0.29)


@pytest.mark.unit
def test_live_occupancy_24996_is_fencepost() -> None:
    assert occupancy_under_exam_fencepost(0.2499578) is True
    assert occupancy_under_exam_fencepost(0.2477) is True
    assert occupancy_under_exam_fencepost(0.25) is False
    assert occupancy_under_exam_fencepost(0.23) is False
    assert occupancy_fencepost_blocks_expand(
        occupancy=0.2499578,
        occupancy_exam_armed=False,
    ) is True
    assert occupancy_fencepost_blocks_expand(
        occupancy=0.2499578,
        occupancy_exam_armed=True,
    ) is False
    assert occupancy_fencepost_blocks_expand(
        occupancy=0.23998,
        occupancy_exam_armed=False,
    ) is True


@pytest.mark.unit
def test_freeze_fencepost_next_action_is_retry_stage_not_expand() -> None:
    freeze = build_terminal_freeze(
        reason="phoenix_cycle",
        curriculum_stage="stage3_mixed",
        stages_passed=["stage1_trend", "stage2_range"],
        swarm_rejected_no_lift=True,
        expansion_step=0,
        occupancy=0.2499578,
        occupancy_exam_armed=False,
    )
    assert freeze["next_action"] == "retry_stage"
    actions = freeze_attention_fields(freeze)["attention_recommended_actions"]
    assert actions[0] == "retry_stage"
    assert "expand_data" not in actions
    assert "wipe_and_retry" in actions


@pytest.mark.unit
def test_freeze_without_occupancy_still_offers_expand_when_ladder_open() -> None:
    freeze = build_terminal_freeze(
        reason="phoenix_cycle",
        curriculum_stage="stage3_mixed",
        stages_passed=["stage1_trend", "stage2_range"],
        swarm_rejected_no_lift=True,
        expansion_step=0,
    )
    assert freeze["next_action"] == "expand_data_or_accept_or_wipe"


@pytest.mark.unit
def test_reset_current_stage_sample_keeps_scope_zeros_trades() -> None:
    out = reset_current_stage_sample(
        {
            "stage_trades": 3075,
            "stage_wins": 712,
            "stage_range_flat_bars": 7404,
            "stage_range_total_signals": 29621,
            "occupancy": 0.24996,
            "occupancy_exam_armed": True,
            "swarm_rejected_no_lift": True,
            "curriculum_stage_scope": "stage3_mixed",
            "retries_this_stage": 1,
        }
    )
    assert out["stage_trades"] == 0
    assert out["stage_wins"] == 0
    assert out["stage_range_flat_bars"] == 0
    assert out["occupancy"] is None
    assert out["occupancy_exam_armed"] is False
    assert out["swarm_rejected_no_lift"] is False
    assert out["curriculum_stage_scope"] == "stage3_mixed"
    assert out["retries_this_stage"] == 2
    assert out["stage_sample_reset"] is True


@pytest.mark.unit
def test_retry_current_stage_resolves_freeze_and_starts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lumina_launcher.services.birth_runner_retry_stage import retry_current_stage

    progress = {
        "stage": "stage_stalled",
        "phase": "phoenix_cycle",
        "progress_pct": 48.2,
        "cumulative_trades": 3475,
        "target_trades": 25000,
        "ppo_steps": 77000,
        "birth_start_time": 1.0,
        "curriculum_stage": "stage3_mixed",
        "terminal_freeze": {
            "schema": "terminal_freeze_v1",
            "reason": "phoenix_cycle",
            "resolved": False,
            "next_action": "retry_stage_or_wipe",
        },
    }
    checkpoint = {
        "phase": "phoenix_cycle",
        "curriculum_stage": "stage3_mixed",
        "stages_passed": ["stage1_trend", "stage2_range"],
        "stage_metrics": {
            "stage_trades": 3075,
            "stage_wins": 712,
            "occupancy": 0.24996,
            "swarm_rejected_no_lift": True,
            "curriculum_stage_scope": "stage3_mixed",
        },
    }
    written: dict[str, object] = {}

    class _Svc:
        workspace_root = tmp_path

        def _load_progress(self) -> dict[str, object]:
            return dict(progress)

    monkeypatch.setattr(
        "lumina_core.birth.checkpoint.read_checkpoint_payload",
        lambda _root: dict(checkpoint),
    )

    def _write_ckpt(_root: object, payload: dict[str, object]) -> None:
        written["checkpoint"] = payload

    monkeypatch.setattr(
        "lumina_core.birth.checkpoint.write_checkpoint_payload",
        _write_ckpt,
    )
    monkeypatch.setattr(
        "lumina_core.birth.progress.write_birth_progress",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_recovery.is_stage_stalled_recovery_eligible",
        lambda _svc: True,
    )
    monkeypatch.setattr(
        "lumina_launcher.services.birth_runner_start.start_birth",
        lambda *_a, **_k: {"status": "started"},
    )
    result = retry_current_stage(_Svc(), target_trades=25000)
    assert result["status"] == "started"
    metrics = written["checkpoint"]["stage_metrics"]  # type: ignore[index]
    assert metrics["stage_trades"] == 0
    assert metrics["swarm_rejected_no_lift"] is False
    freeze = written["checkpoint"]["terminal_freeze"]  # type: ignore[index]
    assert freeze["resolved"] is True
    assert freeze["resolved_action"] == "retry_stage"
