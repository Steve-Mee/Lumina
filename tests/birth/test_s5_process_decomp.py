"""S5 process decomp: G0 invariants + Gate 1 M2 process-R. Floors stay pinned."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.birth_trade_geometry import (
    MES_POINT_VALUE_USD,
    MES_TICK_SIZE,
    SEGMENT_BREAK_KEY,
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
    S3_OCCUPANCY_MAX,
    S3_OCCUPANCY_MIN,
    S5_DD_EQUITY_USD,
    S5_DD_MAX_PCT,
    S5_EDGE_MIN,
    S5_MIN_TRADES,
    S5_SHARPE_FLOOR,
    build_foundation_snapshot,
)
from lumina_core.birth.foundation_pass import evaluate_foundation_pass
from lumina_core.birth.notional_cap import (
    birth_fill_pnl_usd,
    birth_gym_point_value,
    clip_birth_exam_pnl,
)
from lumina_core.birth.s5_close_ledger_trace import REGIME_JOIN_KEY, close_ledger_row
from lumina_core.birth.s5_process_decomp import (
    PRE_GATE1_REWARD_CLASS,
    birth_close_process_r,
    classify_live_close_reward,
    evaluate_triggers,
    exit_table,
    target_clean_count,
)
from lumina_core.maturity.birth_exit import is_birth_exit_sufficient
from lumina_core.rl.gym_stop_fill import birth_force_qty_one, plan_birth_exit_fill
from lumina_core.rl.reward_shaper import (
    RewardShapingState,
    TradeCloseContext,
    compute_expectancy_reward,
)
from tests.birth.test_s5_notional_cap import _open_then_mark
from tests.birth.test_s5_shared_imu import (
    _envelope_decision,
    _v2_receipt,
    _write_five_receipts,
)


def test_a_floors_and_mes_ssot_pinned() -> None:
    assert MES_POINT_VALUE_USD == 5.0
    assert S5_DD_EQUITY_USD == 50_000.0
    assert S5_DD_MAX_PCT == 25.0
    assert S5_SHARPE_FLOOR == pytest.approx(-2.0)
    assert S5_EDGE_MIN == pytest.approx(-0.03)
    assert POLICY_EDGE_MIN_TRADES == 150
    assert S5_MIN_TRADES == 50
    assert S3_OCCUPANCY_MIN == pytest.approx(0.25)
    assert S3_OCCUPANCY_MAX == pytest.approx(0.75)
    assert birth_gym_point_value() == pytest.approx(5.0)
    assert birth_force_qty_one("stage5_probe_handoff") is True
    src = Path("lumina_core/birth/sim_runner.py").read_text(encoding="utf-8")
    assert "force_qty_one=bool(birth_force_qty_one" in src


def test_a_qty1_delta10_books_fifty_before_clip() -> None:
    raw = birth_fill_pnl_usd(entry_price=20000.0, exit_price=20010.0, side=1, quantity=1)
    assert raw == pytest.approx(50.0)
    assert raw != pytest.approx(200.0)


def test_a_200pt_adverse_gap_books_cap() -> None:
    raw = birth_fill_pnl_usd(entry_price=23000.0, exit_price=22800.0, side=1, quantity=1)
    assert raw == pytest.approx(-1000.0)
    booked = clip_birth_exam_pnl(raw, entry_price=23000.0, qty=1)
    assert booked == pytest.approx(-501.25)


def test_b_s2_cum_still_force_open() -> None:
    d = _envelope_decision(
        CurriculumStage.STAGE2_RANGE, cumulative_flat=0.903, rolling_flat=0.50, position=0
    )
    assert d.mode == "FORCE_OPEN"


def test_b_s3_s4_s5_inband_passthrough() -> None:
    for stage in (
        CurriculumStage.STAGE3_MIXED,
        CurriculumStage.STAGE4_VIABLE_PLANT,
        CurriculumStage.STAGE5_PROBE_HANDOFF,
    ):
        d = _envelope_decision(stage, cumulative_flat=0.50, position=0)
        assert d.mode == "PASSTHROUGH"


def test_b_s5_seed_and_rearm() -> None:
    from lumina_core.birth.s5_occupancy_continuity import apply_s5_occupancy_seed
    from lumina_core.birth.stage2_participation_envelope import decide_stage2_participation

    loop = SimpleNamespace(
        stage=CurriculumStage.STAGE5_PROBE_HANDOFF,
        host=SimpleNamespace(
            _stage_pass_receipts=[
                SimpleNamespace(stage="stage4_viable_plant", occupancy=0.50)
            ]
        ),
        stage_range_total_signals=0,
        stage_range_flat_bars=0,
        occupancy_control_flat=0.0,
        occupancy_in_band_seen=False,
        occupancy_seed_source="n/a",
        occupancy_seed_value=None,
    )
    assert apply_s5_occupancy_seed(loop) == "s4_receipt"
    in_band = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.73,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.25,
        band_hi=0.75,
        hysteresis=0.04,
        under_band_release_hysteresis=0.04,
        min_signals=50,
        cumulative_in_band_passthrough=True,
        in_band_seen=True,
    )
    assert in_band.mode == "PASSTHROUGH"
    over = _envelope_decision(
        CurriculumStage.STAGE5_PROBE_HANDOFF, cumulative_flat=0.77, position=0
    )
    assert over.mode == "FORCE_OPEN"


def test_b_refractory_and_plant_tag() -> None:
    from lumina_core.birth.force_open_plant import ForceOpenChatterBound
    from lumina_core.birth.stage3_inband_idle import plant_tag_for_entry

    chatter = ForceOpenChatterBound()
    chatter.on_bar(trade_closed=True, closed_was_plant=True)
    assert chatter.blocks(8) is True
    chatter.on_bar(trade_closed=False, closed_was_plant=False)
    assert chatter.blocks(8) is True
    assert plant_tag_for_entry(force_open_this_step=True) is True
    assert plant_tag_for_entry(force_open_this_step=False) is False


def test_c_m1_not_shipped_flag_honest() -> None:
    clean = plan_birth_exit_fill(
        hit_stop=False,
        hit_target=True,
        flatten=False,
        force_time=False,
        force_flat=False,
        close_price=20100.0,
        stop_price=19900.0,
        target_price=20050.0,
        is_gap=False,
    )
    assert clean is not None
    assert clean.gap is False
    assert clean.reason == "target"
    assert clean.mark_price == pytest.approx(20050.0)
    gapped = plan_birth_exit_fill(
        hit_stop=False,
        hit_target=True,
        flatten=False,
        force_time=False,
        force_flat=False,
        close_price=20200.0,
        stop_price=19900.0,
        target_price=20050.0,
        is_gap=True,
    )
    assert gapped is not None
    assert gapped.gap is True
    assert gapped.mark_price == pytest.approx(20200.0)
    both = plan_birth_exit_fill(
        hit_stop=True,
        hit_target=True,
        flatten=False,
        force_time=False,
        force_flat=False,
        close_price=20000.0,
        stop_price=19950.0,
        target_price=20050.0,
        is_gap=False,
    )
    assert both is not None
    assert both.reason == "stop"
    src = Path("lumina_core/rl/gym_stop_fill.py").read_text(encoding="utf-8")
    assert "row_is_segment_gap" in src
    assert SEGMENT_BREAK_KEY in Path("lumina_core/birth/birth_trade_geometry.py").read_text(
        encoding="utf-8"
    )


def test_c_m2_birth_close_equals_process_r() -> None:
    win = birth_close_process_r(307.30, 308.0)
    loss = birth_close_process_r(-307.30, 308.0)
    cap = birth_close_process_r(501.25, 298.12)
    assert win == pytest.approx(307.30 / 308.0)
    assert loss == pytest.approx(-307.30 / 308.0)
    assert cap == pytest.approx(501.25 / 298.12)
    info, _env = _open_then_mark(
        entry=23000.0, mark=23120.0, qty_frac=1.0, gap=False, stop_pct=0.00268
    )
    assert info.get("trade_closed") is True
    booked = float(info.get("rl_close_accounting_net_usd") or 0.0)
    risk = float(info.get("risk_usd") or 0.0)
    expected = birth_close_process_r(booked, risk)
    assert float(info.get("training_reward") or 0.0) == pytest.approx(expected)
    comps = info.get("reward_components") or {}
    assert comps.get("process_r") == pytest.approx(expected)


def test_c_m2_non_birth_expectancy_unchanged() -> None:
    ctx = TradeCloseContext(
        net_pnl=50.0,
        equity=50_000.0,
        stop_pct=0.00268,
        side=1,
        risk_usd=308.0,
    )
    state = RewardShapingState()
    from lumina_core.birth.config import BirthRewardConfig

    cfg = BirthRewardConfig(
        enabled=True,
        expectancy_coeff=0.5,
        loss_asymmetry_coeff=1.25,
        volatility_penalty_coeff=0.0,
        trend_align_bonus_coeff=0.0,
        drawdown_penalty_coeff=0.0,
        sharpe_bonus_coeff=0.0,
    )
    shaped, _ = compute_expectancy_reward(ctx, state, cfg)
    process = birth_close_process_r(50.0, 308.0)
    assert shaped != pytest.approx(process)
    info, env = _open_then_mark(
        entry=23000.0,
        mark=23120.0,
        qty_frac=1.0,
        gap=False,
        stop_pct=0.00268,
        trade_mode="sim",
        instrument="NQ SEP26",
    )
    assert env.trade_mode == "sim"
    if info.get("trade_closed"):
        raw_comps = info.get("reward_components")
        comps = raw_comps if isinstance(raw_comps, dict) else {}
        assert "process_r" not in comps


def test_c_gate1_is_m2_not_m1_m3_m4() -> None:
    src_step = Path("lumina_core/rl/gym_environment_step.py").read_text(encoding="utf-8")
    src_close = Path("lumina_core/rl/gym_birth_close.py").read_text(encoding="utf-8")
    assert "birth_close_process_r" in src_close
    assert "training_reward_after_book" in src_step
    assert "S5_IDLE_REGIMES" not in src_step
    assert classify_live_close_reward() == PRE_GATE1_REWARD_CLASS
    assert PRE_GATE1_REWARD_CLASS == "mixed"


def test_c_ledger_trace_keeps_regime_and_reward() -> None:
    row = close_ledger_row(
        {
            "pnl": -307.3,
            "qty": 1,
            "cap_usd": 500.0,
            "close_reason": "stop",
            "gap": False,
            "plant_entry": False,
            "entry_price": 23000.0,
            "risk_usd": 308.0,
            "trade_r": -1.0,
            "point_value": 5.0,
            "regime": "TREND_DOWN",
            "reward": -1.0,
        }
    )
    assert row["regime"] == "TREND_DOWN"
    assert row["reward_on_close"] == pytest.approx(-1.0)
    assert row["intended_risk_usd"] == pytest.approx(308.0)
    assert row["point_value"] == pytest.approx(5.0)
    assert "sim_runner.py:704" in REGIME_JOIN_KEY


def test_c_g0_tables_and_m2_trigger() -> None:
    rows = [
        {
            "pnl": 501.25,
            "close_reason": "target",
            "gap": True,
            "trade_r": 1.6,
            "cap_usd": 500.0,
            "regime": "TREND_UP",
        },
        {
            "pnl": -307.3,
            "close_reason": "stop",
            "gap": False,
            "trade_r": -1.0,
            "cap_usd": 500.0,
            "regime": "TREND_DOWN",
        },
        {
            "pnl": -80.0,
            "close_reason": "time_stop",
            "gap": False,
            "trade_r": -0.26,
            "cap_usd": 500.0,
            "regime": "NEUTRAL",
        },
    ]
    g0a = exit_table(rows)
    assert g0a["target"]["n"] == 1
    assert target_clean_count(rows) == 0
    trig = evaluate_triggers(rows, p_ft=0.321, force_open=0, gap_flag_honest=True)
    assert trig["m1_indicated"] is False
    assert trig["m1_count_trip"] is True
    assert trig["m2_indicated"] is True
    assert trig["gate1"] == "M2"


def test_d_policy_149_cannot_pass() -> None:
    snap = build_foundation_snapshot(
        trades=149,
        wins=70,
        skill_trades=149,
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
    assert decision.passed is False
    assert "policy_sample" in decision.message
    assert "149" in decision.message


def test_d_policy_150_common_body_can_pass() -> None:
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


def test_d_failing_s5_does_not_write_fitness(tmp_path: Path) -> None:
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
    assert not (tmp_path / "state" / "lumina_birth_fitness_vector.json").is_file()


def test_d_five_receipts_matching_vector_exits(tmp_path: Path) -> None:
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


def test_d_missing_vector_and_checksum_mismatch(tmp_path: Path) -> None:
    receipts = _write_five_receipts(tmp_path)
    assert is_birth_exit_sufficient(tmp_path) is False
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


def test_e_forbidden_krukken_and_floors_grep() -> None:
    forbidden = (
        "S5_IDLE_REGIMES",
        "MAX_PLANT",
        "MAX_S5_PLANT",
        "MAX_TIME_STOP",
        "if synthetic",
    )
    files = [
        "lumina_core/birth/foundation_metrics.py",
        "lumina_core/birth/s5_process_decomp.py",
        "lumina_core/birth/s5_close_ledger_trace.py",
        "lumina_core/rl/gym_environment_step.py",
        "lumina_core/rl/gym_birth_close.py",
        "lumina_core/rl/gym_stop_fill.py",
        "lumina_core/birth/sim_runner.py",
        "lumina_core/birth/stage3_inband_ssot.py",
    ]
    for rel in files:
        src = Path(rel).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in src
    metrics = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "S5_SHARPE_FLOOR = -2.0" in metrics
    assert "S5_DD_MAX_PCT = 25.0" in metrics
    assert "S5_DD_EQUITY_USD = 50_000.0" in metrics
    assert "S5_EDGE_MIN = -0.03" in metrics
    assert MES_TICK_SIZE == pytest.approx(0.25)
