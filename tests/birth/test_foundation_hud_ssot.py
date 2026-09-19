"""HUD progress snapshot must equal Foundation pass physics (ADR-0046)."""

from __future__ import annotations

import pytest

from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.foundation_metrics import median_loss_r, r_multiples, stop_usd
from lumina_core.birth.stage_loop_progress_metrics import (
    STAGE_VAL_PNL_CHECKPOINT_CAP,
    restore_stage_val_pnl,
    restore_stage_val_pnl_from_buffer,
    restore_stage_val_r,
    restore_stage_val_r_from_buffer,
    serialize_stage_val_pnl,
    serialize_stage_val_r,
)
from lumina_core.birth.stage_scorecard import build_scorecard_payload
from lumina_core.notifications.milestone_events_plateau import plateau_entered_event


@pytest.mark.unit
def test_serialize_stage_val_pnl_caps_and_round_trips() -> None:
    series = [float(i) for i in range(STAGE_VAL_PNL_CHECKPOINT_CAP + 25)]
    stored = serialize_stage_val_pnl(series)
    assert len(stored) == STAGE_VAL_PNL_CHECKPOINT_CAP
    assert stored[0] == 25.0
    restored = restore_stage_val_pnl(stored)
    assert restored == stored
    assert restore_stage_val_pnl(None) == []
    assert restore_stage_val_pnl("nope") == []


@pytest.mark.unit
def test_serialize_stage_val_r_round_trips_and_buffer_ignores_usd() -> None:
    stored = serialize_stage_val_r([-1.05, -1.12, 1.38])
    assert restore_stage_val_r(stored) == stored
    restored = restore_stage_val_r_from_buffer(
        [
            {"done": True, "pnl": -159.0, "trade_r": -1.1},
            {"done": True, "pnl": -159.0},
            {"done": False, "trade_r": -9.0},
        ],
        stage_trades=10,
    )
    assert restored == [-1.1]


@pytest.mark.unit
def test_restore_stage_val_pnl_from_buffer_uses_last_stage_closes() -> None:
    oracle = [{"done": True, "pnl": 35.0, "source": "oracle"} for _ in range(20)]
    stage = [{"done": True, "pnl": -20.2} for _ in range(70)] + [{"done": True, "pnl": 28.0} for _ in range(80)]
    restored = restore_stage_val_pnl_from_buffer(
        oracle + stage,
        stage_trades=150,
    )
    assert len(restored) == 150
    assert restored[0] == pytest.approx(-20.2)
    usd = stop_usd(stop_pct=0.000537, ref_price=7521.25)
    assert median_loss_r(r_multiples(restored, stop_usd_value=usd)) is not None


@pytest.mark.unit
def test_checkpoint_pnl_round_trip_preserves_median_loss_r() -> None:
    pnl = [-20.2] * 80 + [28.0] * 70
    stored = serialize_stage_val_pnl(pnl)
    restored = restore_stage_val_pnl(stored)
    usd = stop_usd(stop_pct=0.000537, ref_price=7521.25)
    original = median_loss_r(r_multiples(pnl, stop_usd_value=usd))
    after = median_loss_r(r_multiples(restored, stop_usd_value=usd))
    assert original is not None
    assert after == pytest.approx(float(original))


