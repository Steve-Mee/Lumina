"""Fail-closed kill battery for S0 freeze + ResearchBridge. No pytest."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import PromotionCandidate
from lumina_core.agent_orchestration.schemas_research_execution import RESEARCH_EXECUTION_FILL_TOPIC
from lumina_core.broker.broker_bridge.schemas import Order, Position
from lumina_core.order_gatekeeper.ungated_place_block import (
    EMERGENCY_REASONS,
    EMERGENCY_SOURCES,
    S0_PLACE_SOURCE_ALLOWLIST,
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
    blocked_fabric_place_result,
    blocked_order_result,
    flatten_intent_from_position,
    freeze_is_armed,
    gate_order,
    inspect_order_flags,
    instrument_root,
    is_emergency_reason,
    is_risk_reducing_side,
    live_qty_from_broker_book,
    live_qty_from_order_or_engine,
    live_qty_from_positions,
    research_execution_mode_from_mapping,
    signed_qty_from_position,
)
from lumina_core.research_bridge.costs import hypothetical_execution_costs, tick_value_usd
from lumina_core.research_bridge.horizon import HorizonRefused, require_expected_horizon_bars
from lumina_core.research_bridge.install import attach_shadow_runtime
from lumina_core.research_bridge.jsonl import append_shadow_record, default_shadow_jsonl_path
from lumina_core.research_bridge.market_health import (
    FRESH_BAR_MAX_AGE_SEC,
    LOST_CONNECTION,
    STALE_OR_MISSING,
    MarketHealth,
    healthy_closed_bar,
    unhealthy_market,
)
from lumina_core.research_bridge.shadow_runtime import ShadowRuntime
from lumina_research.agents.provenance import ProvenanceAuthority
from tests.research_bridge.helpers import make_runtime, sealed_candidate, unsigned_candidate_fields


def _refuse(exc: type[BaseException], fn: object, *args: object, **kwargs: object) -> None:
    try:
        if callable(fn):
            fn(*args, **kwargs)
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}")


def _block(source: str, **kwargs: object) -> None:
    allowed, reason = assert_validation_gate_or_block(source, **kwargs)  # type: ignore[arg-type]
    if allowed is not False or reason != UNGATED_PLACE_BLOCK_REASON:
        raise AssertionError(f"expected S0 block for {source} got {(allowed, reason)}")


def _allow(source: str, want: str, **kwargs: object) -> None:
    allowed, reason = assert_validation_gate_or_block(source, **kwargs)  # type: ignore[arg-type]
    if allowed is not True or reason != want:
        raise AssertionError(f"expected {want} for {source} got {(allowed, reason)}")


def _freeze_battery() -> None:
    if freeze_is_armed() is not True:
        raise AssertionError("S0 freeze must stay armed")
    if research_execution_mode_from_mapping(None) != "off":
        raise AssertionError("missing mode is off")
    if research_execution_mode_from_mapping({"research_execution_mode": "live"}) != "off":
        raise AssertionError("illegal mode is off")
    if research_execution_mode_from_mapping({"research_execution_mode": "SHADOW"}) != "shadow":
        raise AssertionError("shadow mode parse")
    _block("supervisor_tick_exec.run_tick_exec", order_side="BUY", live_position_qty=0, order_qty=1)
    _block("operations_service_orders.place_order", order_side="SELL", source_agent="research_bridge")
    _block(
        "emergency_order_endpoints",
        emergency=True,
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        reason="api_emergency_stop",
    )
    _block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=1,
        order_qty=2,
    )
    _block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=0,
        order_qty=1,
    )
    _block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=-1,
        order_qty=1,
    )
    _allow(
        "emergency_order_endpoints",
        "emergency_flatten_or_cancel_allowed",
        emergency=True,
        order_side="SELL",
        live_position_qty=2,
        order_qty=2,
        reason="api_emergency_stop",
    )
    _allow(
        "policy_engine.execute_order",
        "reduce_only_allowed",
        reduce_only=True,
        order_side="BUY",
        live_position_qty=-1,
        order_qty=1,
    )
    if is_risk_reducing_side(order_side="SELL", live_position_qty=1, order_qty=1) is not True:
        raise AssertionError("exact long flatten is reducing")
    if is_risk_reducing_side(order_side="SELL", live_position_qty=1, order_qty=2) is not False:
        raise AssertionError("flip is not reducing")
    if is_risk_reducing_side(order_side="HOLD", live_position_qty=1, order_qty=1) is not False:
        raise AssertionError("HOLD is not reducing")
    if signed_qty_from_position(Position(symbol="MNQ", quantity=2, avg_price=1.0, side="SHORT")) != -2:
        raise AssertionError("fabric SHORT must be negative")
    if live_qty_from_positions([Position(symbol="MES JUN26", quantity=-3, avg_price=1.0, side="SELL")], "MES") != -3:
        raise AssertionError("paper short net")
    if live_qty_from_positions("nope", "MES") is not None:
        raise AssertionError("string book is unreadable")
    if live_qty_from_positions([Position(symbol="MES", quantity=1, avg_price=1.0, side="BUY")], "") is not None:
        raise AssertionError("empty symbol is unreadable")
    if live_qty_from_positions(object(), "MES") is not None:  # type: ignore[arg-type]
        raise AssertionError("non-iterable book is unreadable")
    if live_qty_from_order_or_engine(
        Order(symbol="MES", side="SELL", quantity=1, metadata={"live_position_qty": 99}),
        SimpleNamespace(live_position_qty=0),
        None,
    ) != 0:
        raise AssertionError("metadata live qty must be ignored")
    spoof = Order(symbol="MES", side="SELL", quantity=1, metadata={"reduce_only": True, "live_position_qty": 99})
    allowed, reason = gate_order("policy_engine.execute_order", spoof, engine=SimpleNamespace(live_position_qty=0))
    if allowed is not False or reason != UNGATED_PLACE_BLOCK_REASON:
        raise AssertionError("metadata spoof must not flatten")
    flags = inspect_order_flags(None)
    if flags != (False, "", "", None):
        raise AssertionError(f"missing order flags {flags}")
    blocked = blocked_order_result()
    if blocked.accepted is not False or blocked.message != UNGATED_PLACE_BLOCK_REASON:
        raise AssertionError("blocked_order_result shape")
    fabric = blocked_fabric_place_result()
    if fabric.get("code") != UNGATED_PLACE_BLOCK_REASON or fabric.get("type") != "error":
        raise AssertionError("blocked_fabric_place_result shape")
    if live_qty_from_broker_book(None, "MES") is not None:
        raise AssertionError("missing broker is unreadable")
    book = SimpleNamespace(get_positions=lambda: [Position(symbol="MES", quantity=1, avg_price=1.0, side="BUY")])
    if live_qty_from_broker_book(book, "MES") != 1:
        raise AssertionError("broker book long")
    if instrument_root("mes jun26") != "MES" or instrument_root("") != "" or instrument_root(None) != "":
        raise AssertionError("instrument_root")
    if is_emergency_reason("api_emergency_stop") is not True or is_emergency_reason("nope") is not False:
        raise AssertionError("emergency reason set")
    if "eod_force_close" not in EMERGENCY_SOURCES or "eod_force_close" not in EMERGENCY_REASONS:
        raise AssertionError("emergency sets drifted")
    if live_qty_from_positions([Position(symbol="MNQ", quantity=1, avg_price=1.0, side="LONG")], "MES") != 0:
        raise AssertionError("unmatched root is flat")
    if is_risk_reducing_side(order_side="BUY", live_position_qty=-2, order_qty=2) is not True:
        raise AssertionError("exact short cover is reducing")
    if is_risk_reducing_side(order_side="BUY", live_position_qty=-2, order_qty=3) is not False:
        raise AssertionError("oversize cover flips")
    if research_execution_mode_from_mapping({"research_execution_mode": "sim"}) != "sim":
        raise AssertionError("sim mode parse")
    if research_execution_mode_from_mapping({"research_execution_mode": "  "}) != "off":
        raise AssertionError("blank mode is off")
    allowed, reason = gate_order("operations_service_orders.place_order", None)
    if allowed is not False or reason != UNGATED_PLACE_BLOCK_REASON:
        raise AssertionError("missing order is blocked")
    inspect_bad = inspect_order_flags(Order(symbol="MES", side="buy", quantity=2, metadata="x"))  # type: ignore[arg-type]
    if inspect_bad[0] is not False or inspect_bad[2] != "BUY" or inspect_bad[3] != 2:
        raise AssertionError(f"inspect fail-closed {inspect_bad}")
    if S0_PLACE_SOURCE_ALLOWLIST:
        raise AssertionError("S0 allow-list must stay empty")
    if flatten_intent_from_position(Position(symbol="MNQ", quantity=2, avg_price=1.0, side="SHORT")) != ("BUY", -2):
        raise AssertionError("fabric short flatten is BUY")
    if flatten_intent_from_position(Position(symbol="ES", quantity=3, avg_price=1.0, side="LONG")) != ("SELL", 3):
        raise AssertionError("fabric long flatten is SELL")
    if flatten_intent_from_position(Position(symbol="MES", quantity=1, avg_price=1.0, side="LONG")) != ("SELL", 1):
        raise AssertionError("one-lot long flatten is SELL")
    if flatten_intent_from_position(Position(symbol="MES", quantity=0, avg_price=0.0, side="BUY")) is not None:
        raise AssertionError("flat has no flatten intent")
    _block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="BUY",
        live_position_qty=1,
        order_qty=1,
    )
    _block(
        "policy_engine.execute_order",
        order_side="SELL",
        live_position_qty=1,
        order_qty=1,
    )
    _block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=1,
        order_qty=None,
    )
    _block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=1,
        order_qty="x",
    )
    _block(
        "eod_force_close",
        emergency=True,
        order_side="SELL",
        live_position_qty=3,
        order_qty=0,
        reason="eod_force_close",
    )
    _allow(
        "eod_force_close",
        "emergency_flatten_or_cancel_allowed",
        order_side="SELL",
        live_position_qty=1,
        order_qty=1,
    )
    _allow(
        "heartbeat_watchdog",
        "emergency_flatten_or_cancel_allowed",
        order_side="SELL",
        live_position_qty=1,
        order_qty=1,
        reason="heartbeat_watchdog_flatten",
    )
    _allow(
        "eod_force_close",
        "emergency_flatten_or_cancel_allowed",
        emergency=False,
        reduce_only=True,
        order_side="BUY",
        live_position_qty=-2,
        order_qty=2,
        reason="eod_force_close",
    )
    if is_risk_reducing_side(order_side="SELL", live_position_qty=3, order_qty=1) is not True:
        raise AssertionError("partial long reduce is reducing")
    if is_risk_reducing_side(order_side="BUY", live_position_qty=-3, order_qty=1) is not True:
        raise AssertionError("partial short cover is reducing")
    if is_risk_reducing_side(order_side="buy", live_position_qty=-1, order_qty=1) is not True:
        raise AssertionError("side is case-insensitive")
    if signed_qty_from_position(SimpleNamespace(quantity="x", side="LONG")) is not None:
        raise AssertionError("bad qty is unreadable")
    if signed_qty_from_position(Position(symbol="MES", quantity=4, avg_price=1.0, side="BUY")) != 4:
        raise AssertionError("BUY is long")
    if live_qty_from_broker_book(SimpleNamespace(), "MES") is not None:
        raise AssertionError("missing get_positions is unreadable")

    class _Boom:
        def get_positions(self) -> list[Position]:
            raise RuntimeError("book down")

    if live_qty_from_broker_book(_Boom(), "MES") is not None:
        raise AssertionError("broker exception is unreadable")
    reduce_order = Order(
        symbol="MES",
        side="SELL",
        quantity=1,
        metadata={"reduce_only": True, "reason": "paper_stop_or_target_close"},
    )
    allowed, reason = gate_order(
        "paper_simulator.check_close",
        reduce_order,
        app=SimpleNamespace(sim_position_qty=1),
        engine=SimpleNamespace(live_position_qty=0),
    )
    if allowed is not True or reason != "reduce_only_allowed":
        raise AssertionError("app qty wins over engine")
    allowed, reason = gate_order(
        "policy_engine.execute_order",
        reduce_order,
        live_position_qty=1,
        broker=SimpleNamespace(get_positions=lambda: []),
    )
    if allowed is not True:
        raise AssertionError("explicit live qty wins over empty book")
    if live_qty_from_order_or_engine(None, SimpleNamespace(live_position_qty=2), None) != 2:
        raise AssertionError("engine live qty")
    if live_qty_from_order_or_engine(None, SimpleNamespace(live_position_qty=2), SimpleNamespace()) != 2:
        raise AssertionError("missing sim qty falls through to engine")
    if instrument_root("  nq 06-26 ") != "NQ":
        raise AssertionError("root strips and uppercases")
    custom = blocked_order_result("nope")
    if custom.message != "nope" or custom.accepted is not False:
        raise AssertionError("custom blocked message")
    if blocked_fabric_place_result("nope").get("code") != "nope":
        raise AssertionError("custom fabric block")
    flags = inspect_order_flags(
        Order(symbol="MES", side="SELL", quantity=1, metadata={"reduce_only": True, "reason": "eod_force_close"})
    )
    if flags[0] is not True or flags[1] != "eod_force_close":
        raise AssertionError("inspect reduce_only and reason")
    if is_emergency_reason(" API_EMERGENCY_STOP ") is not True:
        raise AssertionError("emergency reason is case-insensitive")
    if research_execution_mode_from_mapping({"research_execution_mode": "SHADOW"}) != "shadow":
        raise AssertionError("shadow casefold")
    if live_qty_from_positions([], "MES") != 0:
        raise AssertionError("empty book is flat")
    if live_qty_from_positions(b"nope", "MES") is not None:
        raise AssertionError("bytes book is unreadable")
    if live_qty_from_positions(None, "MES") is not None:
        raise AssertionError("missing positions unreadable")
    proto_short = SimpleNamespace(instrument="MNQ 06-26", quantity=2, side="SHORT")
    if live_qty_from_positions([proto_short], "MNQ") != -2:
        raise AssertionError("instrument attr short")


def _horizon_costs_battery() -> None:
    _refuse(HorizonRefused, require_expected_horizon_bars, None, oos_size=30)
    _refuse(HorizonRefused, require_expected_horizon_bars, 0, oos_size=30)
    _refuse(HorizonRefused, require_expected_horizon_bars, True)
    if require_expected_horizon_bars(8, oos_size=30) != 8:
        raise AssertionError("horizon 8")
    if abs(tick_value_usd("MES") - 1.25) > 1e-12:
        raise AssertionError("MES tick value")
    if abs(tick_value_usd("ES") - 12.50) > 1e-12:
        raise AssertionError("ES tick value")
    if abs(tick_value_usd("MNQ") - 0.50) > 1e-12:
        raise AssertionError("MNQ tick value")
    if abs(tick_value_usd("NQ") - 5.00) > 1e-12:
        raise AssertionError("NQ tick value")
    mes = hypothetical_execution_costs(instrument="MES", direction="BUY", size=1.0, reference_price=5000.0)
    es = hypothetical_execution_costs(instrument="ES", direction="BUY", size=1.0, reference_price=5000.0)
    mnq = hypothetical_execution_costs(instrument="MNQ", direction="SELL", size=1.0, reference_price=20_000.0)
    nq = hypothetical_execution_costs(instrument="NQ", direction="BUY", size=1.0, reference_price=20_000.0)
    two = hypothetical_execution_costs(instrument="MES", direction="BUY", size=1.0, reference_price=5000.0, qty=2)
    if abs(mes.commission_usd - 0.94) > 1e-12 or abs(es.commission_usd - 2.87) > 1e-12:
        raise AssertionError("ADR-0055 free-plan commission")
    if abs(nq.commission_usd - 2.87) > 1e-12 or abs(mnq.commission_usd - 0.94) > 1e-12:
        raise AssertionError("NQ/MNQ commission")
    if abs(two.commission_usd - 1.88) > 1e-12 or abs(two.slippage_usd - 2.50) > 1e-12:
        raise AssertionError("qty scales commission and slippage")
    if abs(mes.slippage_usd - 1.25) > 1e-12 or abs(mnq.slippage_usd - 0.50) > 1e-12:
        raise AssertionError("one-tick slippage dollars")
    if abs(mes.slippage_ticks - 1.0) > 1e-12:
        raise AssertionError("one-tick slippage ticks")
    if abs(mes.fill_price - 5000.25) > 1e-12:
        raise AssertionError("BUY fill is +tick")
    if abs(mnq.fill_price - 19_999.75) > 1e-12:
        raise AssertionError("SELL fill is -tick")
    if abs(mes.commission_ticks - (0.94 / 1.25)) > 1e-12:
        raise AssertionError("MES commission ticks")
    if abs(mnq.commission_ticks - (0.94 / 0.50)) > 1e-12:
        raise AssertionError("MNQ commission ticks")
    penny = hypothetical_execution_costs(instrument="MES", direction="BUY", size=1.0, reference_price=1.0)
    if abs(penny.fill_price - 1.25) > 1e-12:
        raise AssertionError("reference_price 1.0 is valid")
    frac = hypothetical_execution_costs(instrument="MES", direction="BUY", size=0.4, reference_price=5000.0)
    if abs(frac.commission_usd - 0.94) > 1e-12:
        raise AssertionError("fractional size still one contract")
    _refuse(ValueError, hypothetical_execution_costs, instrument="MES", direction="BUY", size=1.0, reference_price=0.0)
    _refuse(ValueError, hypothetical_execution_costs, instrument="MES", direction="BUY", size=0.0, reference_price=5000.0)
    try:
        hypothetical_execution_costs(instrument="MES", direction="BUY", size=1.0, reference_price=5000.0, qty=0)
    except ValueError as exc:
        if "quantity must be >= 1" not in str(exc):
            raise AssertionError("qty=0 message") from exc
    else:
        raise AssertionError("qty=0 must raise quantity")
    _refuse(ValueError, hypothetical_execution_costs, instrument="MES", direction="BUY", size=1.0, reference_price=float("nan"))
    _refuse(ValueError, hypothetical_execution_costs, instrument="MES", direction="BUY", size=float("inf"), reference_price=5000.0)
    _refuse(HorizonRefused, require_expected_horizon_bars, -1, oos_size=8)
    _refuse(HorizonRefused, require_expected_horizon_bars, 8.0)
    if require_expected_horizon_bars(1, oos_size=99) != 1:
        raise AssertionError("horizon 1")
    es_sell = hypothetical_execution_costs(instrument="ES", direction="SELL", size=1.0, reference_price=5000.0)
    if abs(es_sell.fill_price - (5000.0 - 0.25)) > 1e-12:
        raise AssertionError("ES SELL fill is -tick")
    if abs(es_sell.slippage_usd - 12.50) > 1e-12:
        raise AssertionError("ES one-tick dollars")
    sized = hypothetical_execution_costs(instrument="MES", direction="BUY", size=2.0, reference_price=5000.0)
    if abs(sized.commission_usd - 1.88) > 1e-12 or abs(sized.slippage_usd - 2.50) > 1e-12:
        raise AssertionError("size 2 without qty still two contracts")
    if mes.research_total_usd is None:
        raise AssertionError("research four-leg must return dollars")
    execution_total = float(mes.commission_usd + mes.slippage_usd)
    want_disc = abs(float(mes.research_total_usd) - execution_total) > 1e-12
    if mes.discrepancy is not want_disc:
        raise AssertionError("discrepancy flag")
    if abs(es.tick_value_usd - 12.50) > 1e-12 or abs(nq.tick_value_usd - 5.00) > 1e-12:
        raise AssertionError("tick value on costs")
    if abs(mes.tick_size - 0.25) > 1e-12:
        raise AssertionError("MES tick size")
    if abs(es.commission_ticks - (2.87 / 12.50)) > 1e-12:
        raise AssertionError("ES commission ticks")


def _market_battery() -> None:
    bad = unhealthy_market()
    allowed, reason = bad.allow_new_intents()
    if allowed is not False or reason != LOST_CONNECTION or bad.reference_price() is not None:
        raise AssertionError("default market is lost")
    stale = healthy_closed_bar(close=5000.0, age_sec=121.0)
    allowed, reason = stale.allow_new_intents()
    if allowed is not False or reason != STALE_OR_MISSING:
        raise AssertionError("stale bar must refuse")
    ok = healthy_closed_bar(close=5000.0, age_sec=1.0)
    allowed, reason = ok.allow_new_intents()
    if allowed is not True or reason != "ok" or ok.reference_price() != 5000.0:
        raise AssertionError("fresh bar must allow")
    nan = healthy_closed_bar(close=float("nan"), age_sec=1.0)
    if nan.allow_new_intents()[0] is not False or nan.reference_price() is not None:
        raise AssertionError("nan close is stale")
    if abs(FRESH_BAR_MAX_AGE_SEC - 120.0) > 1e-12:
        raise AssertionError("fresh bar max age")
    forming = MarketHealth(connection_alive=True, forming_only=True, last_closed_close=5000.0, last_closed_age_sec=1.0)
    if forming.allow_new_intents() != (False, STALE_OR_MISSING):
        raise AssertionError("forming-only is stale")
    missing_close = MarketHealth(connection_alive=True, forming_only=False, last_closed_close=None, last_closed_age_sec=1.0)
    if missing_close.allow_new_intents()[0] is not False:
        raise AssertionError("missing close is stale")
    zero = MarketHealth(connection_alive=True, forming_only=False, last_closed_close=0.0, last_closed_age_sec=1.0)
    if zero.allow_new_intents()[0] is not False:
        raise AssertionError("zero close is stale")
    missing_age = MarketHealth(connection_alive=True, forming_only=False, last_closed_close=5000.0, last_closed_age_sec=None)
    if missing_age.allow_new_intents()[0] is not False:
        raise AssertionError("missing age is stale")
    neg = MarketHealth(connection_alive=True, forming_only=False, last_closed_close=5000.0, last_closed_age_sec=-1.0)
    if neg.allow_new_intents()[0] is not False:
        raise AssertionError("negative age is stale")
    edge = healthy_closed_bar(close=5000.0, age_sec=120.0)
    if edge.allow_new_intents()[0] is not True:
        raise AssertionError("age == max is still fresh")
    over = healthy_closed_bar(close=5000.0, age_sec=120.0001)
    if over.allow_new_intents()[0] is not False:
        raise AssertionError("age just over max is stale")
    inf_close = MarketHealth(connection_alive=True, forming_only=False, last_closed_close=float("inf"), last_closed_age_sec=1.0)
    if inf_close.allow_new_intents()[0] is not False or inf_close.reference_price() is not None:
        raise AssertionError("inf close is stale")
    neg_close = MarketHealth(connection_alive=True, forming_only=False, last_closed_close=-1.0, last_closed_age_sec=1.0)
    if neg_close.allow_new_intents()[0] is not False:
        raise AssertionError("negative close is stale")
    nan_age = MarketHealth(connection_alive=True, forming_only=False, last_closed_close=5000.0, last_closed_age_sec=float("nan"))
    if nan_age.allow_new_intents() != (False, STALE_OR_MISSING):
        raise AssertionError("nan age is stale")
    lost_alive = MarketHealth(connection_alive=False, forming_only=False, last_closed_close=5000.0, last_closed_age_sec=1.0)
    if lost_alive.allow_new_intents() != (False, LOST_CONNECTION):
        raise AssertionError("dead connection wins over fresh bar")
    if STALE_OR_MISSING != "stale_or_missing_market" or LOST_CONNECTION != "lost_connection":
        raise AssertionError("health codes")
    one = healthy_closed_bar(close=1.0, age_sec=0.0)
    if one.allow_new_intents()[0] is not True or one.reference_price() != 1.0:
        raise AssertionError("close 1.0 age 0 is fresh")
    if healthy_closed_bar(close=5000.0).last_closed_age_sec != 1.0:
        raise AssertionError("default age is 1s")
    dead = unhealthy_market()
    if dead.connection_alive is not False or dead.forming_only is not True:
        raise AssertionError("unhealthy default flags")


def _shadow_battery(tmp: Path) -> None:
    _bus, authority, runtime, alerts, observe = make_runtime(tmp, healthy=True, close=5000.0)
    if runtime._tape_kind != "synthetic":
        raise AssertionError("test runtime tape is synthetic")
    intent = runtime.on_candidate(sealed_candidate(authority, instrument="MES", quantity=2.0))
    if intent is None or intent.expected_horizon < 1 or intent.direction != "BUY":
        raise AssertionError("healthy sealed candidate must issue")
    runtime.assert_no_broker_submit()
    if len(runtime.issued_fills()) != 1:
        raise AssertionError("one hypothetical fill")
    if len(observe.calls) != 1:
        raise AssertionError("observe once")
    if int(runtime.issued_fills()[0].quantity) != 2:
        raise AssertionError("qty follows size when size >= 1")
    metric = observe.calls[0][1]
    if not isinstance(metric, (int, float)) or float(metric) >= 0.0:
        raise AssertionError("observe metric is negative cost")
    first_jsonl = (tmp / "research_shadow.jsonl").read_text(encoding="utf-8")
    if "shadow_fill_refused" in first_jsonl:
        raise AssertionError("healthy fill must not log refuse")
    if len(str(runtime.issued_fills()[0].fill_id)) < 10:
        raise AssertionError("shadow fill id length")
    fill = runtime.issued_fills()[0]
    if abs(float(fill.commission) - 1.88) > 1e-12:
        raise AssertionError("fill commission is free-plan MES qty 2")
    if fill.source != "hypothetical_adr0055":
        raise AssertionError("fill source")
    unsigned = PromotionCandidate.model_construct(**unsigned_candidate_fields())
    if runtime.on_candidate(unsigned) is not None:
        raise AssertionError("unsigned candidate must refuse")
    zero_fields = unsigned_candidate_fields(expected_horizon_bars=0)
    forged = PromotionCandidate.model_construct(**{**zero_fields, "issue_mac": authority.seal_issue(zero_fields)})
    if runtime.on_candidate(forged) is not None:
        raise AssertionError("missing horizon must refuse")
    runtime.replace_market(
        MarketHealth(connection_alive=True, forming_only=True, last_closed_close=5000.0, last_closed_age_sec=1.0)
    )
    if runtime.on_candidate(sealed_candidate(authority)) is not None:
        raise AssertionError("forming-only must refuse intent")
    runtime.replace_market(unhealthy_market())
    if runtime.shadow_fill(intent) is not None:
        raise AssertionError("lost market must refuse fill")
    runtime.assert_no_broker_submit()
    if not any("lost_connection" in str(item["code"]) or "stale" in str(item["code"]) for item in alerts.records):
        raise AssertionError("alerts must record refuse")
    if not any("lost connection: no new research" in str(item["message"]) for item in alerts.records):
        raise AssertionError("lost connection human message")
    if not any("stale or missing market: no new research" in str(item["message"]) for item in alerts.records):
        raise AssertionError("stale human message")
    attached = attach_shadow_runtime(EventBus(), jsonl_path=tmp / "install.jsonl")
    if attached.on_candidate(sealed_candidate(attached._authority)) is not None:
        raise AssertionError("install default market must refuse")
    attached.assert_no_broker_submit()
    dead = ShadowRuntime(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        jsonl_path=tmp / "dead.jsonl",
        market=unhealthy_market(),
        tape_kind="nt_pit",
    )
    if dead.on_candidate(sealed_candidate(dead._authority)) is not None:
        raise AssertionError("unhealthy default must refuse intent")
    dead.assert_no_broker_submit()
    dead._broker_submits = 1
    _refuse(AssertionError, dead.assert_no_broker_submit)
    ok_path = tmp / "ok.jsonl"
    append_shadow_record(ok_path, {"event": "signal_intent"})
    written = ok_path.read_text(encoding="utf-8")
    if "signal_intent" not in written or "ts_utc" not in written:
        raise AssertionError("jsonl write stamps ts_utc")
    before_nan = ok_path.read_text(encoding="utf-8")
    nan_ret = append_shadow_record(ok_path, {"event": "nan", "value": float("nan")})
    if nan_ret is not None:
        raise AssertionError("jsonl nan must return None")
    if ok_path.read_text(encoding="utf-8") != before_nan:
        raise AssertionError("jsonl must not persist nan")
    nested = tmp / "nested" / "shadow.jsonl"
    append_shadow_record(nested, {"z_last": 1, "a_first": 2})
    nested_line = nested.read_text(encoding="utf-8")
    if not nested.is_file():
        raise AssertionError("jsonl creates parent dirs")
    if nested_line.find("a_first") > nested_line.find("z_last"):
        raise AssertionError("jsonl sorts keys")
    blocker = tmp / "not_a_directory"
    blocker.write_text("x", encoding="utf-8")
    append_shadow_record(blocker / "shadow.jsonl", {"event": "refused"})
    path = default_shadow_jsonl_path()
    if path.name != "research_shadow.jsonl":
        raise AssertionError("default jsonl name")
    if math.isnan(float("nan")) is not True:
        raise AssertionError("nan")
    _ = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    fills_seen: list[object] = []

    def _cap_fill(event: object) -> None:
        payload = getattr(event, "payload", event)
        fills_seen.append(payload)

    _bus.subscribe(RESEARCH_EXECUTION_FILL_TOPIC, _cap_fill)
    runtime.replace_market(healthy_closed_bar(close=20_000.0, age_sec=1.0))
    sell_intent = runtime.on_candidate(sealed_candidate(authority, instrument="MNQ", direction="SELL"))
    if sell_intent is None or sell_intent.direction != "SELL" or sell_intent.expected_horizon < 1:
        raise AssertionError("SELL candidate must issue")
    sell_fill = runtime.issued_fills()[-1]
    if str(sell_fill.side).upper() != "SELL":
        raise AssertionError("SELL fill side")
    if abs(float(sell_fill.commission) - 0.94) > 1e-12:
        raise AssertionError("MNQ free-plan commission")
    if not fills_seen:
        raise AssertionError("fill topic must publish")
    last_payload = fills_seen[-1]
    side = last_payload.get("side") if isinstance(last_payload, dict) else getattr(last_payload, "side", "")
    if str(side).upper() != "SELL":
        raise AssertionError(f"published fill side {side}")
    if runtime.observe_call_count() != len(observe.calls):
        raise AssertionError("observe_call_count")
    naive = ShadowRuntime(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        jsonl_path=tmp / "naive.jsonl",
        market=healthy_closed_bar(close=5000.0, age_sec=1.0),
        tape_kind="synthetic",
        clock=lambda: datetime(2026, 10, 28, 12, 0),
    )
    naive_intent = naive.on_candidate(sealed_candidate(naive._authority))
    if naive_intent is None or naive_intent.timestamp.tzinfo is None:
        raise AssertionError("naive clock must be stamped UTC")
    naive.assert_no_broker_submit()
    healthy_install = attach_shadow_runtime(
        EventBus(),
        authority=authority,
        jsonl_path=tmp / "healthy_install.jsonl",
        market=healthy_closed_bar(close=5000.0, age_sec=1.0),
        tape_kind="nt_pit",
    )
    if healthy_install._tape_kind != "nt_pit":
        raise AssertionError("install tape_kind")
    installed_intent = healthy_install.on_candidate(sealed_candidate(authority))
    if installed_intent is None:
        raise AssertionError("explicit healthy install must issue")
    healthy_install.assert_no_broker_submit()
    install_jsonl = tmp / "healthy_install.jsonl"
    if not install_jsonl.is_file() or "signal_intent" not in install_jsonl.read_text(encoding="utf-8"):
        raise AssertionError("install must write the given jsonl path")
    if not str(runtime.issued_fills()[0].fill_id).startswith("shadow-"):
        raise AssertionError("shadow fill id prefix")
    if runtime.issued_intents()[0].source != "research_bridge":
        raise AssertionError("intent source is research_bridge")


def run() -> None:
    _freeze_battery()
    _horizon_costs_battery()
    _market_battery()
    with TemporaryDirectory() as tmp:
        _shadow_battery(Path(tmp))
