"""ADR-0046 lock tests: WR/rolling/empty-filter/HUD loopholes cannot pass Birth."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass, ordered_stages
from lumina_core.birth.foundation_metrics import MEDIAN_LOSS_R_MAX, mechanical_ev_r
from lumina_core.birth.foundation_stages import ticks_for_foundation_stage
from lumina_core.birth.stage_pass_receipt_types import StagePassReceipt
from lumina_core.birth.stage_pass_receipt_verify import verify_stage_pass_receipt
from lumina_core.maturity.birth_exit import evaluate_birth_exit
from lumina_core.maturity.post_birth_skill_gates import (
    CERT_OOS_WR_MIN,
    certificate_oos_walls,
    economic_viability,
    risk_discipline,
)


def _cfg() -> BirthCurriculumConfig:
    return BirthCurriculumConfig()


def _base(**kwargs: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "trades": 200,
        "wins": 50,
        "hold_signals": 40,
        "total_signals": 200,
        "range_hold_signals": 40,
        "range_total_signals": 200,
        "range_flat_bars": 80,
        "range_round_trips": 30,
        "constitution_violations": 0,
        "target_trades": 200,
        "cfg": _cfg(),
        "policy_entropy": 0.4,
        "ppo_steps": 800,
        "closes_stop": 80,
        "closes_target": 70,
        "closes_time_stop": 20,
        "closes_flatten": 10,
        "median_loss_r": 1.1,
        "mean_r": -0.2,
        "geometry_net_rr": 1.2,
        "first_touch_hit_rate": 0.29,
        "unique_calendar_days": 20,
    }
    payload.update(kwargs)
    return payload


def test_process_r_floor_stays_1_5() -> None:
    assert MEDIAN_LOSS_R_MAX == 1.5


def test_stage1_passes_on_process_r_not_winrate() -> None:
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        **_base(trades=160, wins=30),  # type: ignore[arg-type]
    )
    assert result.passed is True
    assert result.schema == "foundation_v2"
    stages = ordered_stages()
    assert [s.value for s in stages] == [
        "stage1_trend",
        "stage2_range",
        "stage3_mixed",
        "stage4_viable_plant",
        "stage5_probe_handoff",
    ]


def test_rolling_lift_cannot_pass_stage2() -> None:
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        **_base(  # type: ignore[arg-type]
            trades=250,
            wins=40,
            rolling_winrate=0.55,
            consecutive_rolling_pass_windows=5,
            range_flat_bars=10,
            range_total_signals=200,
        ),
    )
    assert result.passed is False
    assert "occupancy" in result.message


def test_missing_median_loss_r_fails_all_foundation_stages() -> None:
    for stage in ordered_stages():
        kwargs = _base(median_loss_r=None, trades=500, wins=200)
        if stage == CurriculumStage.STAGE5_PROBE_HANDOFF:
            kwargs["oos_sharpe"] = -1.0
            kwargs["oos_dd_pct"] = 10.0
        result = evaluate_stage_pass(stage, **kwargs)  # type: ignore[arg-type]
        assert result.passed is False, stage.value
        assert "median_loss_r" in result.message


def test_empty_trend_filter_is_none() -> None:
    ticks = [{"regime": "NEUTRAL", "last": 1.0} for _ in range(50)]
    assert ticks_for_foundation_stage(
        CurriculumStage.STAGE1_TREND, train_ticks=ticks
    ) is None


def test_empty_validation_is_none() -> None:
    assert (
        ticks_for_foundation_stage(
            CurriculumStage.STAGE4_VIABLE_PLANT,
            train_ticks=[{"regime": "TREND_UP"}],
            validation_ticks=[],
        )
        is None
    )


def test_hold_cap_is_not_a_pass_gate() -> None:
    result = evaluate_stage_pass(
        CurriculumStage.STAGE4_VIABLE_PLANT,
        **_base(  # type: ignore[arg-type]
            trades=150,
            wins=80,
            hold_signals=10,
            total_signals=200,
            first_touch_hit_rate=0.29,
            mean_r=-0.9,
            occupancy=0.4,
            range_flat_bars=80,
            range_total_signals=200,
        ),
    )
    assert result.passed is False
    assert "mean_r" in result.message or "e_mech" in result.message


def test_stage4_fails_if_edge_negative_or_mean_r_below_emech() -> None:
    p_ft = 0.29
    rr = 1.35
    e_mech = mechanical_ev_r(p_ft=p_ft, net_rr=rr)
    anti = evaluate_stage_pass(
        CurriculumStage.STAGE4_VIABLE_PLANT,
        **_base(  # type: ignore[arg-type]
            trades=150,
            wins=20,
            first_touch_hit_rate=p_ft,
            geometry_net_rr=rr,
            mean_r=e_mech + 0.5,
            occupancy=0.4,
        ),
    )
    assert anti.passed is False
    weak_r = evaluate_stage_pass(
        CurriculumStage.STAGE4_VIABLE_PLANT,
        **_base(  # type: ignore[arg-type]
            trades=150,
            wins=50,
            first_touch_hit_rate=p_ft,
            geometry_net_rr=rr,
            mean_r=e_mech - 0.5,
            occupancy=0.4,
        ),
    )
    assert weak_r.passed is False


def test_legacy_runway_stage_cannot_pass() -> None:
    result = evaluate_stage_pass(
        CurriculumStage.STAGE5_PROFIT_VAL,
        **_base(trades=400, wins=200),  # type: ignore[arg-type]
    )
    assert result.passed is False
    assert "legacy" in result.message


def test_receipt_without_v2_fields_fails_integrity() -> None:
    receipt = StagePassReceipt(
        stage="stage1_trend",
        trades=200,
        wins=80,
        winrate=0.4,
        required_trades=150,
        pass_criteria_id="closed_loop",
        provisional=False,
        passed_at="2026-08-14T00:00:00Z",
        engine_version="BRO-v2",
        schema="",
    )
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE1_TREND,
        receipt,
        cfg=_cfg(),
        training_mode="certified",
    )
    assert ok is False
    assert "schema" in reason


def test_artifacts_only_cannot_birth_exit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_birth_completed.flag").write_text("ok", encoding="utf-8")
    decision = evaluate_birth_exit(tmp_path)
    assert decision.exited is False
    assert "foundation_five_receipts_v2" in decision.missing


def test_flatten_theater_fails_settlement() -> None:
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        **_base(  # type: ignore[arg-type]
            closes_stop=5,
            closes_target=5,
            closes_time_stop=0,
            closes_flatten=180,
            closes_unknown=10,
        ),
    )
    assert result.passed is False
    assert "settlement" in result.message


def test_relocated_economic_viability_is_playground_not_birth() -> None:
    gate = economic_viability(mean_r=-0.3, skill_wr=0.30, breakeven_wr=0.425)
    assert gate.passed is False
    assert gate.home_phase == "playground"


def test_relocated_cert_oos_not_birth() -> None:
    gate = certificate_oos_walls(oos_wr=0.33, oos_sharpe=-4.0, max_dd_pct=11.7)
    assert gate.passed is False
    assert gate.home_phase == "proving_ground"
    assert CERT_OOS_WR_MIN == 0.48


def test_relocated_risk_discipline_is_apprenticeship() -> None:
    gate = risk_discipline(sharpe=0.05, max_dd_pct=18.0)
    assert gate.passed is False
    assert gate.home_phase == "apprenticeship"


def test_missing_calendar_days_fails_replay_cap() -> None:
    payload = _base()
    payload.pop("unique_calendar_days")
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        **payload,  # type: ignore[arg-type]
    )
    assert result.passed is False
    assert "replay" in result.message


def test_fail_closed_stage_ticks_never_falls_back_to_train() -> None:
    from lumina_core.birth.foundation_stages import fail_closed_stage_ticks

    train = [{"regime": "NEUTRAL", "last": 1.0} for _ in range(40)]
    assert fail_closed_stage_ticks(
        CurriculumStage.STAGE1_TREND, train_ticks=train
    ) == []
    assert fail_closed_stage_ticks(
        CurriculumStage.STAGE4_VIABLE_PLANT,
        train_ticks=train,
        validation_ticks=[],
    ) == []
    assert fail_closed_stage_ticks(
        CurriculumStage.STAGE5_PROBE_HANDOFF,
        train_ticks=train,
        holdout_ticks=[],
    ) == []


def test_stage4_passes_only_when_both_skill_legs_true() -> None:
    p_ft = 0.29
    rr = 1.35
    e_mech = mechanical_ev_r(p_ft=p_ft, net_rr=rr)
    both = evaluate_stage_pass(
        CurriculumStage.STAGE4_VIABLE_PLANT,
        **_base(  # type: ignore[arg-type]
            trades=150,
            wins=50,
            first_touch_hit_rate=p_ft,
            geometry_net_rr=rr,
            mean_r=e_mech,
            occupancy=0.4,
            unique_calendar_days=20,
        ),
    )
    assert both.passed is True
    edge_only = evaluate_stage_pass(
        CurriculumStage.STAGE4_VIABLE_PLANT,
        **_base(  # type: ignore[arg-type]
            trades=150,
            wins=50,
            first_touch_hit_rate=p_ft,
            geometry_net_rr=rr,
            mean_r=e_mech - 0.5,
            occupancy=0.4,
        ),
    )
    assert edge_only.passed is False


def test_stage5_holdout_pass_and_fitness_checksum(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from lumina_core.birth.fitness_vector import receipt_checksum
    from lumina_core.birth.progress import write_birth_progress

    result = evaluate_stage_pass(
        CurriculumStage.STAGE5_PROBE_HANDOFF,
        **_base(  # type: ignore[arg-type]
            trades=150,
            wins=50,
            occupancy=0.4,
            first_touch_hit_rate=0.28,
            oos_sharpe=-1.0,
            oos_dd_pct=10.0,
            unique_calendar_days=20,
        ),
    )
    assert result.passed is True
    receipts = [
        _v2_receipt("stage1_trend", occupancy=None),
        _v2_receipt("stage2_range"),
        _v2_receipt("stage3_mixed"),
        _v2_receipt("stage4_viable_plant"),
        _v2_receipt("stage5_probe_handoff", oos_sharpe=-1.25),
    ]
    (tmp_path / "state").mkdir()
    write_birth_progress(
        tmp_path,
        stage="foundation_handoff",
        phase="foundation_handoff",
        message="test",
        progress_pct=99.0,
        stage_pass_receipts=[r.to_dict() for r in receipts],
    )
    from lumina_core.birth.fitness_vector import BirthFitnessVector, write_fitness_vector

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
    decision = evaluate_birth_exit(tmp_path)
    assert decision.exited is True


def test_foundation_max_epochs_wired() -> None:
    from lumina_core.birth.curriculum import CurriculumStage
    from lumina_core.birth.foundation_epochs import epoch_cap_exceeded, note_foundation_epoch
    from lumina_core.birth.foundation_stages import foundation_max_epochs

    assert foundation_max_epochs(CurriculumStage.STAGE4_VIABLE_PLANT) == 2
    count, h = note_foundation_epoch(previous_hash="a", current_hash="a", previous_count=2)
    assert count == 3
    assert h == "a"
    assert epoch_cap_exceeded(CurriculumStage.STAGE4_VIABLE_PLANT, 3) is True
    assert epoch_cap_exceeded(CurriculumStage.STAGE1_TREND, 3) is False
    assert epoch_cap_exceeded(CurriculumStage.STAGE5_PROBE_HANDOFF, 9) is False


def test_s5_dd_equity_is_ssot() -> None:
    from lumina_core.birth.certificate_evaluator import (
        _peak_to_end_drawdown_pct,
        max_drawdown_pct,
    )
    from lumina_core.birth.foundation_metrics import S5_DD_EQUITY_USD, S5_DD_MAX_PCT
    from lumina_core.birth.runway import risk_metrics_from_pnl

    assert S5_DD_EQUITY_USD == 50_000.0
    assert S5_DD_MAX_PCT == 25.0
    _, dd = risk_metrics_from_pnl([-1000.0, -1000.0])
    assert dd == max_drawdown_pct([-1000.0, -1000.0], equity=S5_DD_EQUITY_USD)
    assert dd == pytest.approx(4.0)
    v_shape = [-5000.0, -5000.0, 8000.0]
    trough = max_drawdown_pct(v_shape, equity=S5_DD_EQUITY_USD)
    peak_end = _peak_to_end_drawdown_pct(v_shape, equity=S5_DD_EQUITY_USD)
    assert trough == pytest.approx(20.0)
    assert peak_end == pytest.approx(4.0)
    assert trough != pytest.approx(peak_end)


def _v2_receipt(stage: str, **kwargs: object) -> StagePassReceipt:
    from tests.birth.honest_settlement import honest_closes

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
        pass_criteria_id=str(kwargs.get("pass_criteria_id", "closed_loop")),
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


def test_complete_foundation_birth_requires_all_five_receipts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from types import SimpleNamespace

    from lumina_core.birth.foundation_complete import complete_foundation_birth

    host = SimpleNamespace(
        _stage_pass_receipts=[_v2_receipt("stage5_probe_handoff")],
        cumulative_trades=50,
        workspace_root=tmp_path,
    )
    out = complete_foundation_birth(
        host,
        training_mode="certified",
        trade_budget_cap=1000,
        practice_mode=False,
    )
    assert out["status"] == "foundation_incomplete"
    assert "stage1_trend" in str(out["failure_reason"])


def test_complete_foundation_birth_uses_s5_oos_sharpe(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from types import SimpleNamespace

    from lumina_core.birth.foundation_complete import complete_foundation_birth

    (tmp_path / "state").mkdir()
    receipts = [
        _v2_receipt("stage1_trend", occupancy=None),
        _v2_receipt("stage2_range"),
        _v2_receipt("stage3_mixed"),
        _v2_receipt("stage4_viable_plant"),
        _v2_receipt("stage5_probe_handoff", oos_sharpe=-1.25),
    ]

    class _Buf:
        def __len__(self) -> int:
            return 0

    host = SimpleNamespace(
        _stage_pass_receipts=receipts,
        cumulative_trades=900,
        workspace_root=tmp_path,
        birth_config=SimpleNamespace(
            curriculum=SimpleNamespace(polish_ppo_timesteps=100)
        ),
        buffer=_Buf(),
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
    out = complete_foundation_birth(
        host,
        training_mode="certified",
        trade_budget_cap=1000,
        practice_mode=False,
    )
    assert out["status"] == "completed"
    assert out["fitness_vector"]["oos_sharpe"] == -1.25
    assert out["fitness_vector"]["oos_sharpe"] != 0.0
