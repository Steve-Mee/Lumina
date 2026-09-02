"""Shared occupancy envelope + in-band idle for S2–S5 (one airframe, one pilot)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.fitness_vector import (
    BirthFitnessVector,
    receipt_checksum,
    write_fitness_vector,
)
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S2_OCCUPANCY_MAX,
    S2_OCCUPANCY_MIN,
    S3_EDGE_MIN,
    S3_MIN_TRADES,
    S3_OCCUPANCY_MAX,
    S3_OCCUPANCY_MIN,
    S4_EDGE_MIN,
    S4_MIN_TRADES,
    S5_DD_MAX_PCT,
    S5_EDGE_MIN,
    S5_MIN_TRADES,
    S5_SHARPE_FLOOR,
    build_foundation_snapshot,
)
from lumina_core.birth.foundation_occupancy_envelope import (
    foundation_cumulative_in_band_passthrough,
    foundation_envelope_controller_spec,
    foundation_occupancy_envelope_enabled,
)
from lumina_core.birth.foundation_pass import evaluate_foundation_pass
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.stage2_participation_envelope import (
    MODE_FORCE_OPEN,
    MODE_PASSTHROUGH,
    decide_stage2_participation,
    occupancy_control_over,
)
from lumina_core.birth.stage3_inband_idle import (
    FOUNDATION_INBAND_IDLE_REGIMES,
    S3_INBAND_REGIMES,
    S4_IDLE_REGIMES,
    plant_tag_for_entry,
    s3_inband_idle_armed,
)
from lumina_core.birth.stage_pass_receipt_types import StagePassReceipt
from lumina_core.maturity.birth_exit import is_birth_exit_sufficient
from tests.birth.honest_settlement import honest_closes
from tests.birth.test_s3_inband_idle import simulate_passthrough_hold_mask_bars


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        stage2_participation_envelope_enabled=True,
        stage3_participation_envelope_enabled=True,
        stage4_participation_envelope_enabled=True,
        stage5_participation_envelope_enabled=True,
    )


def _envelope_decision(
    stage: CurriculumStage,
    *,
    cumulative_flat: float,
    position: int,
    rolling_flat: float | None = None,
) -> object:
    cfg = _cfg()
    enabled = foundation_occupancy_envelope_enabled(stage, cfg)
    spec = foundation_envelope_controller_spec(stage, cfg)
    return decide_stage2_participation(
        enabled=enabled,
        range_flat_ratio=float(cumulative_flat),
        rolling_flat_ratio=rolling_flat,
        range_total_signals=8000,
        position=int(position),
        bars_in_position=0,
        band_lo=spec.band_lo,
        band_hi=spec.band_hi,
        hysteresis=spec.hysteresis,
        under_band_release_hysteresis=spec.release_hysteresis,
        min_signals=50,
        cumulative_in_band_passthrough=foundation_cumulative_in_band_passthrough(
            stage.value
        ),
    )


def test_floors_unchanged() -> None:
    assert S5_MIN_TRADES == 50
    assert S5_EDGE_MIN == pytest.approx(-0.03)
    assert S5_SHARPE_FLOOR == pytest.approx(-2.0)
    assert S5_DD_MAX_PCT == pytest.approx(25.0)
    assert POLICY_EDGE_MIN_TRADES == 150
    assert S3_MIN_TRADES == 400
    assert S3_EDGE_MIN == pytest.approx(-0.05)
    assert S4_MIN_TRADES == 100
    assert S4_EDGE_MIN == pytest.approx(0.0)
    assert S2_OCCUPANCY_MIN == pytest.approx(0.30)
    assert S2_OCCUPANCY_MAX == pytest.approx(0.70)
    assert S3_OCCUPANCY_MIN == pytest.approx(0.25)
    assert S3_OCCUPANCY_MAX == pytest.approx(0.75)


def test_a_s2_cloud_replica_still_force_open() -> None:
    assert occupancy_control_over(cumulative_flat=0.903, rolling_flat=0.50) == pytest.approx(
        0.903
    )
    d = _envelope_decision(
        CurriculumStage.STAGE2_RANGE,
        cumulative_flat=0.903,
        rolling_flat=0.50,
        position=0,
    )
    assert d.mode == MODE_FORCE_OPEN


def test_a_s3_cumulative_in_band_passthrough() -> None:
    d = _envelope_decision(
        CurriculumStage.STAGE3_MIXED,
        cumulative_flat=0.577,
        rolling_flat=0.278,
        position=0,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.reason == "exam_cumulative_in_band"


def test_a_s4_cum_1_pos_0_force_open() -> None:
    cfg = _cfg()
    assert foundation_occupancy_envelope_enabled(
        CurriculumStage.STAGE4_VIABLE_PLANT, cfg
    ) is True
    d = _envelope_decision(
        CurriculumStage.STAGE4_VIABLE_PLANT, cumulative_flat=1.0, position=0
    )
    assert d.mode == MODE_FORCE_OPEN
    assert plant_tag_for_entry(force_open_this_step=d.mode == MODE_FORCE_OPEN) is True


def test_a_s5_cum_1_pos_0_force_open() -> None:
    cfg = _cfg()
    assert foundation_occupancy_envelope_enabled(
        CurriculumStage.STAGE5_PROBE_HANDOFF, cfg
    ) is True
    d = _envelope_decision(
        CurriculumStage.STAGE5_PROBE_HANDOFF, cumulative_flat=1.0, position=0
    )
    assert d.mode == MODE_FORCE_OPEN
    assert plant_tag_for_entry(force_open_this_step=True) is True


def test_a_s4_s5_in_band_passthrough_not_force_open() -> None:
    s4 = _envelope_decision(
        CurriculumStage.STAGE4_VIABLE_PLANT, cumulative_flat=0.55, position=0
    )
    s5 = _envelope_decision(
        CurriculumStage.STAGE5_PROBE_HANDOFF, cumulative_flat=0.55, position=0
    )
    assert s4.mode == MODE_PASSTHROUGH
    assert s5.mode == MODE_PASSTHROUGH
    assert s4.mode != MODE_FORCE_OPEN
    assert s5.mode != MODE_FORCE_OPEN


def test_a_s1_envelope_off() -> None:
    assert (
        foundation_occupancy_envelope_enabled(CurriculumStage.STAGE1_TREND, _cfg())
        is False
    )


def test_b_idle_s3_in_band_armed() -> None:
    assert (
        s3_inband_idle_armed(
            curriculum_regime="mixed",
            participation_mode=MODE_PASSTHROUGH,
            position=0,
            cumulative_flat=0.58,
            band_lo=0.25,
            band_hi=0.75,
            policy_trades=0,
        )
        is True
    )


def test_b_idle_s3_over_flat_disarmed() -> None:
    assert (
        s3_inband_idle_armed(
            curriculum_regime="mixed",
            participation_mode=MODE_PASSTHROUGH,
            position=0,
            cumulative_flat=0.90,
            band_lo=0.25,
            band_hi=0.75,
            policy_trades=0,
        )
        is False
    )


def test_b_idle_s4_in_band_armed() -> None:
    assert "stage4_viable_plant" in FOUNDATION_INBAND_IDLE_REGIMES
    assert (
        s3_inband_idle_armed(
            curriculum_regime="stage4_viable_plant",
            participation_mode=MODE_PASSTHROUGH,
            position=0,
            cumulative_flat=0.58,
            band_lo=0.25,
            band_hi=0.75,
            policy_trades=0,
        )
        is True
    )


def test_b_idle_s4_over_flat_disarmed() -> None:
    """Regression vs PR #9 over-flat skip."""
    assert "stage4_viable_plant" in S4_IDLE_REGIMES
    assert "stage4_viable_plant" not in S3_INBAND_REGIMES
    assert (
        s3_inband_idle_armed(
            curriculum_regime="stage4_viable_plant",
            participation_mode=MODE_PASSTHROUGH,
            position=0,
            cumulative_flat=1.0,
            band_lo=0.25,
            band_hi=0.75,
            policy_trades=0,
        )
        is False
    )


