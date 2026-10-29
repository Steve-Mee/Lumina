"""Attack tests for every S2 fail-closed path."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import HYPOTHESIS_AGENT_ID
from lumina_core.agent_orchestration.schemas_research_execution import (
    FILL_TRANSLATOR_AGENT_ID,
    RESEARCH_EXECUTION_FILL_TOPIC,
    RESEARCH_EXECUTION_ORDER_TOPIC,
    RESEARCH_EXECUTION_SIGNAL_TOPIC,
    ResearchExecutionFill,
)
from lumina_core.agent_orchestration.schemas_trading import ExecutionFill
from lumina_core.order_gatekeeper.ungated_place_block import (
    S0_PLACE_SOURCE_ALLOWLIST,
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
    freeze_is_armed,
)
from lumina_core.research_bridge.calibrator_rows import CalibratorRowRefused, normalize_fill_source
from lumina_core.research_bridge.fill_index import FillIndex, FillIndexRefused
from lumina_core.research_bridge.fill_stamp import FillStampRefused, stamp_commission, stamp_slippage
from lumina_core.research_bridge.fill_translator import FillTranslator, TranslateRefused
from lumina_core.research_bridge.horizon import HorizonRefused, require_expected_horizon_bars
from lumina_core.risk.live_release import LIVE_ACCOUNT_PATH_CLOSED_S1, admit_live_orders
from tests.research_bridge.s2_helpers import broker_fill, make_translator, utc

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.safety_gate
def test_s0_and_s1_stay_armed() -> None:
    assert freeze_is_armed() is True
    assert S0_PLACE_SOURCE_ALLOWLIST == frozenset()
    allowed, reason = assert_validation_gate_or_block("research_bridge", order_side="BUY", order_qty=1)
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON
    ok, live_reason = admit_live_orders(None)
    assert ok is False
    assert live_reason != "ok"
    assert LIVE_ACCOUNT_PATH_CLOSED_S1


@pytest.mark.unit
@pytest.mark.safety_gate
def test_horizon_still_required() -> None:
    with pytest.raises(HorizonRefused):
        require_expected_horizon_bars(None, oos_size=30)
    with pytest.raises(HorizonRefused):
        require_expected_horizon_bars(0)
    with pytest.raises(FillIndexRefused, match="expected_horizon"):
        FillIndex().remember("cid", "hyp", 0)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_unknown_source_refused() -> None:
    with pytest.raises(CalibratorRowRefused, match="unknown_fill_source"):
        normalize_fill_source("research_four_leg")


@pytest.mark.unit
@pytest.mark.safety_gate
def test_invalid_stamp_inputs_fail_closed() -> None:
    with pytest.raises(FillStampRefused):
        stamp_commission("MES", 0)
    with pytest.raises(FillStampRefused):
        stamp_commission("NOTAROOT", 1)
    with pytest.raises(FillStampRefused):
        stamp_slippage(symbol="MES", side="BUY", fill_price=5000.0, reference_price=0.0, qty=1)
    with pytest.raises(FillStampRefused):
        stamp_slippage(symbol="MES", side="HOLD", fill_price=5000.0, reference_price=5000.0, qty=1)
    assert stamp_slippage(symbol="MES", side="BUY", fill_price=5000.0, reference_price=None, qty=1) is None


@pytest.mark.unit
@pytest.mark.safety_gate
def test_translator_cannot_place_and_has_no_broker_import() -> None:
    path = ROOT / "lumina_core" / "research_bridge" / "fill_translator.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("lumina_core.broker")
            assert not module.startswith("lumina_core.risk.live_release")
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("lumina_core.broker")
    assert "place_order" not in source
    assert "submit_order" not in source
    translator = FillTranslator()
    translator.assert_no_broker_submit()


@pytest.mark.unit
@pytest.mark.safety_gate
def test_hypothesis_agent_cannot_publish_fill() -> None:
    bus = EventBus()
    payload = ResearchExecutionFill(
        fill_id="f1",
        symbol="MES",
        side="BUY",
        quantity=1,
        price=5000.0,
        commission=0.94,
        event_ts=utc(),
        source="broker",
        strategy_id="hyp",
        expected_horizon=8,
    ).model_dump(mode="json")
    with pytest.raises(PermissionError):
        bus.publish(topic=RESEARCH_EXECUTION_FILL_TOPIC, producer=HYPOTHESIS_AGENT_ID, payload=payload)


@pytest.mark.unit
def test_fill_translator_cannot_publish_signal_or_order() -> None:
    bus = EventBus()
    with pytest.raises(PermissionError):
        bus.publish(topic=RESEARCH_EXECUTION_SIGNAL_TOPIC, producer=FILL_TRANSLATOR_AGENT_ID, payload={"x": 1})
    with pytest.raises(PermissionError):
        bus.publish(topic=RESEARCH_EXECUTION_ORDER_TOPIC, producer=FILL_TRANSLATOR_AGENT_ID, payload={"x": 1})


@pytest.mark.unit
def test_observe_failure_does_not_pick_another_signal(tmp_path: Path) -> None:
    class Boom:
        def observe(self, signal_id: str, metric: object) -> object:
            raise RuntimeError("monitor_down")

    translator = FillTranslator(
        observe_sink=Boom(),  # type: ignore[arg-type]
        refuse_jsonl=tmp_path / "refuse.jsonl",
    )
    translator.index().remember("cid-1", "hyp-s2", 8)
    result = translator.ingest(broker_fill(), client_order_id="cid-1")
    assert result.observed is False
    assert result.calibrated is True
    text = (tmp_path / "refuse.jsonl").read_text(encoding="utf-8")
    assert "observe_failed" in text


@pytest.mark.unit
def test_execution_fill_and_row_coerce(tmp_path: Path) -> None:
    translator, observe, _index, _bus = make_translator(tmp_path)
    execution = ExecutionFill(
        fill_id="ef1",
        order_id="o1",
        symbol="MES",
        side="BUY",
        quantity=1,
        price=5000.25,
        timestamp="2026-10-29T12:00:00Z",
        commission=0.0,
        raw={"client_order_id": "cid-1", "source": "broker"},
    )
    result = translator.ingest(execution, client_order_id="cid-1", reference_price=5000.0)
    assert result.fill.commission == pytest.approx(0.94)
    assert result.observed is True
    row_result = translator.ingest(
        {
            "fill_id": "row1",
            "symbol": "ES",
            "side": "BUY",
            "qty": 1,
            "fill_price": 5000.25,
            "commission": 0.0,
            "source": "broker",
            "ts": "2026-10-29T12:00:00+00:00",
            "client_order_id": "cid-1",
        },
        client_order_id="cid-1",
    )
    assert row_result.fill.commission == pytest.approx(2.87)
    assert observe.calls[0][0] == "hyp-s2"


@pytest.mark.unit
def test_naive_timestamp_is_utc(tmp_path: Path) -> None:
    translator, _observe, _index, _bus = make_translator(tmp_path)
    result = translator.ingest(
        {
            "fill_id": "naive",
            "symbol": "MES",
            "side": "SELL",
            "quantity": 1,
            "price": 4999.75,
            "commission": 0.94,
            "source": "broker",
            "ts": "2026-10-29T12:00:00",
            "client_order_id": "cid-1",
        },
        client_order_id="cid-1",
        reference_price=5000.0,
    )
    assert result.fill.event_ts.tzinfo is not None
    assert result.fill.event_ts.utcoffset() == timezone.utc.utcoffset(result.fill.event_ts)


@pytest.mark.unit
def test_missing_price_and_qty_fail_closed(tmp_path: Path) -> None:
    translator, _o, _i, _b = make_translator(tmp_path)
    with pytest.raises(TranslateRefused):
        translator.ingest({"symbol": "MES", "side": "BUY", "qty": 1, "source": "broker"})
    with pytest.raises(TranslateRefused):
        translator.ingest(
            {
                "symbol": "MES",
                "side": "BUY",
                "qty": 0,
                "fill_price": 5000.0,
                "source": "broker",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )


@pytest.mark.unit
@pytest.mark.safety_gate
def test_unknown_source_ingest_is_translate_refused(tmp_path: Path) -> None:
    translator, _observe, _index, _bus = make_translator(tmp_path)
    with pytest.raises(TranslateRefused, match="unknown_fill_source"):
        translator.ingest(broker_fill(source="research_four_leg"), client_order_id="cid-1")


@pytest.mark.unit
@pytest.mark.safety_gate
def test_fill_translator_can_publish_mapped_broker_fill(tmp_path: Path) -> None:
    translator, _observe, _index, bus = make_translator(tmp_path, with_bus=True)
    assert bus is not None
    result = translator.ingest(broker_fill(), client_order_id="cid-1", reference_price=5000.0)
    assert result.published is True
    fills = bus.history(RESEARCH_EXECUTION_FILL_TOPIC, limit=10)
    assert len(fills) == 1
    assert fills[0].producer == FILL_TRANSLATOR_AGENT_ID
    assert fills[0].payload["source"] == "broker"
    assert fills[0].payload["commission"] == pytest.approx(0.94)


@pytest.mark.unit
def test_lumina_research_does_not_import_broker() -> None:
    hits: list[str] = []
    root = ROOT / "lumina_research"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("lumina_core.broker"):
                hits.append(f"{path.relative_to(ROOT)}:{node.lineno}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("lumina_core.broker"):
                        hits.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert hits == []


@pytest.mark.unit
def test_cost_calibrate_has_no_broker_import() -> None:
    path = ROOT / "lumina_research" / "validation" / "cost_calibrate.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("lumina_core.broker")
            assert not module.startswith("lumina_core.risk.live_release")
            assert not module.startswith("lumina_core.risk.sim_account_guard")
    assert "place_order" not in source
    assert "LUMINA_LIVE_RELEASE_SECRET" not in source