@pytest.mark.unit
def test_hud_and_engine_share_process_r_and_net_rr() -> None:
    from lumina_core.birth.config import BirthCurriculumConfig

    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    pnl = [-20.2] * 70 + [28.2] * 80
    kwargs = dict(
        trades=150,
        wins=80,
        hold_signals=100,
        total_signals=400,
        constitution_violations=0,
        target_trades=150,
        cfg=cfg,
        pnl_series=pnl,
        stop_pct=0.000537,
        ref_price=7521.25,
        geometry_net_rr=1.3975,
        unique_calendar_days=40,
        closes_stop=70,
        closes_target=80,
        policy_entropy=5.6,
        ppo_steps=2000,
    )
    engine = evaluate_stage_pass(CurriculumStage.STAGE1_TREND, **kwargs)
    hud = build_scorecard_payload(
        stage=CurriculumStage.STAGE1_TREND,
        curriculum_index=1,
        stages_passed=[],
        stage_trades=150,
        stage_wins=80,
        stage_hold_signals=100,
        stage_total_signals=400,
        constitution_violations=0,
        target_trades=2000,
        phase="curriculum_learning",
        patterns_mined=10,
        learning_attempt=1,
        cfg=cfg,
        pnl_series=pnl,
        stop_pct=0.000537,
        ref_price=7521.25,
        geometry_net_rr=1.3975,
        unique_calendar_days=40,
        closes_stop=70,
        closes_target=80,
        policy_entropy=5.6,
        ppo_steps=2000,
    )
    assert engine.median_loss_r is not None
    assert hud["median_loss_r"] == pytest.approx(float(engine.median_loss_r))
    assert hud["geometry_net_rr"] == pytest.approx(float(engine.net_rr or 0.0))
    assert hud["geometry_net_rr_after_cost"] == pytest.approx(hud["geometry_net_rr"])
    assert hud["stage_pass_now"] is bool(engine.passed)
    assert hud["occupancy"] is None
    assert hud["stage_blocker_metric"] is None
    assert hud["pass_reason"] is None
    assert hud["foundation_unique_calendar_days"] == 40
    assert hud["foundation_skill_wr"] == pytest.approx(80 / 150)
    assert "foundation_schema" in hud


@pytest.mark.unit
def test_plateau_entered_event_does_not_invent_wr_45() -> None:
    ev = plateau_entered_event(stage_trades=500, winrate=0.288)
    assert "45%" not in ev.summary
    assert "process-R" in ev.summary
    assert ev.context["pass_target"] == "foundation_process"


@pytest.mark.unit
def test_hud_pass_reason_uses_computed_process_r_not_none() -> None:
    from lumina_core.birth.config import BirthCurriculumConfig

    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    pnl = [-80.0] * 80 + [28.2] * 70
    hud = build_scorecard_payload(
        stage=CurriculumStage.STAGE1_TREND,
        curriculum_index=1,
        stages_passed=[],
        stage_trades=150,
        stage_wins=70,
        stage_hold_signals=100,
        stage_total_signals=400,
        constitution_violations=0,
        target_trades=2000,
        phase="curriculum_learning",
        patterns_mined=10,
        learning_attempt=1,
        cfg=cfg,
        pnl_series=pnl,
        stop_pct=0.000537,
        ref_price=7521.25,
        geometry_net_rr=1.3975,
        unique_calendar_days=89,
        closes_stop=80,
        closes_target=70,
        policy_entropy=5.6,
        ppo_steps=2000,
    )
    assert hud["median_loss_r"] is not None
    assert float(hud["median_loss_r"]) > 1.5
    assert hud["stage_pass_now"] is False
    assert hud["stage_blocker_metric"] == "median_loss_r"
    reason = str(hud["pass_reason"] or "")
    assert "None" not in reason
    assert str(hud["median_loss_r"]) in reason
    assert "days=0" not in reason
    assert hud["foundation_unique_calendar_days"] == 89


@pytest.mark.unit
def test_resolve_unique_calendar_days_prefers_manifest_then_progress() -> None:
    from lumina_core.birth.history_loader import resolve_unique_calendar_days

    assert resolve_unique_calendar_days(0) == 0
    assert (
        resolve_unique_calendar_days(
            0,
            manifest={"actual_calendar_days": 57},
            progress={"actual_calendar_days": 89},
        )
        == 57
    )
    assert (
        resolve_unique_calendar_days(
            0,
            manifest={},
            progress={"actual_calendar_days": 89},
        )
        == 89
    )
    assert resolve_unique_calendar_days(12, manifest={"actual_calendar_days": 89}) == 89


def _s3_hud_kwargs() -> dict[str, object]:
    from lumina_core.birth.config import BirthCurriculumConfig

    return {
        "stage": CurriculumStage.STAGE3_MIXED,
        "curriculum_index": 3,
        "stages_passed": ["stage1_trend", "stage2_range"],
        "stage_trades": 400,
        "stage_wins": 130,
        "stage_hold_signals": 8000,
        "stage_total_signals": 10000,
        "stage_range_flat_bars": 4000,
        "stage_range_total_signals": 10000,
        "stage_range_round_trips": 400,
        "constitution_violations": 0,
        "target_trades": 400,
        "phase": "curriculum_learning",
        "patterns_mined": 100,
        "learning_attempt": 1,
        "cfg": BirthCurriculumConfig(),
        "median_loss_r": 1.18,
        "mean_r": -0.2,
        "geometry_net_rr": 1.27,
        "first_touch_hit_rate": 0.30,
        "unique_calendar_days": 91,
        "closes_stop": 200,
        "closes_target": 150,
        "closes_time_stop": 50,
        "closes_flatten": 0,
        "closes_unknown": 0,
        "policy_entropy": 5.6,
        "ppo_steps": 2000,
        "policy_trades": 400,
        "policy_wins": 130,
    }