def test_b_idle_s5_in_band_thin_policy_armed() -> None:
    assert (
        s3_inband_idle_armed(
            curriculum_regime="stage5_probe_handoff",
            participation_mode=MODE_PASSTHROUGH,
            position=0,
            cumulative_flat=0.50,
            band_lo=0.25,
            band_hi=0.75,
            policy_trades=12,
        )
        is True
    )


def test_b_idle_s5_over_flat_disarmed() -> None:
    assert (
        s3_inband_idle_armed(
            curriculum_regime="stage5_probe_handoff",
            participation_mode=MODE_PASSTHROUGH,
            position=0,
            cumulative_flat=1.0,
            band_lo=0.25,
            band_hi=0.75,
            policy_trades=0,
        )
        is False
    )


def test_b_idle_s2_range_disarmed() -> None:
    assert (
        s3_inband_idle_armed(
            curriculum_regime="stage2_range",
            participation_mode=MODE_PASSTHROUGH,
            position=0,
            cumulative_flat=0.50,
            band_lo=0.30,
            band_hi=0.70,
            policy_trades=0,
        )
        is False
    )


def test_b_idle_policy_150_s4_s5_disarmed() -> None:
    for regime in ("stage4_viable_plant", "stage5_probe_handoff"):
        assert (
            s3_inband_idle_armed(
                curriculum_regime=regime,
                participation_mode=MODE_PASSTHROUGH,
                position=0,
                cumulative_flat=0.55,
                band_lo=0.25,
                band_hi=0.75,
                policy_trades=150,
            )
            is False
        )


