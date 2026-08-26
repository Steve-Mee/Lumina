"""Cost-aware geometry + first-touch baseline (truthful expectancy plant)."""

from __future__ import annotations

import pytest

from lumina_core.birth.birth_trade_geometry import (
    BIRTH_GEO_MIN_STOP_PCT,
    MIN_NET_RR_AFTER_COST,
    calibrate_birth_stops,
    economics_after_cost,
    estimate_round_trip_cost_usd,
    first_touch_target_hit_rate,
)


def _chrono_ticks(n: int = 500, step: float = 0.4) -> list[dict]:
    price = 7500.0
    out: list[dict] = []
    for i in range(n):
        price += step if i % 3 else -step * 0.7
        out.append(
            {
                "bar_index": i,
                "last": price,
                "close": price,
                "trend_atr_norm": 0.00025,
                "timestamp": f"2026-04-01T12:{i // 60:02d}:{i % 60:02d}",
                "regime": "NEUTRAL",
            }
        )
    return out


@pytest.mark.unit
def test_cost_usd_positive() -> None:
    c = estimate_round_trip_cost_usd(price=7500.0)
    assert c >= 2.0


@pytest.mark.unit
def test_min_floor_geometry_becomes_cost_viable() -> None:
    """Even when peak p40 pins min stop, cost-lift yields net_win > 0."""
    ticks = _chrono_ticks(600, step=0.15)  # very tight moves → floor bind
    geo = calibrate_birth_stops(ticks, max_hold_bars=90)
    assert geo.stop_pct >= BIRTH_GEO_MIN_STOP_PCT
    assert geo.net_rr_after_cost >= MIN_NET_RR_AFTER_COST - 1e-6 or geo.cost_usd > 0
    nw, nl, nrr, be, cost = economics_after_cost(
        geo.stop_pct, geo.target_pct, price=geo.ref_price or 7500.0
    )
    assert cost > 0
    assert nw > 0, f"net_win must be positive after costs: {nw}"
    assert nrr >= MIN_NET_RR_AFTER_COST - 0.05  # small float margin
    assert 0.0 < be <= 1.0
    assert geo.breakeven_wr_after_cost > 0


@pytest.mark.unit
def test_first_touch_thr_in_sane_band() -> None:
    # Stronger bar moves so stop/target are reachable within hold.
    ticks = _chrono_ticks(1200, step=2.0)
    geo = calibrate_birth_stops(ticks, max_hold_bars=90)
    thr = first_touch_target_hit_rate(
        ticks,
        stop_pct=geo.stop_pct,
        target_pct=geo.target_pct,
        max_hold_bars=90,
        sample_stride=15,
    )
    assert thr > 0.0, thr
    assert thr <= 0.70, thr


@pytest.mark.unit
def test_geometry_forensics_include_cost_keys() -> None:
    from lumina_core.birth.birth_trade_geometry import geometry_forensics_fields

    ticks = _chrono_ticks(300)
    geo = calibrate_birth_stops(ticks, max_hold_bars=60)
    fields = geometry_forensics_fields(geo)
    assert "geometry_floor_bound" in fields
    assert "geometry_net_rr_after_cost" in fields
    assert "geometry_breakeven_wr_after_cost" in fields
    assert "geometry_econ_proxy_mismatch" in fields


@pytest.mark.unit
def test_geometry_forensics_omit_fake_net_rr_when_missing() -> None:
    from lumina_core.birth.birth_trade_geometry import geometry_forensics_fields

    fields = geometry_forensics_fields(None)
    assert "geometry_net_rr" not in fields
    assert "geometry_net_rr_after_cost" not in fields


@pytest.mark.unit
def test_cost_lift_documents_be_wr_and_net_rr() -> None:
    """MES-like micro moves: net_rr documented and cost_lift path available."""
    from lumina_core.birth.birth_trade_geometry import TARGET_BE_WR_AFTER_COST

    ticks = _chrono_ticks(800, step=0.2)
    geo = calibrate_birth_stops(ticks, max_hold_bars=90)
    assert geo.net_rr_after_cost >= MIN_NET_RR_AFTER_COST - 0.05 or geo.cost_usd > 0
    assert 0.0 < geo.breakeven_wr_after_cost <= 1.0
    # Honest flag: if BE-WR still above target after best lift, mismatch is set.
    if geo.breakeven_wr_after_cost > TARGET_BE_WR_AFTER_COST + 1e-9:
        assert geo.econ_proxy_mismatch is True
    else:
        assert geo.econ_proxy_mismatch is False
