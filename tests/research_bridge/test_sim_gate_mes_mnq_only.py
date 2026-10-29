"""D5: ES/NQ research OrderIntent refused; MES/MNQ allowed when other gates pass."""

from __future__ import annotations

import pytest

from lumina_core.research_bridge.sim_gate import (
    SIM_INSTRUMENT_NOT_YET_RELEASED,
    bind_sim_gate,
    evaluate,
    evaluate_instrument,
)
from tests.research_bridge.s3_helpers import passing_context


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    yield
    bind_sim_gate(None)


@pytest.mark.unit
def test_es_nq_refused() -> None:
    for root in ("ES", "NQ"):
        ok, reason = evaluate(passing_context(instrument=root))
        assert ok is False
        assert reason == SIM_INSTRUMENT_NOT_YET_RELEASED
        ok, reason = evaluate_instrument(root, passing_context(instrument="MES"))
        assert ok is False
        assert reason == SIM_INSTRUMENT_NOT_YET_RELEASED


@pytest.mark.unit
def test_mes_mnq_allowed() -> None:
    for root in ("MES", "MNQ"):
        ok, reason = evaluate(passing_context(instrument=root))
        assert ok is True
        assert reason == "research_sim_gate_ok"