def test_no_s5_idle_regimes_over_flat_kruk() -> None:
    src = Path("lumina_core/birth/stage3_inband_idle.py").read_text(encoding="utf-8")
    assert "S5_IDLE_REGIMES" not in src
    assert "if not s4_idle" not in src
    pre = Path("lumina_core/birth/stage_loop_rollout_pre_caps.py").read_text(
        encoding="utf-8"
    )
    assert "foundation_occupancy_envelope_enabled" in pre
    assert "is_s2\n                and getattr" not in pre


def test_c_s4_b2_replica_envelope_force_open_not_idle() -> None:
    d = _envelope_decision(
        CurriculumStage.STAGE4_VIABLE_PLANT, cumulative_flat=1.0, position=0
    )
    assert d.mode == MODE_FORCE_OPEN
    armed = s3_inband_idle_armed(
        curriculum_regime="stage4_viable_plant",
        participation_mode=MODE_PASSTHROUGH,
        position=0,
        cumulative_flat=1.0,
        band_lo=0.25,
        band_hi=0.75,
        policy_trades=0,
    )
    assert armed is False
    assert plant_tag_for_entry(force_open_this_step=d.mode == MODE_FORCE_OPEN) is True
    assert plant_tag_for_entry(force_open_this_step=False) is False


def test_c_s5_collapse_replica_envelope_force_open_not_idle() -> None:
    d = _envelope_decision(
        CurriculumStage.STAGE5_PROBE_HANDOFF, cumulative_flat=1.0, position=0
    )
    assert d.mode == MODE_FORCE_OPEN
    armed = s3_inband_idle_armed(
        curriculum_regime="stage5_probe_handoff",
        participation_mode=MODE_PASSTHROUGH,
        position=0,
        cumulative_flat=1.0,
        band_lo=0.25,
        band_hi=0.75,
        policy_trades=0,
    )
    assert armed is False
    assert plant_tag_for_entry(force_open_this_step=True) is True


def test_c_s3_40_hold_in_band_still_policy_tagged() -> None:
    rows = simulate_passthrough_hold_mask_bars(
        n_bars=40,
        min_idle_hold_bars=32,
        cumulative_flat=0.58,
        policy_trades=0,
        participation_mode=MODE_PASSTHROUGH,
        position=0,
    )
    first_entry = next((i for i, (side, _p, _r) in enumerate(rows) if side in {1, 2}), None)
    assert first_entry == 31
    _side, is_plant, _reason = rows[31]
    assert is_plant is False


