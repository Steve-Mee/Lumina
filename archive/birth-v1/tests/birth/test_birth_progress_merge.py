"""Tests for birth progress extra merge (PEP 448 duplicate kwargs guard)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.progress import merge_birth_progress_extra, write_birth_progress


@pytest.mark.unit
def test_write_birth_progress_refreshes_session_start_on_restart(tmp_path: Path) -> None:
    """Regression: SCORECARD_PRESERVE_KEYS used to clobber birth_start_time with prev.

    UI showed a stale 'Session start' after wipe/restart (e.g. hours-old clock).
    """
    old_start = 1_700_000_000.0
    write_birth_progress(
        tmp_path,
        stage="history_unavailable",
        phase="loading_history_failed",
        message="old failure",
        progress_pct=100.0,
        birth_start_time=old_start,
        needs_attention=True,
        attention_reason_code="history_unavailable",
        attention_summary="Geen historische data beschikbaar.",
    )
    new_start = old_start + 86_400.0
    write_birth_progress(
        tmp_path,
        stage="loading_data",
        phase="loading_history",
        message="Historische data laden…",
        progress_pct=8.0,
        birth_start_time=new_start,
    )
    payload = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert float(payload["birth_start_time"]) == new_start
    assert float(payload["birth_start_time"]) != old_start
    # Stale attention from the previous failed session must not stick.
    assert payload.get("needs_attention") is not True
    assert payload.get("attention_reason_code") in (None, "", False)


@pytest.mark.unit
def test_write_birth_progress_new_session_drops_freeze_retryable(tmp_path: Path) -> None:
    write_birth_progress(
        tmp_path,
        stage="stage_stalled",
        phase="stage_stalled",
        message="old freeze",
        progress_pct=27.0,
        birth_start_time=1_700_000_000.0,
        retryable=False,
        auto_recovery_active=True,
        is_advancing=True,
        terminal_stall_reason="phoenix_cycle",
        swarm_rejected_no_lift=True,
    )
    write_birth_progress(
        tmp_path,
        stage="loading_data",
        phase="loading_history",
        message="Historische data laden…",
        progress_pct=8.0,
        birth_start_time=1_700_086_400.0,
    )
    payload = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert payload.get("retryable") is not False
    assert payload.get("auto_recovery_active") is not True
    assert payload.get("terminal_stall_reason") in (None, "")
    assert payload.get("swarm_rejected_no_lift") is not True


@pytest.mark.unit
def test_write_birth_progress_mirrors_existing_first_boot(tmp_path: Path) -> None:
    boot = tmp_path / "state" / "first_boot_progress.json"
    boot.parent.mkdir(parents=True, exist_ok=True)
    boot.write_text('{"stage": "paused", "user_initiated_stop": true}', encoding="utf-8")
    write_birth_progress(
        tmp_path,
        stage="loading_data",
        phase="ticks_ready",
        message="Checkpoint hervat",
        progress_pct=24.0,
        cumulative_trades=2155,
        ppo_steps=36500,
        birth_start_time=1_700_000_100.0,
        user_initiated_stop=False,
    )
    canonical = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    legacy = json.loads(boot.read_text(encoding="utf-8"))
    assert canonical == legacy
    assert legacy.get("user_initiated_stop") is False
    assert legacy.get("stage") == "loading_data"


@pytest.mark.unit
def test_write_birth_progress_preserves_session_start_within_same_run(tmp_path: Path) -> None:
    """Mid-run writes that omit birth_start_time keep the session clock."""
    start = 1_710_000_000.0
    write_birth_progress(
        tmp_path,
        stage="loading_data",
        phase="loading_history",
        message="start",
        progress_pct=5.0,
        birth_start_time=start,
    )
    write_birth_progress(
        tmp_path,
        stage="loading_data",
        phase="enriching_news",
        message="news",
        progress_pct=20.0,
        # birth_start_time omitted (0) — resume preserve path
    )
    payload = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert float(payload["birth_start_time"]) == start


@pytest.mark.unit
def test_merge_birth_progress_extra_last_wins() -> None:
    scorecard = {"constitution_violations": 2, "stage_wins": 10}
    constitution_fields = {
        "constitution_violations": 5,
        "constitution_violations_session": 2,
        "constitution_violations_cumulative": 5,
    }
    merged = merge_birth_progress_extra(scorecard, constitution_fields)
    assert merged["constitution_violations"] == 5
    assert merged["constitution_violations_session"] == 2
    assert merged["constitution_violations_cumulative"] == 5
    assert merged["stage_wins"] == 10


@pytest.mark.unit
def test_write_birth_progress_accepts_merged_scorecard_and_constitution(
    tmp_path: Path,
) -> None:
    """Regression: dual ** unpack of constitution_violations raised TypeError (PEP 448)."""
    scorecard = {"constitution_violations": 0, "stage_wins": 0, "stage_winrate": 0.0}
    constitution_fields = {
        "constitution_violations": 0,
        "constitution_violations_session": 0,
        "constitution_violations_cumulative": 0,
    }
    merged = merge_birth_progress_extra(scorecard, constitution_fields)
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="curriculum_learning",
        message="Curriculum stage1_trend: 10 / 500 trades",
        progress_pct=30.0,
        cumulative_trades=10,
        target_trades=5000,
        **merged,
    )
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    assert progress_path.is_file()
    text = progress_path.read_text(encoding="utf-8")
    assert "constitution_violations" in text
    assert "constitution_violations_session" in text
    assert "constitution_violations_cumulative" in text


@pytest.mark.unit
def test_dual_star_unpack_raises_without_merge(tmp_path: Path) -> None:
    scorecard = {"constitution_violations": 0}
    constitution_fields = {"constitution_violations": 0, "constitution_violations_session": 0}
    with pytest.raises(TypeError, match="multiple values for keyword argument"):
        write_birth_progress(
            tmp_path,
            stage="training_running",
            phase="curriculum_learning",
            message="test",
            progress_pct=1.0,
            **scorecard,
            **constitution_fields,
        )


@pytest.mark.unit
def test_terminal_stall_merge_survives_phoenix_curriculum_stage(tmp_path: Path) -> None:
    """Regression: phoenix autonomy_metrics.curriculum_stage collided with stall kwargs."""
    autonomy_extra = {
        "curriculum_stage": "stage1_trend",
        "phoenix_novelty": "expand_data",
        "autonomous_recovery_count": 1,
    }
    budget_fields = {"terminal_stall_reason": "plateau_evolution_exhausted"}
    constitution_fields = {
        "constitution_violations": 0,
        "constitution_violations_session": 0,
        "constitution_violations_cumulative": 0,
    }
    stall_fields = {
        "curriculum_stage": "stage1_trend",
        "stages_passed": [],
        "stage_blocker_metric": "winrate",
        "stage_blocker_value": 0.368,
        "pass_reason": "winrate 36.8% < 45%",
        "retryable": False,
        "needs_attention": True,
        "provisional_graduation": False,
        "graduation_tier": "strict",
        "oos_proxy_winrate": None,
    }
    merged = merge_birth_progress_extra(
        budget_fields,
        constitution_fields,
        autonomy_extra,
        stall_fields,
    )
    write_birth_progress(
        tmp_path,
        stage="stage_stalled",
        phase="stage_stalled",
        message="Stage stage1_trend stalled: winrate",
        progress_pct=27.0,
        cumulative_trades=2705,
        target_trades=50000,
        **merged,
    )
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    loaded = json.loads(progress_path.read_text(encoding="utf-8"))
    assert loaded["stage"] == "stage_stalled"
    assert loaded["curriculum_stage"] == "stage1_trend"
    assert loaded["needs_attention"] is True
    assert loaded["phoenix_novelty"] == "expand_data"
    assert loaded["terminal_stall_reason"] == "plateau_evolution_exhausted"


@pytest.mark.unit
def test_write_birth_progress_clears_stale_blockers_on_stage_change(tmp_path: Path) -> None:
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="curriculum_learning",
        message="stage2 stalled",
        progress_pct=50.0,
        curriculum_stage="stage2_range",
        stage_blocker_metric="position_flat",
        stage_blocker_value=0.7071,
        pass_reason="position_flat 70.7% outside 30–70%",
    )
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="ppo_training",
        message="stage3 rolling",
        progress_pct=60.0,
        curriculum_stage="stage3_mixed",
        stage_trades=50,
        stage_blocker_metric=None,
        stage_blocker_value=None,
        pass_reason=None,
    )
    progress_path = tmp_path / "state" / "lumina_birth_progress.json"
    loaded = json.loads(progress_path.read_text(encoding="utf-8"))
    assert loaded["curriculum_stage"] == "stage3_mixed"
    assert loaded.get("stage_blocker_metric") is None
    assert loaded.get("pass_reason") is None


@pytest.mark.unit
def test_write_birth_progress_stall_clears_live_training_fields(tmp_path: Path) -> None:
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="ppo_training",
        message="PPO batch training",
        progress_pct=27.0,
        ppo_steps=86000,
        cumulative_trades=2731,
        birth_start_time=1_789_404_000.0,
        is_advancing=True,
        sub_phase="ppo_training",
        sub_phase_label="PPO batch training",
        pass_reason="foundation_fail:median_loss_r=None missing_or_gt_1.5;replay_cap trades=2331 days=0",
        retryable=False,
        auto_recovery_active=True,
    )
    write_birth_progress(
        tmp_path,
        stage="stage_stalled",
        phase="stage_stalled",
        message="Terminal freeze: phoenix_cycle — Twin/operator next_action=accept_champion_or_wipe",
        progress_pct=27.0,
        cumulative_trades=2731,
        birth_start_time=1_789_404_000.0,
        retryable=False,
        terminal_stall_reason="phoenix_cycle",
    )
    loaded = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert loaded["is_advancing"] is False
    assert loaded["sub_phase"] == "stage_stalled"
    assert loaded.get("auto_recovery_active") is False
    assert loaded.get("ppo_steps") == 86000
    assert loaded.get("pass_reason") in (None, "")


@pytest.mark.unit
def test_write_birth_progress_keeps_s5_oos_when_later_write_nulls_them(tmp_path: Path) -> None:
    """S5 HUD Sharpe/DD must not flicker to '—' after a PPO heartbeat omits them."""
    start = 1_789_674_000.0
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="curriculum_learning",
        message="S5 holdout exam",
        progress_pct=90.0,
        birth_start_time=start,
        curriculum_stage="stage5_probe_handoff",
        oos_sharpe=-1.0440824062263843,
        oos_dd_pct=7.029706844053261,
        stage_pass_now=True,
    )
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="ppo_training",
        message="PPO training: 9,000/50,000 timesteps in huidige batch (18.0%)",
        progress_pct=91.0,
        birth_start_time=start,
        curriculum_stage="stage5_probe_handoff",
        oos_sharpe=None,
        oos_dd_pct=None,
        stage_pass_now=True,
    )
    payload = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert payload["oos_sharpe"] == pytest.approx(-1.0440824062263843)
    assert payload["oos_dd_pct"] == pytest.approx(7.029706844053261)


@pytest.mark.unit
def test_write_birth_progress_new_session_drops_s5_oos(tmp_path: Path) -> None:
    write_birth_progress(
        tmp_path,
        stage="training_running",
        phase="curriculum_learning",
        message="S5 holdout exam",
        progress_pct=90.0,
        birth_start_time=1_789_674_000.0,
        curriculum_stage="stage5_probe_handoff",
        oos_sharpe=-1.04,
        oos_dd_pct=7.0,
    )
    write_birth_progress(
        tmp_path,
        stage="loading_data",
        phase="loading_history",
        message="Historische data laden…",
        progress_pct=8.0,
        birth_start_time=1_789_760_400.0,
        curriculum_stage="stage1_trend",
    )
    payload = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert payload.get("oos_sharpe") is None
    assert payload.get("oos_dd_pct") is None
    assert payload.get("curriculum_stage") == "stage1_trend"
