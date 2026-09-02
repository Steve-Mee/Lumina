"""S5 OOS drawdown yardstick: unit, formula, currency. Floors stay pinned."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.certificate_evaluator import (
    _peak_to_end_drawdown_pct,
    max_drawdown_pct,
)
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.fitness_vector import (
    BirthFitnessVector,
    receipt_checksum,
    write_fitness_vector,
)
from lumina_core.birth.foundation_complete import complete_foundation_birth
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S5_DD_EQUITY_USD,
    S5_DD_MAX_PCT,
    S5_EDGE_MIN,
    S5_MIN_TRADES,
    S5_SHARPE_FLOOR,
    build_foundation_snapshot,
)
from lumina_core.birth.foundation_pass import evaluate_foundation_pass
from lumina_core.birth.foundation_skill_clock import skill_clock_keeps_stage_open
from lumina_core.birth.pnl_units import POINT_TO_USD, pnl_increments_to_usd
from lumina_core.birth.runway import risk_metrics_from_pnl
from lumina_core.birth.stage2_participation_envelope import (
    MODE_FORCE_OPEN,
    MODE_PASSTHROUGH,
    decide_stage2_participation,
)
from lumina_core.maturity.birth_exit import is_birth_exit_sufficient
from tests.birth.test_s5_shared_imu import _envelope_decision, _v2_receipt, _write_five_receipts


def test_a_floors_pinned() -> None:
    assert S5_DD_EQUITY_USD == 50_000.0
    assert S5_DD_MAX_PCT == 25.0
    assert S5_MIN_TRADES == 50
    assert S5_EDGE_MIN == pytest.approx(-0.03)
    assert S5_SHARPE_FLOOR == pytest.approx(-2.0)
    assert POLICY_EDGE_MIN_TRADES == 150


def test_a_two_losses_are_four_percent_of_50k() -> None:
    sharpe, dd = risk_metrics_from_pnl([-1000.0, -1000.0])
    assert dd == pytest.approx(2000.0 / S5_DD_EQUITY_USD * 100.0)
    assert dd == pytest.approx(4.0)
    assert dd == max_drawdown_pct([-1000.0, -1000.0], equity=S5_DD_EQUITY_USD)
    assert sharpe == pytest.approx(0.0)  # <5 samples


def test_a_v_shape_reports_trough_not_peak_to_end() -> None:
    series = [-5000.0, -5000.0, 8000.0]
    dd = max_drawdown_pct(series, equity=S5_DD_EQUITY_USD)
    peak_end = _peak_to_end_drawdown_pct(series, equity=S5_DD_EQUITY_USD)
    assert dd == pytest.approx(20.0)
    assert peak_end == pytest.approx(4.0)


def test_a_dollars_are_not_percent() -> None:
    usd = 5757.72
    pct = usd / S5_DD_EQUITY_USD * 100.0
    assert pct == pytest.approx(11.51544)
    assert pct <= S5_DD_MAX_PCT


def test_a_currency_points_convert_via_ssot() -> None:
    points = [-200.0, -200.0]
    usd = pnl_increments_to_usd(points, unit="points")
    assert usd == [p * POINT_TO_USD for p in points]
    dd = max_drawdown_pct(usd, equity=S5_DD_EQUITY_USD)
    raw_as_if_usd = max_drawdown_pct(points, equity=S5_DD_EQUITY_USD)
    assert dd == pytest.approx(400.0 * POINT_TO_USD / S5_DD_EQUITY_USD * 100.0)
    assert dd != pytest.approx(raw_as_if_usd)


def test_d_s5_volume_50_policy_149_not_terminal() -> None:
    assert (
        skill_clock_keeps_stage_open(
            stage=CurriculumStage.STAGE5_PROBE_HANDOFF,
            stage_trades=50,
            policy_trades=149,
            ticks_remaining=True,
            participation_mode=MODE_PASSTHROUGH,
            idle_armed=True,
            occupancy_in_band=True,
        )
        is True
    )


def test_d_s5_policy_150_and_floors_can_pass() -> None:
    snap = build_foundation_snapshot(
        trades=150,
        wins=70,
        skill_trades=150,
        skill_wins=70,
        occupancy=0.50,
        median_loss_r_value=1.05,
        mean_r_value=-0.05,
        p_ft=0.28,
        net_rr=1.2,
        settlement_ok=True,
        settlement_share=1.0,
        constitution_violations=0,
        entropy_alive=True,
        unique_calendar_days=40,
        oos_sharpe=-1.0,
        oos_dd_pct=10.0,
    )
    decision = evaluate_foundation_pass(CurriculumStage.STAGE5_PROBE_HANDOFF, snap)
    assert decision.passed is True


def test_d_s5_policy_149_never_passes() -> None:
    snap = build_foundation_snapshot(
        trades=533,
        wins=163,
        skill_trades=149,
        skill_wins=27,
        occupancy=0.716,
        median_loss_r_value=1.05,
        mean_r_value=-0.05,
        p_ft=0.321,
        net_rr=1.2,
        settlement_ok=True,
        settlement_share=1.0,
        constitution_violations=0,
        entropy_alive=True,
        unique_calendar_days=88,
        oos_sharpe=-1.5,
        oos_dd_pct=11.5,
    )
    decision = evaluate_foundation_pass(CurriculumStage.STAGE5_PROBE_HANDOFF, snap)
    assert decision.passed is False
    assert "policy_sample 149 < 150" in decision.message


def test_c_refractory_blocks_chatter_then_rearms() -> None:
    blocked = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=1.0,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        min_dwell_bars=8,
        cumulative_in_band_passthrough=True,
        force_open_refractory=True,
    )
    assert blocked.mode != MODE_FORCE_OPEN
    assert blocked.mode == MODE_PASSTHROUGH
    rearmed = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=1.0,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        min_dwell_bars=8,
        cumulative_in_band_passthrough=True,
        force_open_refractory=False,
    )
    assert rearmed.mode == MODE_FORCE_OPEN


def test_c_in_band_passthrough_ignores_refractory() -> None:
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.55,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        cumulative_in_band_passthrough=True,
        force_open_refractory=True,
    )
    assert d.mode == MODE_PASSTHROUGH


def test_c_s4_first_force_open_still_fires() -> None:
    d = _envelope_decision(
        CurriculumStage.STAGE4_VIABLE_PLANT, cumulative_flat=1.0, position=0
    )
    assert d.mode == MODE_FORCE_OPEN


def test_e_failing_s5_does_not_write_fitness(tmp_path) -> None:  # type: ignore[no-untyped-def]
    receipts = [
        _v2_receipt("stage1_trend", occupancy=None),
        _v2_receipt("stage2_range"),
        _v2_receipt("stage3_mixed"),
        _v2_receipt("stage4_viable_plant"),
        _v2_receipt("stage5_probe_handoff", oos_sharpe=-3.0),
    ]
    host = SimpleNamespace(
        _stage_pass_receipts=receipts,
        cumulative_trades=900,
        workspace_root=tmp_path,
        birth_config=SimpleNamespace(curriculum=SimpleNamespace(polish_ppo_timesteps=100)),
        buffer=[],
        ppo_trainer=SimpleNamespace(
            final_birth_polish=lambda _b: None,
            save_final_birth_policy=lambda _p: None,
        ),
        practice_policy_path=tmp_path / "practice.pt",
        final_policy_path=tmp_path / "final.pt",
        practice_completed_flag_path=tmp_path / "state" / "practice.flag",
        completion_flag_path=tmp_path / "state" / "lumina_birth_completed.flag",
        ppo_steps=0,
        _real_data_pct=1.0,
        birth_start_time=0.0,
    )
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    out = complete_foundation_birth(
        host, training_mode="certified", trade_budget_cap=1000, practice_mode=False
    )
    assert out["status"] == "foundation_incomplete"
    assert "fitness_vector" not in out or out.get("fitness_vector") is None
    assert not (tmp_path / "state" / "lumina_birth_fitness_vector.json").is_file()


def test_e_five_receipts_matching_vector_still_exits(tmp_path) -> None:  # type: ignore[no-untyped-def]
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