def _s5_snap(**overrides: object) -> object:
    payload: dict[str, object] = {
        "trades": 150,
        "wins": 70,
        "skill_trades": 150,
        "skill_wins": 70,
        "occupancy": 0.50,
        "median_loss_r_value": 1.05,
        "mean_r_value": -0.05,
        "p_ft": 0.28,
        "net_rr": 1.2,
        "settlement_ok": True,
        "settlement_share": 1.0,
        "constitution_violations": 0,
        "entropy_alive": True,
        "unique_calendar_days": 40,
        "oos_sharpe": -1.0,
        "oos_dd_pct": 10.0,
    }
    payload.update(overrides)
    return build_foundation_snapshot(**payload)  # type: ignore[arg-type]


def test_d_s5_oos_none_fails_foundation_pass() -> None:
    snap = _s5_snap(oos_sharpe=None, oos_dd_pct=10.0)
    decision = evaluate_foundation_pass(CurriculumStage.STAGE5_PROBE_HANDOFF, snap)
    assert decision.passed is False
    assert "oos_sharpe" in decision.message


def test_d_s5_holdout_oos_can_pass_when_common_body_ok() -> None:
    snap = _s5_snap(oos_sharpe=-1.25, oos_dd_pct=12.0)
    decision = evaluate_foundation_pass(CurriculumStage.STAGE5_PROBE_HANDOFF, snap)
    assert decision.passed is True
    assert snap.oos_sharpe is not None
    assert float(snap.oos_sharpe) > S5_SHARPE_FLOOR
    assert float(snap.oos_dd_pct or 0.0) <= S5_DD_MAX_PCT


def test_d_s5_pnl_series_wires_holdout_oos_not_none() -> None:
    result = evaluate_stage_pass(
        CurriculumStage.STAGE5_PROBE_HANDOFF,
        trades=150,
        wins=70,
        hold_signals=40,
        total_signals=400,
        range_total_signals=400,
        range_flat_bars=200,
        range_round_trips=40,
        constitution_violations=0,
        target_trades=50,
        occupancy=0.50,
        unique_calendar_days=40,
        median_loss_r=1.05,
        mean_r=-0.05,
        first_touch_hit_rate=0.28,
        geometry_net_rr=1.2,
        policy_trades=150,
        policy_wins=70,
        plant_trades=0,
        plant_wins=0,
        pnl_series=[50.0, -20.0, 30.0, 10.0, -5.0] * 10,
        **honest_closes(150),
    )
    assert result.oos_sharpe is not None
    assert result.oos_dd_pct is not None


def test_d_s5_empty_pnl_without_explicit_oos_stays_none() -> None:
    result = evaluate_stage_pass(
        CurriculumStage.STAGE5_PROBE_HANDOFF,
        trades=150,
        wins=70,
        hold_signals=40,
        total_signals=400,
        range_total_signals=400,
        range_flat_bars=200,
        constitution_violations=0,
        target_trades=50,
        occupancy=0.50,
        unique_calendar_days=40,
        median_loss_r=1.05,
        mean_r=-0.05,
        first_touch_hit_rate=0.28,
        geometry_net_rr=1.2,
        policy_trades=150,
        policy_wins=70,
        **honest_closes(150),
    )
    assert result.oos_sharpe is None
    assert result.passed is False
    assert "oos_sharpe" in result.message