@pytest.mark.unit
def test_live_s4_occupancy_below_exam_is_visible_before_volume_gate() -> None:
    """Live S4: 72 trades, plant-flat 0.2477. Occupancy fail must not hide behind volume."""
    from lumina_core.birth.config import BirthCurriculumConfig

    hud = build_scorecard_payload(
        stage=CurriculumStage.STAGE4_VIABLE_PLANT,
        curriculum_index=4,
        stages_passed=["stage1_trend", "stage2_range", "stage3_mixed"],
        stage_trades=72,
        stage_wins=14,
        stage_hold_signals=7000,
        stage_total_signals=9331,
        stage_range_flat_bars=2311,
        stage_range_total_signals=9331,
        stage_range_round_trips=72,
        constitution_violations=0,
        target_trades=100,
        phase="curriculum_learning",
        patterns_mined=10,
        learning_attempt=9,
        cfg=BirthCurriculumConfig(),
        median_loss_r=0.615,
        mean_r=-0.348,
        geometry_net_rr=1.15,
        first_touch_hit_rate=0.297,
        unique_calendar_days=181,
        closes_stop=50,
        closes_target=14,
        closes_time_stop=8,
        policy_entropy=5.6,
        ppo_steps=188000,
        policy_trades=72,
        policy_wins=14,
        occupancy_exam_armed=False,
        envelope_override_fraction=None,
        airframe_override_fraction=0.9846,
    )
    assert hud["stage_pass_now"] is False
    reason = str(hud["pass_reason"] or "")
    assert "occupancy" in reason
    assert hud["envelope_override_fraction"] is None
    assert hud["occupancy_exam_armed"] is False
    occ = hud.get("occupancy")
    assert occ is not None
    assert float(occ) < 0.25


@pytest.mark.unit
def test_hud_stage3_envelope_dominated_is_not_green() -> None:
    """Live lie: occupancy 0.28 green while envelope owned 90% of ticks."""
    clean = build_scorecard_payload(**_s3_hud_kwargs())  # type: ignore[arg-type]
    assert clean["stage_pass_now"] is True
    assert clean["stage_blocker_metric"] is None

    dominated = build_scorecard_payload(
        **_s3_hud_kwargs(),  # type: ignore[arg-type]
        envelope_override_fraction=0.90,
        passthrough_range_flat_bars=4704,
        passthrough_range_total_signals=11762,
    )
    assert dominated["stage_pass_now"] is False
    reason = str(dominated["pass_reason"] or "")
    assert "occupancy_envelope_dominated" in reason
    assert dominated["stage_blocker_metric"] == "occupancy"
    assert dominated["envelope_override_fraction"] == pytest.approx(0.90)
    assert not (
        bool(dominated["stage_pass_now"])
        and str(dominated.get("pass_reason") or "").startswith("foundation_fail")
    )


@pytest.mark.unit
def test_envelope_override_fraction_and_passthrough_occupancy_helpers() -> None:
    from lumina_core.birth.foundation_occupancy_envelope import (
        envelope_override_fraction,
        occupancy_for_foundation_pass,
    )

    assert envelope_override_fraction(11762, 100699) == pytest.approx(100699 / 112461)
    assert envelope_override_fraction(0, 0) is None
    occ = occupancy_for_foundation_pass(
        stage=CurriculumStage.STAGE3_MIXED,
        range_flat_bars=31489,
        range_total_signals=112461,
        passthrough_flat_bars=2000,
        passthrough_total_signals=11762,
    )
    assert occ == pytest.approx(2000 / 11762)
    s1 = occupancy_for_foundation_pass(
        stage=CurriculumStage.STAGE1_TREND,
        range_flat_bars=10,
        range_total_signals=100,
        passthrough_flat_bars=10,
        passthrough_total_signals=100,
    )
    assert s1 is None


