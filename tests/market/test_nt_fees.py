"""The NinjaTrader card is the only execution fee. Unknown roots are refused."""
from __future__ import annotations

import pytest

from lumina_core.market.nt_fees import (
    CostCardError,
    all_in_per_side_usd,
    contract_root,
    gross_close_usd,
    net_close_usd,
    round_turn_fee_usd,
    spec_for,
)


@pytest.mark.unit
def test_card_all_in_is_the_sum_of_the_published_columns() -> None:
    mes = spec_for("MES DEC26")
    assert mes.all_in_per_side("free") == pytest.approx(0.36 + 0.19 + 0.39)
    assert mes.all_in_per_side("monthly") == pytest.approx(0.36 + 0.19 + 0.29)
    assert mes.all_in_per_side("lifetime") == pytest.approx(0.36 + 0.19 + 0.09)
    es = spec_for("ES")
    assert es.all_in_per_side("free") == pytest.approx(1.39 + 0.19 + 1.29)
    assert es.all_in_per_side("monthly") == pytest.approx(1.39 + 0.19 + 0.99)
    assert es.all_in_per_side("lifetime") == pytest.approx(1.39 + 0.19 + 0.59)


@pytest.mark.unit
def test_mes_free_round_trip_is_1_88_and_scales_by_qty() -> None:
    assert round_turn_fee_usd("MES", 1, plan="free") == pytest.approx(1.88)
    assert round_turn_fee_usd("MES", 3, plan="free") == pytest.approx(1.88 * 3)
    assert all_in_per_side_usd("MNQ", plan="free", qty=2) == pytest.approx(0.94 * 2)


@pytest.mark.unit
def test_unknown_root_and_plan_are_refused() -> None:
    with pytest.raises(CostCardError):
        contract_root("CL")
    with pytest.raises(CostCardError):
        round_turn_fee_usd("MES", 1, plan="discount")
    with pytest.raises(CostCardError):
        round_turn_fee_usd("", 1)


@pytest.mark.unit
def test_a_price_win_below_the_fee_is_net_negative() -> None:
    row = {
        "instrument": "MES",
        "qty": 1,
        "side": 1,
        "entry_px": 5000.0,
        "exit_px": 5000.25,
        "pnl": 50.0,
    }
    assert gross_close_usd(row) == pytest.approx(1.25)
    assert net_close_usd(row, plan="free") == pytest.approx(1.25 - 1.88)


@pytest.mark.unit
def test_stored_pnl_is_gross_when_the_prices_do_not_move() -> None:
    row = {"instrument": "MES", "qty": 2, "pnl": 20.0, "entry_px": 5000.0, "fill_px": 5000.0}
    assert net_close_usd(row, plan="free") == pytest.approx(20.0 - 1.88 * 2)