def _v2_receipt(stage: str, **kwargs: object) -> StagePassReceipt:
    floors = {
        "stage1_trend": 160,
        "stage2_range": 250,
        "stage3_mixed": 400,
        "stage4_viable_plant": 150,
        "stage5_probe_handoff": 150,
    }
    trades = int(kwargs.get("trades", floors.get(stage, 200)) or 200)
    wins = int(kwargs.get("wins", max(40, int(trades * 0.40))) or 40)
    occupancy = kwargs.get("occupancy", 0.4)
    mean_r = kwargs.get("mean_r", -0.05)
    oos_sharpe = kwargs.get("oos_sharpe", -1.0)
    closes = honest_closes(trades)
    return StagePassReceipt(
        stage=stage,
        trades=trades,
        wins=wins,
        winrate=float(wins) / float(max(1, trades)),
        required_trades=int(floors.get(stage, 50)),
        pass_criteria_id="closed_loop",
        provisional=False,
        passed_at="2026-08-14T00:00:00Z",
        engine_version="BRO-v2",
        schema="foundation_v2",
        median_loss_r=1.1,
        mean_r=-0.05 if mean_r is None else float(mean_r),  # type: ignore[arg-type]
        occupancy=None if occupancy is None else float(occupancy),  # type: ignore[arg-type]
        edge=0.10,
        p_ft=0.28,
        geometry_net_rr=1.2,
        unique_calendar_days=40,
        policy_entropy=0.4,
        range_flat_ratio=0.45,
        range_round_trips=40,
        range_total_signals=max(200, trades),
        range_flat_bars=int(0.45 * max(200, trades)),
        hold_signals=40,
        total_signals=max(200, trades),
        oos_sharpe=-1.0 if oos_sharpe is None else float(oos_sharpe),  # type: ignore[arg-type]
        oos_dd_pct=10.0,
        **closes,  # type: ignore[arg-type]
    )


def _write_five_receipts(tmp_path: Path, *, s5: StagePassReceipt | None = None) -> list[StagePassReceipt]:
    receipts = [
        _v2_receipt("stage1_trend", occupancy=None),
        _v2_receipt("stage2_range"),
        _v2_receipt("stage3_mixed"),
        _v2_receipt("stage4_viable_plant"),
        s5 if s5 is not None else _v2_receipt("stage5_probe_handoff", oos_sharpe=-1.25),
    ]
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    write_birth_progress(
        tmp_path,
        stage="foundation_handoff",
        phase="foundation_handoff",
        message="test",
        progress_pct=99.0,
        stage_pass_receipts=[r.to_dict() for r in receipts],
    )
    return receipts


def test_e_five_receipts_matching_vector_exits(tmp_path: Path) -> None:
    receipts = _write_five_receipts(tmp_path)
    s5 = receipts[-1]
    vector = BirthFitnessVector(
        schema="foundation_v2",
        mean_r=float(s5.mean_r or 0.0),
        edge=float(s5.edge or 0.0),
        occupancy=float(s5.occupancy or 0.0),
        oos_wr=float(s5.winrate),
        oos_sharpe=float(s5.oos_sharpe or 0.0),
        median_loss_r=float(s5.median_loss_r or 0.0),
        s5_receipt_checksum=receipt_checksum(s5.to_dict()),
        trades=int(s5.trades),
    )
    write_fitness_vector(tmp_path, vector)
    assert is_birth_exit_sufficient(tmp_path) is True


def test_e_five_receipts_without_vector_stays_open(tmp_path: Path) -> None:
    _write_five_receipts(tmp_path)
    assert is_birth_exit_sufficient(tmp_path) is False


def test_e_checksum_mismatch_stays_open(tmp_path: Path) -> None:
    receipts = _write_five_receipts(tmp_path)
    s5 = receipts[-1]
    vector = BirthFitnessVector(
        schema="foundation_v2",
        mean_r=float(s5.mean_r or 0.0),
        edge=float(s5.edge or 0.0),
        occupancy=float(s5.occupancy or 0.0),
        oos_wr=float(s5.winrate),
        oos_sharpe=float(s5.oos_sharpe or 0.0),
        median_loss_r=float(s5.median_loss_r or 0.0),
        s5_receipt_checksum="deadbeefdeadbeef",
        trades=int(s5.trades),
    )
    write_fitness_vector(tmp_path, vector)
    assert is_birth_exit_sufficient(tmp_path) is False
