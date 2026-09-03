"""S5 notional cap (Gate 0) + occupancy re-arm/seed (Gate 1). Floors stay pinned."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest

from lumina_core.birth.birth_trade_geometry import (
    MES_POINT_VALUE_USD,
    MES_TICK_SIZE,
    SEGMENT_BREAK_KEY,
    BirthTradeGeometry,
)
from lumina_core.birth.certificate_evaluator import max_drawdown_pct
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.force_open_plant import apply_force_open_stop
from lumina_core.birth.foundation_metrics import (
    S5_DD_EQUITY_USD,
    S5_DD_MAX_PCT,
    intended_risk_usd,
)
from lumina_core.birth.notional_cap import (
    birth_close_cap_usd,
    birth_exam_book_limit_usd,
    birth_stop_pct_dollar_cap,
    clip_birth_exam_pnl,
    one_tick_usd,
)
from lumina_core.birth.runway import risk_metrics_from_pnl
from lumina_core.birth.s5_occupancy_continuity import (
    REARM_HYST,
    apply_s5_occupancy_seed,
    s4_occupancy_in_s5_exam_band,
)
from lumina_core.birth.stage2_participation_envelope import (
    MODE_FORCE_OPEN,
    MODE_PASSTHROUGH,
    decide_stage2_participation,
)
from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment
from lumina_core.rl.gym_stop_fill import birth_force_qty_one
from tests.birth.test_s5_shared_imu import _envelope_decision


def test_a_floors_still_pinned() -> None:
    assert S5_DD_EQUITY_USD == 50_000.0
    assert S5_DD_MAX_PCT == 25.0


def test_a_force_qty_one_live_on_shadow_rollout_config() -> None:
    src = Path("lumina_core/birth/sim_runner.py").read_text(encoding="utf-8")
    assert "force_qty_one=bool(birth_force_qty_one" in src
    assert birth_force_qty_one("stage5_probe_handoff") is True
    assert birth_force_qty_one("stage4_viable_plant") is True
    assert birth_force_qty_one("stage2_range") is True


class _MarketDataStub:
    def get_tape_snapshot(self) -> dict[str, float]:
        return {
            "volume_delta": 0.0,
            "avg_volume_delta_10": 0.0,
            "bid_ask_imbalance": 1.0,
            "cumulative_delta_10": 0.0,
        }


class _EngineStub:
    def __init__(self, instrument: str = "MES JUN26") -> None:
        self.config = SimpleNamespace(
            instrument=instrument,
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


def _ticks(n: int, price: float) -> list[dict[str, object]]:
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


def _open_then_mark(
    *,
    entry: float,
    mark: float,
    qty_frac: float,
    gap: bool,
    force_qty_one: bool = True,
) -> dict[str, object]:
    stop_pct = 0.003385
    env = RLTradingEnvironment(
        _EngineStub(),
        _ticks(80, price=entry),
        config=RLConfig(
            trade_mode="birth",
            force_qty_one=force_qty_one,
            default_stop_pct=stop_pct,
            default_target_pct=stop_pct * 1.6,
            suppress_random_flatten=True,
            soft_prior_stops=False,
            max_steps=80,
        ),
    )
    env.reset()
    env.step([1.0, qty_frac, stop_pct, stop_pct * 1.6])
    idx = int(getattr(env, "_idx", 1) or 1)
    for row in env.data[idx:]:
        row["close"] = mark
        row["last"] = mark
        if gap:
            row[SEGMENT_BREAK_KEY] = True
    _obs, _rew, _done, _trunc, info = env.step([0.0, qty_frac, stop_pct, stop_pct * 1.6])
    return info


def test_a_gym_action_qty_frac_one_still_fills_qty_one() -> None:
    info = _open_then_mark(
        entry=29539.75, mark=29400.0, qty_frac=1.0, gap=False, force_qty_one=True
    )
    assert info.get("trade_closed") is True
    assert int(info.get("qty") or 0) == 1


def test_a_force_open_stop_qty10_is_ten_times_tighter() -> None:
    action = np.array([1.0, 1.0, 0.01, 0.02], dtype=np.float32)
    row = {"close": 20000.0, "last": 20000.0, "trend_atr_norm": 0.02}
    geo = BirthTradeGeometry(stop_pct=0.0012, target_pct=0.0020, source="test")
    _a1, s1 = apply_force_open_stop(
        action, row, geo, min_dwell_bars=8, equity=50_000.0, qty=1
    )
    _a10, s10 = apply_force_open_stop(
        action, row, geo, min_dwell_bars=8, equity=50_000.0, qty=10
    )
    assert s10 == pytest.approx(s1 / 10.0, rel=1e-9)
    assert float(_a1[1]) == 0.0
    assert float(_a10[1]) == 0.0
    assert birth_force_qty_one("stage5_probe_handoff") is True


def test_a_gap_mark_ten_pct_books_exam_cap_not_raw() -> None:
    entry = 29539.75
    mark = entry * 0.90
    info = _open_then_mark(entry=entry, mark=mark, qty_frac=1.0, gap=True)
    assert info.get("trade_closed") is True
    booked = float(info.get("rl_close_accounting_net_usd") or 0.0)
    tick = one_tick_usd()
    assert abs(booked) <= S5_DD_EQUITY_USD * 0.01 + tick + 1e-9
    raw_if_nq20 = abs(mark - entry) * 20.0
    assert raw_if_nq20 > 10_000.0
    assert abs(booked) < raw_if_nq20


def test_a_intended_risk_dollar_cap_is_500() -> None:
    px = 29539.75
    stop = birth_stop_pct_dollar_cap(price=px, qty=1, equity=S5_DD_EQUITY_USD)
    risk = intended_risk_usd(stop_pct=stop, entry_price=px, qty=1, point_value=MES_POINT_VALUE_USD)
    assert risk == pytest.approx(500.0, abs=one_tick_usd())


def test_a_hundred_clipped_losses_are_100pct_of_50k() -> None:
    series = [-500.0] * 100
    _sharpe, dd = risk_metrics_from_pnl(series)
    assert dd == pytest.approx(100.0)
    assert dd == max_drawdown_pct(series, equity=S5_DD_EQUITY_USD)


def test_a_unit_test_fails_if_birth_close_books_over_cap() -> None:
    limit = birth_exam_book_limit_usd(entry_price=29539.75, qty=1)
    assert limit == pytest.approx(500.0 + MES_TICK_SIZE * MES_POINT_VALUE_USD)
    clipped = clip_birth_exam_pnl(-1_053_820.80, entry_price=29539.75, qty=1)
    assert abs(clipped) <= limit + 1e-12
    assert birth_close_cap_usd(entry_price=29539.75, qty=1) == pytest.approx(500.0)


def test_c_s5_seed_in_band_first_decision_passthrough() -> None:
    loop = SimpleNamespace(
        stage=CurriculumStage.STAGE5_PROBE_HANDOFF,
        host=SimpleNamespace(
            _stage_pass_receipts=[
                SimpleNamespace(stage="stage4_viable_plant", occupancy=0.476)
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
    assert loop.occupancy_control_flat == pytest.approx(0.476)
    assert loop.occupancy_in_band_seen is True
    d = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=float(loop.occupancy_control_flat),
        range_total_signals=int(loop.stage_range_total_signals),
        position=0,
        bars_in_position=0,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        cumulative_in_band_passthrough=True,
        in_band_seen=bool(loop.occupancy_in_band_seen),
        rearm_hysteresis=REARM_HYST,
    )
    assert d.mode == MODE_PASSTHROUGH
    assert d.mode != MODE_FORCE_OPEN


def test_c_s5_seed_missing_or_out_of_band_still_bootstraps() -> None:
    missing = SimpleNamespace(
        stage=CurriculumStage.STAGE5_PROBE_HANDOFF,
        host=SimpleNamespace(_stage_pass_receipts=[]),
        stage_range_total_signals=0,
        stage_range_flat_bars=0,
        occupancy_control_flat=0.0,
        occupancy_in_band_seen=False,
        occupancy_seed_source="n/a",
        occupancy_seed_value=None,
    )
    assert apply_s5_occupancy_seed(missing) == "missing"
    assert missing.occupancy_in_band_seen is False
    oob = SimpleNamespace(
        stage=CurriculumStage.STAGE5_PROBE_HANDOFF,
        host=SimpleNamespace(
            _stage_pass_receipts=[
                SimpleNamespace(stage="stage4_viable_plant", occupancy=0.90)
            ]
        ),
        stage_range_total_signals=0,
        stage_range_flat_bars=0,
        occupancy_control_flat=0.0,
        occupancy_in_band_seen=False,
        occupancy_seed_source="n/a",
        occupancy_seed_value=None,
    )
    assert apply_s5_occupancy_seed(oob) == "s4_out_of_band"
    d = _envelope_decision(
        CurriculumStage.STAGE5_PROBE_HANDOFF, cumulative_flat=1.0, position=0
    )
    assert d.mode == MODE_FORCE_OPEN
    assert s4_occupancy_in_s5_exam_band(0.90) is False


def test_c_rearm_hysteresis_after_in_band() -> None:
    common = dict(
        enabled=True,
        range_total_signals=8000,
        position=0,
        bars_in_position=0,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        cumulative_in_band_passthrough=True,
        in_band_seen=True,
        rearm_hysteresis=REARM_HYST,
    )
    mid = decide_stage2_participation(range_flat_ratio=0.73, **common)
    assert mid.mode != MODE_FORCE_OPEN
    hi = decide_stage2_participation(range_flat_ratio=0.77, **common)
    assert hi.mode == MODE_FORCE_OPEN
    band = decide_stage2_participation(range_flat_ratio=0.55, **common)
    assert band.mode == MODE_PASSTHROUGH


def test_c_in_band_passthrough_ignores_rearm_and_refractory() -> None:
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
        in_band_seen=True,
        rearm_hysteresis=REARM_HYST,
    )
    assert d.mode == MODE_PASSTHROUGH


def test_c_s4_first_force_open_still_fires() -> None:
    d = _envelope_decision(
        CurriculumStage.STAGE4_VIABLE_PLANT, cumulative_flat=1.0, position=0
    )
    assert d.mode == MODE_FORCE_OPEN


def test_no_idle_regimes_or_plant_cap_kruk() -> None:
    forbidden = ("S5_IDLE_REGIMES", "MAX_PLANT", "MAX_S5_PLANT", "MAX_FORCE_OPEN")
    for rel in (
        "lumina_core/birth/stage3_inband_idle.py",
        "lumina_core/birth/stage2_participation_envelope.py",
        "lumina_core/birth/s5_occupancy_continuity.py",
        "lumina_core/birth/foundation_metrics.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in src
