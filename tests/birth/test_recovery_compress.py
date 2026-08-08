"""H6: compressed recovery ladder — single active surface, theater flags."""

from __future__ import annotations

from lumina_core.birth.recovery_compress import compress_recovery, recovery_from_progress


def test_idle_when_no_recovery_flags() -> None:
    out = compress_recovery(phase="curriculum_learning")
    assert out["schema"] == "recovery_compress_v1"
    assert out["active"] == "idle"
    assert out["theater"] is False
    assert out["next_action"] == "none"


def test_priority_terminal_beats_plateau() -> None:
    out = compress_recovery(
        phase="stage_stalled",
        plateau_active=True,
        terminal_stall_reason="plateau_evolution_exhausted",
        remediation_exhausted=True,
    )
    assert out["active"] == "terminal_stall"
    assert "plateau" in out["layers"]
    assert out["productive"] is False


def test_swarm_block_before_phoenix() -> None:
    out = compress_recovery(
        phase="phoenix_cycle",
        swarm_rejected_no_lift=True,
        phoenix_enabled=True,
        strong_recovery_mode=True,
    )
    assert out["active"] == "swarm_block"
    # T11: freeze + attention → accept/wipe sacred path
    assert out["next_action"] == "accept_champion_or_wipe"
    assert out["flags"].get("champion_freeze") is True


def test_hard_stop_phase_is_swarm_block_not_ladder_theater() -> None:
    out = compress_recovery(
        phase="swarm_reject_hard_stop",
        swarm_rejected_no_lift=True,
        needs_attention=True,
        plateau_active=True,
        plateau_full_recovery_cycles=2,
        adaptation_tier=3,
        wall_behavior="adaptive",
    )
    # needs_attention has higher priority than swarm_block
    assert out["active"] in ("needs_attention", "swarm_block")
    assert out["next_action"] == "accept_champion_or_wipe"
    assert "adaptation" not in out["layers"]  # ladder theater suppressed under freeze
    assert out["flags"].get("champion_freeze") is True


def test_recovery_theater_ops_report() -> None:
    from lumina_core.birth.recovery_compress import build_recovery_theater_ops_report

    report = build_recovery_theater_ops_report(
        {
            "phase": "swarm_reject_hard_stop",
            "swarm_rejected_no_lift": True,
            "needs_attention": True,
        }
    )
    assert report["schema"] == "recovery_theater_ops_v1"
    assert report["ok"] is True
    assert report["next_action"] == "accept_champion_or_wipe"


def test_theater_on_multi_cycle_plateau() -> None:
    out = compress_recovery(
        phase="curriculum_learning",
        plateau_active=True,
        plateau_full_recovery_cycles=3,
        plateau_noop_count=1,
    )
    assert out["active"] == "plateau"
    assert out["theater"] is True
    assert "plateau_multi_cycle_no_clear_exit" in out["theater_reasons"]
    assert out["productive"] is False
    assert out["next_action"] == "stop_auto_recovery_expand_or_manual"


def test_productive_adaptation_ladder() -> None:
    out = compress_recovery(
        phase="curriculum_learning",
        wall_behavior="adaptive",
        adaptation_tier=1,
        max_adaptation_tiers=4,
        retries_this_stage=1,
        max_stage_retries=5,
    )
    assert out["active"] == "adaptation"
    assert out["theater"] is False
    assert out["productive"] is True
    assert out["next_action"] == "let_engine_recover"


def test_pass_metric_not_restored_is_theater_not_productive() -> None:
    """Attempt counters without pass-metric restore = recovery theater."""
    out = compress_recovery(
        phase="curriculum_learning",
        plateau_active=True,
        plateau_evolution_step=4,
        autonomous_recovery_successes=3,
        stage_blocker_metric="position_flat",
        volume_gate_status="PASSED",
    )
    assert out["active"] == "plateau"
    assert out["theater"] is True
    assert "pass_metric_not_restored" in out["theater_reasons"]
    assert out["productive"] is False


def test_recovery_from_progress_roundtrip() -> None:
    progress = {
        "phase": "stage_stalled",
        "plateau_active": True,
        "plateau_full_recovery_cycles": 2,
        "adaptation_tier": 2,
        "wall_behavior": "adaptive",
        "needs_attention": False,
        "trade_budget_remaining": 5000,
        "stall_remediation_step": 2,
        "stall_remediation_cycle": 1,
        "stall_remediation_max_steps": 4,
        "stall_remediation_max_cycles": 2,
    }
    out = recovery_from_progress(progress)
    assert out["schema"] == "recovery_compress_v1"
    assert out["active"] in ("plateau", "stall_remediation", "adaptation", "terminal_stall")
    # already compressed reused
    progress["recovery"] = out
    again = recovery_from_progress(progress)
    assert again is out or again["active"] == out["active"]


def test_certificate_surface() -> None:
    out = compress_recovery(phase="certificate_failed")
    assert out["active"] == "certificate"
    assert out["next_action"] == "continue_learning_or_wipe"
