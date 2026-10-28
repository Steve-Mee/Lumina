"""Stage-1 stop physics: qty-normalized R, stop-fill, gap-fill. Gate stays 1.5R."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.birth_trade_geometry import SEGMENT_BREAK_KEY
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.foundation_metrics import (
    MEDIAN_LOSS_R_MAX,
    build_foundation_snapshot,
    intended_risk_usd,
    median_loss_r,
    process_r_ok,
    r_multiples,
    r_multiples_from_risk,
    stop_usd,
)
from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment
from lumina_core.rl.gym_stop_fill import (
    birth_force_qty_one,
    plan_birth_exit_fill,
    row_is_segment_gap,
)


def test_median_loss_r_gate_stays_1_5() -> None:
    assert MEDIAN_LOSS_R_MAX == pytest.approx(1.5)


@pytest.mark.unit
def test_qty8_fill_at_stop_is_one_r_not_eight() -> None:
    stop_pct = 0.000512
    entry = 7543.0
    qty = 8
    risk = intended_risk_usd(stop_pct=stop_pct, entry_price=entry, qty=qty)
    one_lot = stop_usd(stop_pct=stop_pct, ref_price=entry, qty=1)
    pnl = -risk  # exact stop, ignore costs
    rs = r_multiples_from_risk([pnl], [risk])
    lie = r_multiples([pnl], stop_usd_value=one_lot)
    assert median_loss_r(rs) == pytest.approx(1.0, abs=0.02)
    assert median_loss_r(lie) == pytest.approx(8.0, abs=0.05)
    snap = build_foundation_snapshot(
        trades=1,
        wins=0,
        r_series=rs,
        unique_calendar_days=40,
        settlement_ok=True,
        entropy_alive=True,
    )
    assert process_r_ok(snap.median_loss_r)
    lie_snap = build_foundation_snapshot(
        trades=1,
        wins=0,
        pnl_series=[pnl],
        stop_pct=stop_pct,
        ref_price=entry,
        qty=1,
        unique_calendar_days=40,
    )
    assert not process_r_ok(lie_snap.median_loss_r)


@pytest.mark.unit
def test_missing_r_series_after_volume_gate_fails_closed() -> None:
    snap = build_foundation_snapshot(
        trades=200,
        wins=50,
        r_series=[],
        unique_calendar_days=40,
        settlement_ok=True,
        entropy_alive=True,
        net_rr=1.4,
        p_ft=0.32,
    )
    assert snap.median_loss_r is None
    assert process_r_ok(snap.median_loss_r) is False
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=200,
        wins=50,
        hold_signals=40,
        total_signals=200,
        constitution_violations=0,
        target_trades=150,
        unique_calendar_days=40,
        r_series=[],
        geometry_net_rr=1.4,
        first_touch_hit_rate=0.32,
        closes_stop=140,
        closes_target=60,
        policy_entropy=0.4,
        ppo_steps=800,
    )
    assert result.passed is False
    assert "median_loss_r" in result.message


@pytest.mark.unit
def test_stop_fill_plan_non_gap_marks_stop_not_close() -> None:
    plan = plan_birth_exit_fill(
        hit_stop=True,
        hit_target=False,
        flatten=False,
        force_time=False,
        force_flat=False,
        close_price=7400.0,
        stop_price=7539.14,
        target_price=7560.0,
        is_gap=False,
    )
    assert plan is not None
    assert plan.reason == "stop"
    assert plan.mark_price == pytest.approx(7539.14)
    assert plan.gap is False


@pytest.mark.unit
def test_gap_fill_uses_close() -> None:
    plan = plan_birth_exit_fill(
        hit_stop=True,
        hit_target=False,
        flatten=False,
        force_time=False,
        force_flat=False,
        close_price=7400.0,
        stop_price=7539.14,
        target_price=7560.0,
        is_gap=True,
    )
    assert plan is not None
    assert plan.mark_price == pytest.approx(7400.0)
    assert plan.gap is True


@pytest.mark.unit
def test_same_bar_stop_beats_target() -> None:
    plan = plan_birth_exit_fill(
        hit_stop=True,
        hit_target=True,
        flatten=False,
        force_time=False,
        force_flat=False,
        close_price=7540.0,
        stop_price=7539.0,
        target_price=7541.0,
        is_gap=False,
    )
    assert plan is not None
    assert plan.reason == "stop"
    assert plan.mark_price == pytest.approx(7539.0)


@pytest.mark.unit
def test_segment_break_key_is_gap() -> None:
    assert row_is_segment_gap({SEGMENT_BREAK_KEY: True}) is True
    assert row_is_segment_gap({"close": 1.0}) is False


@pytest.mark.unit
def test_birth_force_qty_one_all_birth_stages() -> None:
    assert birth_force_qty_one("stage1_trend") is True
    assert birth_force_qty_one("trend") is True
    assert birth_force_qty_one("stage2_range") is True
    assert birth_force_qty_one("stage5_probe_handoff") is True


class _MarketDataStub:
    def get_tape_snapshot(self) -> dict[str, float]:
        return {
            "volume_delta": 0.0,
            "avg_volume_delta_10": 0.0,
            "bid_ask_imbalance": 1.0,
            "cumulative_delta_10": 0.0,
        }


class _EngineStub:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            instrument="MES JUN26",
            trade_mode="birth",
            risk_controller={},
        )
        self.market_data = _MarketDataStub()
        self.AI_DRAWN_FIBS: dict[str, object] = {}
        self.world_model: dict[str, object] = {}

    def detect_market_regime(self, _df: object) -> str:
        return "NEUTRAL"

    def get_current_dream_snapshot(self) -> dict[str, object]:
        return {
            "confidence": 0.0,
            "confluence_score": 0.0,
            "stop": 0.0,
            "target": 0.0,
            "fib_levels": {},
        }


def _flat_ticks(n: int = 80, price: float = 7543.0) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for i in range(n):
        rows.append(
            {
                "timestamp": f"2026-01-01T{i:04d}:00Z",
                "close": price,
                "last": price,
                "bid": price - 0.25,
                "ask": price + 0.25,
                "volume": 10,
                "regime": "NEUTRAL",
            }
        )
    return rows


def _run_until_close(
    *,
    gap: bool,
    qty_frac: float,
    force_qty_one: bool,
    min_dwell: int = 0,
) -> dict[str, object]:
    stop_pct = 0.000512
    entry = 7543.0
    env = RLTradingEnvironment(
        _EngineStub(),
        _flat_ticks(80, price=entry),
        config=RLConfig(
            trade_mode="birth",
            force_qty_one=force_qty_one,
            default_stop_pct=stop_pct,
            default_target_pct=stop_pct * 1.6,
            suppress_random_flatten=True,
            participation_min_dwell_bars=min_dwell,
            soft_prior_stops=False,
            max_steps=80,
        ),
    )
    env.reset()
    open_action = [1.0, qty_frac, stop_pct, stop_pct * 1.6]
    _obs, _rew, _done, _trunc, info = env.step(open_action)
    if not info.get("trade_closed") and int(getattr(env, "_position", 0) or 0) == 0:
        return info
    crash = 7400.0
    idx = int(getattr(env, "_idx", 1) or 1)
    for row in env.data[idx:]:
        row["close"] = crash
        row["last"] = crash
        if gap:
            row[SEGMENT_BREAK_KEY] = True
    hold = [0.0, qty_frac, stop_pct, stop_pct * 1.6]
    _obs, _rew, _done, _trunc, info = env.step(hold)
    return info


@pytest.mark.unit
def test_gym_close_through_stop_fills_at_stop_not_close() -> None:
    info = _run_until_close(gap=False, qty_frac=0.0, force_qty_one=True)
    assert info.get("trade_closed") is True
    assert info.get("close_reason") == "stop"
    trade_r = float(info.get("trade_r") or 0.0)
    assert abs(trade_r) <= 1.5 + 1e-9
    assert float(info.get("qty") or 0) == 1.0


@pytest.mark.unit
def test_gym_gap_fill_may_exceed_1_5r() -> None:
    info = _run_until_close(gap=True, qty_frac=0.0, force_qty_one=True)
    assert info.get("trade_closed") is True
    assert info.get("close_reason") == "stop"
    trade_r = float(info.get("trade_r") or 0.0)
    assert abs(trade_r) > 1.5


@pytest.mark.unit
def test_min_dwell_cannot_suppress_stop() -> None:
    info = _run_until_close(
        gap=False, qty_frac=0.0, force_qty_one=True, min_dwell=50
    )
    assert info.get("trade_closed") is True
    assert info.get("close_reason") == "stop"
    assert abs(float(info.get("trade_r") or 0.0)) <= 1.5 + 1e-9


@pytest.mark.unit
def test_gym_qty8_stop_fill_median_near_one_r() -> None:
    info = _run_until_close(gap=False, qty_frac=0.80, force_qty_one=False)
    assert info.get("trade_closed") is True
    assert int(info.get("qty") or 0) == 8
    trade_r = float(info.get("trade_r") or 0.0)
    assert abs(trade_r) <= 1.5 + 1e-9
    # 8-lot USD loss divided by 1-lot stop would be ~8R; qty-normalized is ~1R.
    risk = float(info.get("risk_usd") or 0.0)
    pnl = float(info.get("rl_close_accounting_net_usd") or 0.0)
    one_lot = intended_risk_usd(stop_pct=0.000512, entry_price=7543.0, qty=1)
    assert abs(pnl / max(one_lot, 1e-9)) > 4.0
    assert abs(pnl / max(risk, 1e-9)) <= 1.5 + 1e-9
