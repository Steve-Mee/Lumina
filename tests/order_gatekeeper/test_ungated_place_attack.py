"""Attack tests: bypass routes cannot reopen ungated places (D1/D8)."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from lumina_core.broker.broker_bridge.paper_broker import PaperBroker
from lumina_core.broker.broker_bridge.schemas import Order, Position
from lumina_core.order_gatekeeper.ungated_place_block import (
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
    blocked_fabric_place_result,
    freeze_is_armed,
    gate_order,
    live_qty_from_positions,
    signed_qty_from_position,
)

ROOT = Path(__file__).resolve().parents[2]


def _buy() -> Order:
    return Order(symbol="MES", side="BUY", quantity=1, order_type="MARKET")


def _flatten_sell(*, qty: int = 1, extra: dict[str, object] | None = None) -> Order:
    meta: dict[str, object] = {"reduce_only": True}
    if extra:
        meta.update(extra)
    return Order(symbol="MES", side="SELL", quantity=qty, order_type="MARKET", metadata=meta)


@pytest.mark.unit
def test_confluence_yaml_env_and_source_agent_cannot_reopen() -> None:
    assert freeze_is_armed() is True
    probes = (
        ("supervisor_tick_exec.run_tick_exec", "BUY", "confluence"),
        ("operations_service_orders.place_order", "SELL", "operator"),
        ("policy_engine.execute_order", "BUY", "policy"),
        ("reasoning_service.submit_order", "BUY", "reasoning"),
        ("trade_workers.submit_order_with_risk_check", "BUY", "workers"),
        ("paper_simulator.try_open", "BUY", "paper"),
        ("paper_trade_executor.submit_paper_order", "BUY", "paper_exec"),
        ("fabric_client_ops.place_order_sync", "BUY", "fabric"),
        ("paper_broker.submit_order", "BUY", "paper_broker"),
        ("ninjatrader.broker.submit_order", "BUY", "nt_broker"),
        ("cross_trade_broker.submit_order", "BUY", "cross_trade"),
    )
    for source, side, _label in probes:
        allowed, reason = assert_validation_gate_or_block(
            source,
            order_side=side,
            source_agent="research_bridge",
            reduce_only=False,
        )
        assert allowed is False, source
        assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_reduce_only_without_opposing_position_is_blocked() -> None:
    allowed, reason = assert_validation_gate_or_block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=0,
        order_qty=1,
    )
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON
    allowed_add, reason_add = assert_validation_gate_or_block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=-1,
        order_qty=1,
    )
    assert allowed_add is False
    assert reason_add == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_reduce_only_qty_that_flips_sign_is_blocked() -> None:
    allowed, reason = assert_validation_gate_or_block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=1,
        order_qty=2,
    )
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON
    allowed_short, reason_short = assert_validation_gate_or_block(
        "emergency_order_endpoints",
        emergency=True,
        order_side="BUY",
        live_position_qty=-1,
        order_qty=2,
        reason="api_emergency_stop",
    )
    assert allowed_short is False
    assert reason_short == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_exact_flatten_qty_is_allowed_and_zero_qty_is_not() -> None:
    allowed, reason = assert_validation_gate_or_block(
        "eod_force_close",
        emergency=True,
        order_side="SELL",
        live_position_qty=3,
        order_qty=3,
        reason="eod_force_close",
    )
    assert allowed is True
    assert reason == "emergency_flatten_or_cancel_allowed"
    allowed_zero, reason_zero = assert_validation_gate_or_block(
        "eod_force_close",
        emergency=True,
        order_side="SELL",
        live_position_qty=3,
        order_qty=0,
        reason="eod_force_close",
    )
    assert allowed_zero is False
    assert reason_zero == UNGATED_PLACE_BLOCK_REASON
    allowed_none, reason_none = assert_validation_gate_or_block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=1,
        order_qty=None,
    )
    assert allowed_none is False
    assert reason_none == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_emergency_source_or_reason_spoof_cannot_open() -> None:
    for source, reason in (
        ("emergency_order_endpoints", "api_emergency_stop"),
        ("eod_force_close", "eod_force_close"),
        ("heartbeat_watchdog", "heartbeat_watchdog_flatten"),
        ("emergency_flatten_policy", "emergency_flatten"),
        ("policy_engine.execute_order", "fabric_emergency_flatten"),
    ):
        allowed, blocked = assert_validation_gate_or_block(
            source,
            emergency=True,
            order_side="BUY",
            live_position_qty=0,
            order_qty=1,
            reason=reason,
        )
        assert allowed is False, source
        assert blocked == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_metadata_live_qty_is_ignored_and_cannot_spoof_a_flatten() -> None:
    order = Order(
        symbol="MES",
        side="SELL",
        quantity=1,
        metadata={"reduce_only": True, "live_position_qty": 99},
    )
    allowed, reason = gate_order("policy_engine.execute_order", order, engine=SimpleNamespace(live_position_qty=0))
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON
    allowed_book, reason_book = gate_order(
        "policy_engine.execute_order",
        order,
        engine=SimpleNamespace(live_position_qty=99),
        broker=SimpleNamespace(get_positions=lambda: [Position(symbol="MES", quantity=0, avg_price=0.0, side="BUY")]),
    )
    assert allowed_book is False
    assert reason_book == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_yaml_env_reload_and_allowlist_rebind_cannot_reopen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LUMINA_RESEARCH_EXECUTION_MODE", "live")
    monkeypatch.setenv("LUMINA_TRADE_MODE", "real")
    monkeypatch.setenv("research_execution_mode", "sim")
    cfg = tmp_path / "config.yaml"
    cfg.write_text("research_execution_mode: live\nmode: real\ntrade_mode: real\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    import lumina_core.order_gatekeeper.ungated_place_block as freeze

    importlib.reload(freeze)
    monkeypatch.setattr(freeze, "S0_PLACE_SOURCE_ALLOWLIST", frozenset({"research_bridge", "confluence"}))
    monkeypatch.setattr(freeze, "freeze_is_armed", lambda: False)
    allowed, reason = freeze.assert_validation_gate_or_block(
        "supervisor_tick_exec.run_tick_exec",
        order_side="BUY",
        source_agent="research_bridge",
        live_position_qty=0,
        order_qty=1,
    )
    assert allowed is False
    assert reason == freeze.UNGATED_PLACE_BLOCK_REASON
    assert freeze.S0_PLACE_SOURCE_ALLOWLIST == frozenset({"research_bridge", "confluence"})
    assert freeze.freeze_is_armed() is False
    assert "os.environ" not in (ROOT / "lumina_core" / "order_gatekeeper" / "ungated_place_block.py").read_text(
        encoding="utf-8"
    )
    _ = os.environ.get("LUMINA_RESEARCH_EXECUTION_MODE")


@pytest.mark.unit
def test_freeze_is_armed_monkeypatch_cannot_allow_a_buy(monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.order_gatekeeper.ungated_place_block as freeze

    monkeypatch.setattr(freeze, "freeze_is_armed", lambda: False)
    allowed, reason = freeze.assert_validation_gate_or_block(
        "operations_service_orders.place_order",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
    )
    assert freeze.freeze_is_armed() is False
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_reflection_and_import_tricks_still_block() -> None:
    freeze = importlib.import_module("lumina_core.order_gatekeeper.ungated_place_block")
    fn = getattr(freeze, "assert_validation_gate_or_block")
    allowed, reason = fn("policy_engine.execute_order", order_side="BUY", source_agent="research_bridge")
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON
    via_package = importlib.import_module("lumina_core.order_gatekeeper")
    allowed2, reason2 = via_package.assert_validation_gate_or_block(
        "fabric_client_ops.place_order_sync",
        order_side="SELL",
        live_position_qty=0,
        order_qty=1,
    )
    assert allowed2 is False
    assert reason2 == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_direct_paper_broker_buy_is_blocked() -> None:
    broker = PaperBroker(engine=SimpleNamespace(live_position_qty=0, config=SimpleNamespace(trade_mode="paper")))
    result = broker.submit_order(_buy())
    assert result.accepted is False
    assert result.message == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_direct_paper_broker_flatten_does_not_flip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_core.broker.broker_bridge.paper_broker.run_final_arbitration",
        lambda *_a, **_k: (False, "admission_engine_required"),
    )
    engine = SimpleNamespace(config=SimpleNamespace(trade_mode="paper"), live_position_qty=1)
    broker = PaperBroker(engine=engine)
    broker._positions["MES"] = Position(symbol="MES", quantity=1, avg_price=5000.0, side="BUY")
    flip = broker.submit_order(_flatten_sell(qty=2))
    assert flip.accepted is False
    assert flip.message == UNGATED_PLACE_BLOCK_REASON
    exact = broker.submit_order(_flatten_sell(qty=1))
    assert exact.accepted is False
    assert "admission_engine_required" in exact.message
    assert exact.message != UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_fabric_mixin_buy_is_blocked_before_rpc() -> None:
    from lumina_core.broker.ninjatrader.fabric_client_ops import FabricClientOpsMixin

    class _Fake(FabricClientOpsMixin):
        def __init__(self) -> None:
            self.config = SimpleNamespace(mode_context="sim", trade_mode="sim")
            self.is_connected = True
            self._safe_mode = 1

        @property
        def safe_mode(self) -> int:
            return int(self._safe_mode)

        def get_account_state(self) -> tuple[object, list[Position], str]:
            return None, [], "ok"

        def _send_and_wait(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            raise AssertionError("must not RPC an ungated BUY")

    fake = _Fake()
    out = fake.place_order_sync(_buy(), client_order_id="attack-buy")
    assert out == blocked_fabric_place_result()
    assert out["code"] == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_fabric_mixin_short_cover_cannot_flip() -> None:
    from lumina_core.broker.ninjatrader.fabric_client_ops import FabricClientOpsMixin

    class _Fake(FabricClientOpsMixin):
        def __init__(self) -> None:
            self.config = SimpleNamespace(mode_context="sim", trade_mode="sim")
            self.is_connected = True
            self._safe_mode = 1

        @property
        def safe_mode(self) -> int:
            return int(self._safe_mode)

        def get_account_state(self) -> tuple[object, list[Position], str]:
            return None, [Position(symbol="MNQ", quantity=1, avg_price=1.0, side="SHORT")], "ok"

        def _send_and_wait(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            raise AssertionError("must not RPC a flipping cover")

    fake = _Fake()
    order = Order(
        symbol="MNQ",
        side="BUY",
        quantity=2,
        order_type="MARKET",
        metadata={"reduce_only": True, "reason": "api_emergency_stop"},
    )
    out = fake.place_order_sync(order, client_order_id="flip-cover")
    assert out["code"] == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_fabric_mixin_true_reduce_reaches_later_gates() -> None:
    from lumina_core.broker.ninjatrader.fabric_client_ops import FabricClientOpsMixin

    class _Fake(FabricClientOpsMixin):
        def __init__(self) -> None:
            self.config = SimpleNamespace(mode_context="sim", trade_mode="sim")
            self.is_connected = True
            self._safe_mode = 2

        @property
        def safe_mode(self) -> int:
            return int(self._safe_mode)

        def get_account_state(self) -> tuple[object, list[Position], str]:
            return None, [Position(symbol="MNQ", quantity=1, avg_price=1.0, side="LONG")], "ok"

        def _send_and_wait(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            raise AssertionError("SAFE_MODE must reject before RPC")

    fake = _Fake()
    order = Order(
        symbol="MNQ",
        side="SELL",
        quantity=1,
        order_type="MARKET",
        metadata={"reduce_only": True, "decision_context_id": "ctx-safe"},
    )
    out = fake.place_order_sync(order, client_order_id="c-safe-reduce")
    assert out["type"] == "error"
    assert out["code"] == "SAFE_MODE"


@pytest.mark.unit
def test_signed_book_qty_handles_fabric_abs_and_paper_net() -> None:
    long_abs = Position(symbol="MNQ", quantity=2, avg_price=1.0, side="LONG")
    short_abs = Position(symbol="MNQ", quantity=2, avg_price=1.0, side="SHORT")
    paper_short = Position(symbol="MES JUN26", quantity=-3, avg_price=1.0, side="SELL")
    assert signed_qty_from_position(long_abs) == 2
    assert signed_qty_from_position(short_abs) == -2
    assert signed_qty_from_position(paper_short) == -3
    assert live_qty_from_positions([long_abs], "MNQ 06-26") == 2
    assert live_qty_from_positions([short_abs], "MNQ") == -2
    assert live_qty_from_positions([paper_short], "MES") == -3
    proto = SimpleNamespace(instrument="ES 06-26", quantity=1, side="LONG")
    assert live_qty_from_positions([proto], "ES") == 1
    assert live_qty_from_positions("not-a-book", "MES") is None


@pytest.mark.unit
def test_gate_order_prefers_broker_book_over_engine() -> None:
    order = _flatten_sell()
    broker = SimpleNamespace(
        get_positions=lambda: [Position(symbol="MES", quantity=1, avg_price=1.0, side="BUY")]
    )
    allowed, reason = gate_order(
        "policy_engine.execute_order",
        order,
        engine=SimpleNamespace(live_position_qty=0),
        broker=broker,
    )
    assert allowed is True
    assert reason == "reduce_only_allowed"


@pytest.mark.unit
def test_supervisor_module_does_not_import_research_bridge() -> None:
    text = (ROOT / "lumina_core" / "engine" / "supervisor_tick_exec.py").read_text(encoding="utf-8")
    assert "research_bridge" not in text
    assert "SignalIntent" not in text
    assert "schemas_research_execution" not in text


@pytest.mark.unit
def test_nt_submit_frame_forwards_reduce_only_tag() -> None:
    text = (ROOT / "lumina_core" / "broker" / "ninjatrader" / "broker.py").read_text(encoding="utf-8")
    assert 'frame["reduce_only"] = True' in text
    sync = (ROOT / "lumina_core" / "broker" / "ninjatrader" / "bridge_command_sync.py").read_text(encoding="utf-8")
    assert '"reduce_only": bool(frame.get("reduce_only", False))' in sync


@pytest.mark.unit
def test_freeze_module_never_loads_config_yaml() -> None:
    text = (ROOT / "lumina_core" / "order_gatekeeper" / "ungated_place_block.py").read_text(encoding="utf-8")
    assert "config.yaml" not in text
    assert "yaml.safe_load" not in text
    assert "os.environ" not in text
    assert "os.getenv" not in text
    assert "S0_PLACE_SOURCE_ALLOWLIST" in text


@pytest.mark.unit
def test_research_execution_mode_parser_is_observability_only() -> None:
    from lumina_core.order_gatekeeper.ungated_place_block import research_execution_mode_from_mapping

    assert research_execution_mode_from_mapping(None) == "off"
    assert research_execution_mode_from_mapping({}) == "off"
    assert research_execution_mode_from_mapping({"research_execution_mode": "live"}) == "off"
    assert research_execution_mode_from_mapping({"research_execution_mode": "SHADOW"}) == "shadow"
    allowed, reason = assert_validation_gate_or_block(
        "policy_engine.execute_order",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
    )
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_flatten_intent_covers_fabric_short_with_buy_not_sell() -> None:
    from lumina_core.order_gatekeeper.ungated_place_block import flatten_intent_from_position

    short = Position(symbol="MNQ", quantity=2, avg_price=1.0, side="SHORT")
    long = Position(symbol="ES", quantity=3, avg_price=1.0, side="LONG")
    paper_short = Position(symbol="MES JUN26", quantity=-4, avg_price=1.0, side="SELL")
    assert flatten_intent_from_position(short) == ("BUY", -2)
    assert flatten_intent_from_position(long) == ("SELL", 3)
    assert flatten_intent_from_position(paper_short) == ("BUY", -4)
    assert flatten_intent_from_position(Position(symbol="MES", quantity=0, avg_price=0.0, side="BUY")) is None
    unsigned_sell = assert_validation_gate_or_block(
        "emergency_order_endpoints",
        emergency=True,
        order_side="SELL",
        live_position_qty=-2,
        order_qty=2,
        reason="api_emergency_stop",
    )
    assert unsigned_sell == (False, UNGATED_PLACE_BLOCK_REASON)


@pytest.mark.unit
def test_emergency_flatten_covers_fabric_short_and_rejects_unreadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    lumina_os = ROOT / "lumina_os"
    if str(lumina_os) not in sys.path:
        sys.path.insert(0, str(lumina_os))
    from lumina_core.broker.broker_bridge.schemas import OrderResult
    from lumina_os.backend import emergency_order_endpoints as em

    captured: list[Order] = []

    class _Broker:
        def __init__(self, positions: list[Position]) -> None:
            self._positions = positions

        def connect(self) -> None:
            return None

        def disconnect(self) -> None:
            return None

        def get_positions(self) -> list[Position]:
            return list(self._positions)

        def submit_order(self, order: Order) -> OrderResult:
            captured.append(order)
            return OrderResult(accepted=True, order_id="flat-1", status="filled", message="ok")

    monkeypatch.setattr(
        em,
        "_create_emergency_broker",
        lambda: _Broker([Position(symbol="MNQ", quantity=2, avg_price=1.0, side="SHORT")]),
    )
    out = em._execute_emergency_flatten()
    assert out["status"] == "ok"
    assert out["flattened_count"] == 1
    assert captured[0].side == "BUY"
    assert captured[0].quantity == 2
    assert captured[0].metadata.get("reduce_only") is True
    captured.clear()
    monkeypatch.setattr(
        em,
        "_create_emergency_broker",
        lambda: _Broker([SimpleNamespace(symbol="MNQ", quantity="nope", side="SHORT")]),  # type: ignore[list-item]
    )
    with pytest.raises(em.HTTPException) as blocked:
        em._execute_emergency_flatten()
    assert blocked.value.status_code == 503
    assert captured == []


@pytest.mark.unit
def test_eod_and_paper_executor_cover_fabric_short() -> None:
    from lumina_core.engine.paper_trade_executor import PaperTradeExecutor

    mock_broker = MagicMock()
    mock_broker.submit_order.return_value = type("Res", (), {"accepted": True})()
    executor = PaperTradeExecutor(broker=mock_broker, engine=SimpleNamespace(live_position_qty=-2))
    short = Position(symbol="MNQ", quantity=2, avg_price=1.0, side="SHORT")
    res = executor.build_and_submit_eod_close(pos=short, mode="sim")
    assert getattr(res, "accepted", False) is True
    sent = mock_broker.submit_order.call_args[0][0]
    assert sent.side == "BUY"
    assert sent.quantity == 2
    mock_broker.submit_order.reset_mock()
    long = Position(symbol="MES", quantity=2, avg_price=1.0, side="LONG")
    res_long = executor.build_and_submit_eod_close(pos=long, mode="sim")
    assert getattr(res_long, "accepted", False) is True
    sent_long = mock_broker.submit_order.call_args[0][0]
    assert sent_long.side == "SELL"
    assert sent_long.quantity == 2
    unreadable = executor.build_and_submit_eod_close(pos=SimpleNamespace(symbol="MES", quantity="x"), mode="sim")
    assert getattr(unreadable, "accepted", True) is False


@pytest.mark.unit
def test_fabric_modify_order_is_s0_blocked() -> None:
    from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient

    client = FabricGrpcClient(FabricConfig(host="127.0.0.1", port=1, mode_context="sim"))
    client._connected = True

    def _rpc(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise AssertionError("modify must not RPC in S0")

    client._send_and_wait = _rpc  # type: ignore[method-assign]
    out = client.modify_order_sync(client_order_id="m1", quantity=3, price=1.0)
    assert out == blocked_fabric_place_result()


@pytest.mark.unit
def test_bridge_submit_frame_missing_qty_is_zero_not_one() -> None:
    text = (ROOT / "lumina_core" / "broker" / "ninjatrader" / "bridge_command_sync.py").read_text(encoding="utf-8")
    assert "int(frame.get(\"quantity\") or 0)" in text
    assert "int(frame.get(\"quantity\", 1) or 1)" not in text
