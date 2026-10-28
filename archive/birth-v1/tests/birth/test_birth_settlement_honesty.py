"""Settlement honesty + Birth gym RNG-flatten lock (live forensics 2026-08-13)."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from lumina_core.birth.birth_trade_geometry import economic_skill_gap
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_terminal_traps import detect_hold_trap
from lumina_core.birth.stage2_participation_envelope import MODE_PASSTHROUGH, decide_stage2_participation
from lumina_core.birth.starship_edgescore_core import (
    evaluate_settlement_honesty,
    settlement_progress_fields,
)
from lumina_core.birth.starship_edgescore_stage3 import evaluate_stage3_edgescore
from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment
from tests.birth.honest_settlement import honest_closes


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _flat_ticks(n: int = 200, price: float = 5000.0) -> list[dict[str, object]]:
    ticks: list[dict[str, object]] = []
    for i in range(n):
        ticks.append(
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
    return ticks


class _Runtime:
    config = SimpleNamespace(instrument="MES", trade_mode="birth")


@pytest.mark.unit
def test_settlement_fails_when_volume_met_and_ssot_missing() -> None:
    ok, share, reason = evaluate_settlement_honesty(trades=500, required=500)
    assert ok is False
    assert share == 0.0
    assert "missing" in reason


@pytest.mark.unit
def test_settlement_warmup_before_volume() -> None:
    ok, share, reason = evaluate_settlement_honesty(trades=20, required=500)
    assert ok is True
    assert share == pytest.approx(-1.0)
    assert reason == "warmup"


@pytest.mark.unit
def test_settlement_progress_fields_warmup_share_is_null() -> None:
    fields = settlement_progress_fields()
    assert fields["stage_settlement_share"] is None
    assert fields["stage_closes_stop_cum"] == 0
    assert fields["stage_closes_unknown_cum"] == 0


@pytest.mark.unit
def test_settlement_progress_fields_honest_share() -> None:
    fields = settlement_progress_fields(
        closes_stop=555,
        closes_target=217,
        closes_time_stop=12,
        closes_flatten=0,
        closes_unknown=0,
    )
    assert fields["stage_settlement_share"] == pytest.approx(1.0)
    assert fields["stage_closes_time_stop_cum"] == 12


@pytest.mark.unit
def test_settlement_fails_flatten_dominant() -> None:
    closes = honest_closes(500, flatten_share=0.90)
    ok, share, reason = evaluate_settlement_honesty(
        trades=500, required=500, min_share=0.70, **closes
    )
    assert ok is False
    assert share < 0.70
    assert "share" in reason


@pytest.mark.unit
def test_settlement_passes_stop_target_majority() -> None:
    closes = honest_closes(500)
    ok, share, reason = evaluate_settlement_honesty(
        trades=500, required=500, min_share=0.70, **closes
    )
    assert ok is True
    assert share >= 0.70
    assert reason == "ok"


@pytest.mark.unit
def test_stage3_fails_flatten_theater_even_with_hygiene() -> None:
    """WR 40% + flat 32% + flatten-share 90% must not pass."""
    cfg = _cfg()
    r = evaluate_stage3_edgescore(
        trades=500,
        wins=200,
        hold_signals=300,
        total_signals=1000,
        constitution_violations=0,
        required=500,
        cfg=cfg,
        rolling_winrate=0.40,
        hold_ratio=0.50,
        range_flat_ratio=0.32,
        range_total_signals=1000,
        range_round_trips=500,
        **honest_closes(500, flatten_share=0.90),
    )
    assert r.passed is False
    assert r.activity_ok is False
    assert "settlement" in r.message


@pytest.mark.unit
def test_stage3_passes_high_hold_when_occupancy_and_settlement_honest() -> None:
    """Hold 88% is geometry, not a gate — occupancy + settlement carry activity."""
    cfg = _cfg()
    r = evaluate_stage3_edgescore(
        trades=500,
        wins=180,  # 36% durable lifetime
        hold_signals=880,
        total_signals=1000,
        constitution_violations=0,
        required=500,
        cfg=cfg,
        rolling_winrate=0.36,
        hold_ratio=0.88,
        range_flat_ratio=0.32,
        range_total_signals=1000,
        range_round_trips=500,
        **honest_closes(500),
    )
    assert r.passed is True
    assert r.activity_ok is True


@pytest.mark.unit
def test_stage3_fails_under_activity_flat() -> None:
    cfg = _cfg()
    r = evaluate_stage3_edgescore(
        trades=500,
        wins=200,
        hold_signals=200,
        total_signals=1000,
        constitution_violations=0,
        required=500,
        cfg=cfg,
        rolling_winrate=0.40,
        hold_ratio=0.20,
        range_flat_ratio=0.80,
        range_total_signals=1000,
        range_round_trips=500,
        **honest_closes(500),
    )
    assert r.passed is False
    assert "under-activity" in r.message


@pytest.mark.unit
def test_stage3_fails_over_trading_flat() -> None:
    cfg = _cfg()
    r = evaluate_stage3_edgescore(
        trades=500,
        wins=200,
        hold_signals=300,
        total_signals=1000,
        constitution_violations=0,
        required=500,
        cfg=cfg,
        rolling_winrate=0.40,
        hold_ratio=0.30,
        range_flat_ratio=0.03,
        range_total_signals=1000,
        range_round_trips=500,
        **honest_closes(500),
    )
    assert r.passed is False
    assert "over-trading" in r.message


@pytest.mark.unit
def test_birth_gym_hold_does_not_rng_flatten() -> None:
    """Birth SIM: HOLD bars must not close via 5% RNG flatten."""
    np.random.seed(0)
    data = _flat_ticks(160)
    cfg = RLConfig(
        trade_mode="birth",
        max_steps=150,
        suppress_random_flatten=False,
        participation_min_dwell_bars=0,
        range_patience_active=False,
    )
    env = RLTradingEnvironment(_Runtime(), data, config=cfg)
    env.reset()
    open_action = np.array([1.0, 0.5, 0.0076, 0.0131], dtype=np.float32)
    env.step(open_action)
    assert int(env._position) != 0
    hold = np.array([0.0, 0.5, 0.0076, 0.0131], dtype=np.float32)
    for _ in range(80):
        _obs, _reward, terminated, truncated, info = env.step(hold)
        assert int(env._position) != 0, "Birth HOLD must not RNG-flatten"
        assert str(info.get("close_reason") or "") == ""
        if terminated or truncated:
            break
    assert int(env._position) != 0


@pytest.mark.unit
def test_economic_skill_gap_positive_when_below_breakeven() -> None:
    assert economic_skill_gap(be_wr=0.433, skill_wr=0.30) == pytest.approx(0.133)
    assert economic_skill_gap(be_wr=0.433, skill_wr=0.48) == pytest.approx(0.0)


@pytest.mark.unit
def test_hold_trap_suppressed_when_occupancy_in_band() -> None:
    cfg = _cfg()
    assert (
        detect_hold_trap(
            hold_ratio=0.90,
            winrate=0.30,
            pass_metric_target=0.45,
            velocity_stall=True,
            cfg=cfg,
            range_flat_ratio=0.32,
        )
        is False
    )
    assert (
        detect_hold_trap(
            hold_ratio=0.90,
            winrate=0.30,
            pass_metric_target=0.45,
            velocity_stall=True,
            cfg=cfg,
            range_flat_ratio=0.90,
        )
        is True
    )


@pytest.mark.unit
def test_stage3_envelope_passthrough_in_band_no_sticky_pin() -> None:
    """flat=0.32 with band 0.28–0.72 and hyst 0.0 must PASSTHROUGH (not FORCE_HOLD)."""
    decision = decide_stage2_participation(
        enabled=True,
        range_flat_ratio=0.32,
        range_total_signals=200,
        position=1,
        bars_in_position=10,
        stop_pct=0.0076,
        target_pct=0.0131,
        qty_frac=0.5,
        band_lo=0.28,
        band_hi=0.72,
        hysteresis=0.0,
        under_band_release_hysteresis=0.0,
        min_signals=50,
        min_dwell_bars=8,
        max_hold_bars=120,
    )
    assert decision.mode == MODE_PASSTHROUGH
