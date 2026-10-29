"""After calibration, research commission_usd ≥ ADR-0055 all-in for that root."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.market.nt_fees import all_in_per_side_usd
from lumina_research.validation.cost_calibrate import (
    CostCalibrateRefused,
    assert_does_not_undercut_card,
    calibrate_fills,
    calibrate_root,
    card_commission_usd,
    research_commission_usd,
    tighten_only,
    write_research_calibration,
)
from lumina_research.validation.cost_model import CostModel


@pytest.mark.unit
@pytest.mark.safety_gate
def test_research_commission_meets_card_for_each_root() -> None:
    for root, card in (("MES", 0.94), ("MNQ", 0.94), ("ES", 2.87), ("NQ", 2.87)):
        assert all_in_per_side_usd(root, qty=1) == pytest.approx(card)
        research = research_commission_usd(root, 1)
        assert_does_not_undercut_card(root, research, 1)
        assert research + 1e-12 >= card_commission_usd(root, 1)


@pytest.mark.unit
def test_undercut_is_refused() -> None:
    with pytest.raises(CostCalibrateRefused, match="undercuts_card"):
        assert_does_not_undercut_card("MES", 0.93, 1)


@pytest.mark.unit
def test_coefficients_never_cheapen() -> None:
    assert tighten_only(0.10, 0.20) == pytest.approx(0.20)
    assert tighten_only(0.10, 0.05) == pytest.approx(0.10)
    with pytest.raises(CostCalibrateRefused):
        tighten_only(-0.1, 0.2)
    calibrated = calibrate_root(
        root="MES",
        execution_commission_usd=0.94,
        execution_slippage_usd=1.25,
        qty=1,
        model=CostModel(slippage_coefficient=0.10, impact_coefficient=0.10),
    )
    assert calibrated.slippage_coefficient >= 0.10
    assert calibrated.impact_coefficient >= 0.10
    assert calibrated.execution_commission_usd == pytest.approx(0.94)


@pytest.mark.unit
def test_cannot_write_live_calibration_filename(tmp_path: Path) -> None:
    with pytest.raises(CostCalibrateRefused, match="cannot_write_live_state"):
        write_research_calibration(tmp_path / "cost_model_calibration.json", {"x": 1})


@pytest.mark.unit
@pytest.mark.safety_gate
def test_calibrate_fills_skips_hypothetical_and_does_not_undercut(tmp_path: Path) -> None:
    output = tmp_path / "research_cost_calibration.json"
    payload = calibrate_fills(
        [
            {
                "symbol": "MES",
                "qty": 1,
                "commission": 0.94,
                "slippage_usd": 1.25,
                "source": "hypothetical_adr0055",
            },
            {
                "symbol": "MES",
                "qty": 1,
                "commission": 0.94,
                "slippage_usd": 1.25,
                "source": "broker",
            },
            {
                "symbol": "ES",
                "qty": 1,
                "commission": 2.87,
                "slippage_usd": 12.50,
                "source": "broker",
            },
        ],
        output=output,
    )
    assert "MES" in payload["by_root"]
    assert "ES" in payload["by_root"]
    assert payload["by_root"]["MES"]["sample_count"] == 1
    assert payload["by_root"]["MES"]["research_commission_usd"] + 1e-12 >= 0.94
    assert payload["by_root"]["ES"]["research_commission_usd"] + 1e-12 >= 2.87
    assert payload["winner"] == "execution_side"
    assert output.is_file()
    assert not (tmp_path / "cost_model_calibration.json").exists()
