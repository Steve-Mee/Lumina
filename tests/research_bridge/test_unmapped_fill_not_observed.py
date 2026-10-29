"""Fill without strategy_id updates calibrator, not monitor."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.research_bridge.s2_helpers import broker_fill, make_translator


@pytest.mark.unit
@pytest.mark.safety_gate
def test_unmapped_fill_not_observed(tmp_path: Path) -> None:
    translator, observe, _index, _bus = make_translator(tmp_path, remember=None)
    fill = broker_fill(client_order_id="unknown-cid")
    result = translator.ingest(fill, client_order_id="unknown-cid", reference_price=5000.0)
    assert result.observed is False
    assert result.published is False
    assert result.calibrated is True
    assert observe.calls == []
    assert len(translator.calibrator_rows()) == 1
    assert translator.calibrator_rows()[0]["strategy_id"] == ""


@pytest.mark.unit
def test_empty_strategy_id_does_not_pick_another_signal(tmp_path: Path) -> None:
    translator, observe, index, _bus = make_translator(tmp_path, remember=("cid-other", "hyp-other", 8))
    fill = broker_fill(strategy_id="", client_order_id="cid-unmapped")
    result = translator.ingest(fill, client_order_id="cid-unmapped")
    assert result.observed is False
    assert observe.calls == []
    assert index.lookup("cid-other") is not None
