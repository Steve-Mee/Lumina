"""Research four-leg > card: FillEvent.commission stays card; discrepancy logged."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from lumina_core.research_bridge.fill_stamp import execution_commission
from lumina_research.validation.cost_calibrate import execution_wins, research_four_leg_usd
from tests.research_bridge.s2_helpers import broker_fill, make_translator


@pytest.mark.unit
@pytest.mark.safety_gate
def test_discrepancy_execution_wins_on_fill_event(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    translator, _observe, _index, _bus = make_translator(tmp_path)
    four_leg = research_four_leg_usd("MES", 1)
    assert four_leg > 0.94
    fill = broker_fill(commission=four_leg)
    with caplog.at_level(logging.WARNING):
        result = translator.ingest(fill, client_order_id="cid-1")
    assert result.fill.commission == pytest.approx(0.94)
    assert result.fill.commission != pytest.approx(four_leg)
    assert "cost_discrepancy" in caplog.text
    card, _ticks, discrepancy = execution_commission("MES", 1, four_leg)
    assert card == pytest.approx(0.94)
    assert discrepancy is True
    kept, flagged = execution_wins(four_leg, 0.94 + 1.25)
    assert kept == pytest.approx(0.94 + 1.25)
    assert flagged is True