@pytest.mark.unit
def test_exam_window_ignores_lifetime_airframe_override() -> None:
    """Live trap: 87% taxi override must not fail a plant that holds the band."""
    from lumina_core.birth.foundation_occupancy_envelope import (
        OccupancyExamWindow,
        exam_window_override_fraction,
        occupancy_for_foundation_pass,
        step_occupancy_exam_window,
    )
    from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN

    taxi = OccupancyExamWindow()
    for _ in range(20):
        taxi = step_occupancy_exam_window(
            taxi,
            plant_flat=0.20,
            exam_lo=S3_OCCUPANCY_MIN,
            exam_hi=S3_OCCUPANCY_MAX,
            passthrough=False,
            empty=False,
        )
    assert taxi.armed is False
    assert exam_window_override_fraction(taxi) is None

    win = OccupancyExamWindow()
    for i in range(60):
        win = step_occupancy_exam_window(
            win,
            plant_flat=0.40,
            exam_lo=S3_OCCUPANCY_MIN,
            exam_hi=S3_OCCUPANCY_MAX,
            passthrough=True,
            empty=i % 2 == 0,
        )
    assert win.ready is True
    assert exam_window_override_fraction(win) == pytest.approx(0.0)
    occ = occupancy_for_foundation_pass(
        stage=CurriculumStage.STAGE3_MIXED,
        range_flat_bars=4000,
        range_total_signals=10000,
        passthrough_flat_bars=2000,
        passthrough_total_signals=11762,
        exam_armed=True,
        exam_passthrough_flat_bars=win.passthrough_flat,
        exam_passthrough_total_signals=win.passthrough_signals,
    )
    assert occ == pytest.approx(win.passthrough_flat / win.passthrough_signals)
    assert 0.25 <= float(occ) <= 0.75

    left = step_occupancy_exam_window(
        win,
        plant_flat=0.20,
        exam_lo=S3_OCCUPANCY_MIN,
        exam_hi=S3_OCCUPANCY_MAX,
        passthrough=True,
        empty=True,
    )
    assert left.armed is False

    payload = build_scorecard_payload(
        **_s3_hud_kwargs(),  # type: ignore[arg-type]
        envelope_override_fraction=0.10,
        airframe_override_fraction=0.87,
        occupancy_exam_armed=True,
        exam_passthrough_flat_bars=win.passthrough_flat,
        exam_passthrough_total_signals=win.passthrough_signals,
    )
    assert payload["stage_pass_now"] is True
    assert payload["airframe_override_fraction"] == pytest.approx(0.87)
    assert payload["envelope_override_fraction"] == pytest.approx(0.10)

    dominated = build_scorecard_payload(
        **_s3_hud_kwargs(),  # type: ignore[arg-type]
        envelope_override_fraction=0.87,
        occupancy_exam_armed=True,
        exam_passthrough_flat_bars=40,
        exam_passthrough_total_signals=60,
    )
    assert dominated["stage_pass_now"] is False
    assert "occupancy_envelope_dominated" in str(dominated.get("pass_reason") or "")


@pytest.mark.unit
def test_live_replica_taxi_occupancy_is_plant_flat_not_passthrough_0_197() -> None:
    from lumina_core.birth.foundation_occupancy_envelope import occupancy_for_foundation_pass

    overtrade = occupancy_for_foundation_pass(
        stage=CurriculumStage.STAGE3_MIXED,
        range_flat_bars=25000,
        range_total_signals=126328,
        passthrough_flat_bars=2320,
        passthrough_total_signals=11762,
        exam_armed=False,
    )
    assert overtrade == pytest.approx(25000 / 126328)
    assert overtrade is not None and overtrade < 0.25
    in_band_unproven = occupancy_for_foundation_pass(
        stage=CurriculumStage.STAGE3_MIXED,
        range_flat_bars=31582,
        range_total_signals=126328,
        passthrough_flat_bars=2320,
        passthrough_total_signals=11762,
        exam_armed=False,
    )
    assert in_band_unproven is None
    thin = occupancy_for_foundation_pass(
        stage=CurriculumStage.STAGE3_MIXED,
        range_flat_bars=31582,
        range_total_signals=126328,
        exam_armed=True,
        exam_passthrough_flat_bars=10,
        exam_passthrough_total_signals=20,
    )
    assert thin is None
