"""S5 MES $5 settlement SSOT. Floors unchanged. No NQ $20 birth path."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.birth_trade_geometry import MES_POINT_VALUE_USD, MES_TICK_SIZE
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S5_DD_EQUITY_USD,
    S5_DD_MAX_PCT,
    S5_EDGE_MIN,
    S5_SHARPE_FLOOR,
)
from lumina_core.birth.notional_cap import (
    birth_fill_pnl_usd,
    birth_gym_point_value,
    clip_birth_exam_pnl,
)
from lumina_core.rl.gym_stop_fill import birth_force_qty_one


def test_mes_point_value_and_s5_floors_pinned() -> None:
    assert MES_POINT_VALUE_USD == 5.0
    assert S5_DD_EQUITY_USD == 50_000.0
    assert S5_DD_MAX_PCT == 25.0
    assert S5_SHARPE_FLOOR == pytest.approx(-2.0)
    assert S5_EDGE_MIN == pytest.approx(-0.03)
    assert POLICY_EDGE_MIN_TRADES == 150
    assert birth_gym_point_value() == pytest.approx(5.0)
    assert birth_force_qty_one("stage5_probe_handoff") is True


def test_qty1_ten_points_books_fifty_before_clip() -> None:
    raw = birth_fill_pnl_usd(entry_price=20000.0, exit_price=20010.0, side=1, quantity=1)
    assert raw == pytest.approx(50.0)
    assert raw != pytest.approx(200.0)


def test_two_hundred_point_adverse_gap_books_mes_cap() -> None:
    raw = birth_fill_pnl_usd(entry_price=23000.0, exit_price=22800.0, side=1, quantity=1)
    assert raw == pytest.approx(-1000.0)
    booked = clip_birth_exam_pnl(raw, entry_price=23000.0, qty=1)
    assert booked == pytest.approx(-(500.0 + MES_TICK_SIZE * MES_POINT_VALUE_USD))
    assert booked == pytest.approx(-501.25)


def test_force_qty_one_still_on_sim_runner_path() -> None:
    src = Path("lumina_core/birth/sim_runner.py").read_text(encoding="utf-8")
    assert "force_qty_one=bool(birth_force_qty_one" in src
