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
    stage = (
        [{"done": True, "pnl": -20.2} for _ in range(70)]
        + [{"done": True, "pnl": 28.0} for _ in range(80)]
    )
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
    assert resolve_unique_calendar_days(12, manifest={"actual_calendar_days": 89}) == 12
