"""T10: capital-path Event Bus lineage inventory / typed contracts."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.schemas import (
    CRITICAL_EVENT_BUS_TOPICS,
    EVENT_BUS_TOPIC_MODELS,
    AdmissionLineageCheckedPayload,
)
from lumina_core.risk.capital_bus_lineage import (
    CAPITAL_PATH_CORE_TOPICS,
    build_capital_bus_lineage_inventory,
    evaluate_capital_bus_lineage_gate,
)


@pytest.mark.unit
def test_lineage_checked_payload_typed() -> None:
    p = AdmissionLineageCheckedPayload(
        decision_context_id="ctx-1",
        mode="sim",
        symbol="MNQ",
        side="BUY",
        quantity=1,
        reason="admitted",
        stage="capital_aperture_admission",
    )
    assert p.decision_context_id == "ctx-1"
    assert "risk.admission.lineage_checked" in EVENT_BUS_TOPIC_MODELS
    assert "risk.admission.lineage_checked" in CRITICAL_EVENT_BUS_TOPICS


@pytest.mark.unit
def test_capital_bus_lineage_gate_passes() -> None:
    inv = build_capital_bus_lineage_inventory()
    assert inv["schema"] == "capital_bus_lineage_inventory_v1"
    assert inv["typed_models_missing"] == []
    for topic in CAPITAL_PATH_CORE_TOPICS:
        assert topic in EVENT_BUS_TOPIC_MODELS
    gate = evaluate_capital_bus_lineage_gate()
    assert gate["ok"] is True
    assert gate["hard_fail"] is False
