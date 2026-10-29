"""ATM (A) default, companion STOP (C) fallback, fail-closed if neither."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.broker.broker_bridge.schemas import Order, OrderResult
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.research_bridge.binding_policy import reduce_qty
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.market_health import healthy_closed_bar
from lumina_core.research_bridge.protective_attach import (
    ATM_STOP_ATR_MULTIPLE,
    ATM_STOP_ATR_PERIOD,
    DEFAULT_ATM_CONFIRM_TIMEOUT_MS,
    DEFAULT_COMPANION_CONFIRM_TIMEOUT_MS,
    FILL_BEFORE_ATM,
    GENERIC_ATM_INSTRUMENTS,
    GENERIC_ATM_TEMPLATE_NAME,
    PATH_ATM,
    PATH_COMPANION,
    PATH_REFUSED,
    PROTECTIVE_REFUSED,
    ProtectiveAttachConfig,
    atm_confirmed,
    atm_confirmed_on_time,
    companion_confirmed,
    emergency_flatten_order,
    from_engine,
    from_mapping,
    live_fill_without_confirmed_atm,
    plan_protective_attach,
    resolve_atm_template,
)
from lumina_core.research_bridge.sim_gate import bind_sim_gate
from lumina_core.research_bridge.sim_runtime import SimRuntime
from lumina_core.risk.alarm_executor import AlarmExecutor
from lumina_research.agents.provenance import ProvenanceAuthority
from tests.research_bridge.helpers import sealed_candidate
from tests.research_bridge.s3_helpers import RecordingSubmitter, fake_engine, passing_context

T0 = datetime(2026, 10, 29, 16, 36, tzinfo=timezone.utc)


class _JumpClock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def jump_ms(self, ms: int) -> None:
        self.now = self.now + timedelta(milliseconds=int(ms))


class _RejectAtm(RecordingSubmitter):
    def submit_order(self, order: Order) -> OrderResult:
        meta = order.metadata if isinstance(order.metadata, dict) else {}
        if str(meta.get("atm_strategy_template") or "").strip():
            self.orders.append(order)
            return OrderResult(accepted=False, order_id="", status="rejected", message="atm_attach_failed")
        return super().submit_order(order)


class _AcceptAtmUnconfirmed(RecordingSubmitter):
    def submit_order(self, order: Order) -> OrderResult:
        meta = order.metadata if isinstance(order.metadata, dict) else {}
        if str(meta.get("atm_strategy_template") or "").strip():
            self.stack_at_submit = []
            self.orders.append(order)
            return OrderResult(accepted=True, order_id="sim-atm", status="accepted", message="ok", raw={})
        return super().submit_order(order)


class _SlowStop(RecordingSubmitter):
    def __init__(self, clock: _JumpClock) -> None:
        super().__init__()
        self.clock = clock

    def submit_order(self, order: Order) -> OrderResult:
        if str(order.order_type).upper() == "STOP":
            self.clock.jump_ms(6000)
        return super().submit_order(order)


def _runtime(
    tmp_path: Path,
    submitter: RecordingSubmitter,
    *,
    protective: ProtectiveAttachConfig | None = None,
    clock: _JumpClock | None = None,
    alarm: AlarmExecutor | None = None,
) -> SimRuntime:
    ctx = passing_context()
    bind_sim_gate(ctx)
    return SimRuntime(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        jsonl_path=tmp_path / "s4-atm.jsonl",
        market=healthy_closed_bar(close=5000.0),
        fill_index=FillIndex(),
        gate_ctx=ctx,
        engine=fake_engine(),
        submitter=submitter,
        pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
        protective=protective,
        clock=clock,
        alarm_executor=alarm,
    )


@pytest.mark.unit
def test_resolve_template_prefers_connection_then_account() -> None:
    cfg = from_mapping(
        {
            "atm": {
                "default_template": "DefaultTpl",
                "templates_by_account": {"Sim101": "AcctTpl"},
                "templates_by_connection": {"playback": ""},
                "fallback_companion": True,
            }
        },
        account="Sim101",
        connection="playback",
    )
    assert resolve_atm_template(cfg) == ""
    plan = plan_protective_attach(cfg)
    assert plan.path == PATH_COMPANION
    cfg2 = from_mapping(
        {"atm": {"templates_by_account": {"Sim101": "LuminaProtective"}}},
        account="Sim101",
    )
    assert plan_protective_attach(cfg2).path == PATH_ATM
    assert plan_protective_attach(cfg2).atm_template == GENERIC_ATM_TEMPLATE_NAME
    assert GENERIC_ATM_TEMPLATE_NAME == "LuminaProtective"
    assert GENERIC_ATM_INSTRUMENTS == ("ES", "NQ", "MES", "MNQ")
    assert ATM_STOP_ATR_PERIOD == 14
    assert ATM_STOP_ATR_MULTIPLE == 1.5
    refused = from_mapping({"atm": {"fallback_companion": False}}, account="Sim101")
    plan_r = plan_protective_attach(refused)
    assert plan_r.path == PATH_REFUSED
    assert plan_r.reason == PROTECTIVE_REFUSED
    zero_timeout = from_mapping({"atm": {"companion_confirm_timeout_ms": 0}})
    assert zero_timeout.companion_confirm_timeout_ms == 5000
    reduce_plan = plan_protective_attach(cfg2, reduce_only=True)
    assert reduce_plan.path == PATH_REFUSED
    assert reduce_plan.reason == "reduce_only"


@pytest.mark.unit
@pytest.mark.safety_gate
def test_atm_path_does_not_submit_companion(tmp_path: Path) -> None:
    submitter = RecordingSubmitter()
    protective = ProtectiveAttachConfig(
        templates_by_account=(("Sim101", "LuminaProtective"),),
        account="Sim101",
    )
    runtime = _runtime(tmp_path, submitter, protective=protective)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is not None
    assert result.accepted is True
    assert atm_confirmed(result) is True
    assert len(submitter.orders) == 1
    assert submitter.orders[0].metadata.get("atm_strategy_template") == "LuminaProtective"
    assert len(runtime._fill_index) == 1
    bind_sim_gate(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_atm_reject_does_not_retry_entry(tmp_path: Path) -> None:
    submitter = _RejectAtm()
    protective = ProtectiveAttachConfig(
        templates_by_account=(("Sim101", "LuminaProtective"),),
        account="Sim101",
        fallback_companion=True,
    )
    runtime = _runtime(tmp_path, submitter, protective=protective)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is None or result.accepted is not True
    assert len(runtime._fill_index) == 0
    types = [str(o.order_type).upper() for o in submitter.orders]
    assert types.count("MARKET") == 1
    assert "STOP" not in types
    bind_sim_gate(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_atm_live_unconfirmed_attaches_companion(tmp_path: Path) -> None:
    submitter = _AcceptAtmUnconfirmed()
    protective = ProtectiveAttachConfig(
        templates_by_account=(("Sim101", "LuminaProtective"),),
        account="Sim101",
        fallback_companion=True,
    )
    runtime = _runtime(tmp_path, submitter, protective=protective)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is not None
    assert result.accepted is True
    types = [str(o.order_type).upper() for o in submitter.orders]
    assert "STOP" in types
    assert len(runtime._fill_index) == 1
    bind_sim_gate(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_atm_live_unconfirmed_without_fallback_flattens(tmp_path: Path) -> None:
    submitter = _AcceptAtmUnconfirmed()
    protective = ProtectiveAttachConfig(
        templates_by_account=(("Sim101", "LuminaProtective"),),
        account="Sim101",
        fallback_companion=False,
    )
    runtime = _runtime(tmp_path, submitter, protective=protective)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is None
    assert len(runtime._fill_index) == 0
    reasons = [str(o.metadata.get("reason") or "") for o in submitter.orders]
    assert "unconfirmed_protective_stop" in reasons
    bind_sim_gate(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_atm_reject_without_fallback_refuses(tmp_path: Path) -> None:
    submitter = _RejectAtm()
    protective = ProtectiveAttachConfig(
        templates_by_account=(("Sim101", "LuminaProtective"),),
        account="Sim101",
        fallback_companion=False,
    )
    runtime = _runtime(tmp_path, submitter, protective=protective)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is None or result.accepted is not True
    assert len(runtime._fill_index) == 0
    assert any(str(o.order_type).upper() == "MARKET" for o in submitter.orders)
    bind_sim_gate(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_companion_timeout_flattens(tmp_path: Path) -> None:
    clock = _JumpClock()
    submitter = _SlowStop(clock)
    protective = ProtectiveAttachConfig(fallback_companion=True, companion_confirm_timeout_ms=5000, account="Sim101")
    positions = LivePositionManager(app=SimpleNamespace())
    alarm = AlarmExecutor(
        bus=EventBus(),
        positions=positions,
        submitter=submitter,
        jsonl_path=tmp_path / "alarm.jsonl",
        clock=clock,
    )
    runtime = _runtime(tmp_path, submitter, protective=protective, clock=clock, alarm=alarm)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is None
    assert len(runtime._fill_index) == 0
    reasons = [str(o.metadata.get("reason") or "") for o in submitter.orders]
    assert "unconfirmed_protective_stop" in reasons or any("alarm_executor" in r for r in reasons)
    bind_sim_gate(None)


@pytest.mark.unit
def test_companion_confirmed_respects_timeout() -> None:
    started = T0
    ok = OrderResult(accepted=True, order_id="s", status="accepted")
    assert companion_confirmed(ok, started=started, now=started + timedelta(milliseconds=100), timeout_ms=5000) is True
    assert companion_confirmed(ok, started=started, now=started + timedelta(milliseconds=5000), timeout_ms=5000) is True
    assert companion_confirmed(ok, started=started, now=started + timedelta(milliseconds=5001), timeout_ms=5000) is False
    assert companion_confirmed(ok, started=started, now=started + timedelta(milliseconds=6000), timeout_ms=5000) is False
    bad = OrderResult(accepted=False, order_id="", status="rejected")
    assert companion_confirmed(bad, started=started, now=started, timeout_ms=5000) is False


@pytest.mark.unit
def test_unconfirmed_stage_flattens_full_qty() -> None:
    assert reduce_qty("unconfirmed_protective_stop", 2) == 2


@pytest.mark.unit
def test_empty_template_is_companion_fallback() -> None:
    plan = plan_protective_attach(ProtectiveAttachConfig(account="Sim101"))
    assert plan.path == PATH_COMPANION
    assert "second order" in plan.residual_risk.lower() or "MARKET" in plan.residual_risk
    assert DEFAULT_COMPANION_CONFIRM_TIMEOUT_MS == 5000
    flat = emergency_flatten_order(instrument="MES", entry_side="BUY", quantity=2, strategy_id="hyp-a")
    assert flat.side == "SELL"
    assert flat.metadata.get("reason") == "unconfirmed_protective_stop"
    assert flat.metadata.get("reduce_only") is True
    cover = emergency_flatten_order(instrument="MNQ", entry_side="SELL", quantity=1, strategy_id="hyp-b")
    assert cover.side == "BUY"
    engine_cfg = from_engine(
        SimpleNamespace(
            nt_connected_account="Sim101",
            config=SimpleNamespace(
                ninjatrader={
                    "atm": {
                        "templates_by_account": {"Sim101": "LuminaProtective"},
                        "fallback_companion": True,
                    }
                }
            ),
        )
    )
    assert plan_protective_attach(engine_cfg).path == PATH_ATM


@pytest.mark.unit
@pytest.mark.safety_gate
def test_no_template_no_fallback_refuses_before_submit(tmp_path: Path) -> None:
    submitter = RecordingSubmitter()
    protective = ProtectiveAttachConfig(account="Sim101", fallback_companion=False)
    runtime = _runtime(tmp_path, submitter, protective=protective)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is None
    assert submitter.orders == []
    assert len(runtime._fill_index) == 0
    bind_sim_gate(None)


@pytest.mark.unit
def test_one_generic_atr_template_for_four_markets() -> None:
    cfg = from_mapping(
        {"atm": {"default_template": GENERIC_ATM_TEMPLATE_NAME, "fallback_companion": True}},
        account="Sim101",
    )
    plan = plan_protective_attach(cfg)
    assert plan.path == PATH_ATM
    assert plan.atm_template == GENERIC_ATM_TEMPLATE_NAME
    assert plan.atm_confirm_timeout_ms == DEFAULT_ATM_CONFIRM_TIMEOUT_MS
    assert "fill" in plan.residual_risk.lower() or "StartAtmStrategy" in plan.residual_risk
    for instrument in GENERIC_ATM_INSTRUMENTS:
        tagged = ProtectiveAttachConfig(
            default_template=GENERIC_ATM_TEMPLATE_NAME,
            account="Sim101",
        )
        assert plan_protective_attach(tagged).atm_template == GENERIC_ATM_TEMPLATE_NAME
        assert instrument in GENERIC_ATM_INSTRUMENTS


class _FillBeforeAtm(RecordingSubmitter):
    def submit_order(self, order: Order) -> OrderResult:
        meta = order.metadata if isinstance(order.metadata, dict) else {}
        if str(meta.get("atm_strategy_template") or "").strip() and str(order.order_type).upper() != "STOP":
            self.orders.append(order)
            return OrderResult(
                accepted=True,
                order_id="fill-before-atm",
                status="filled",
                filled_qty=int(order.quantity),
                message="ok",
                raw={},
            )
        return super().submit_order(order)


class _FillBeforeAtmHiddenReject(RecordingSubmitter):
    def submit_order(self, order: Order) -> OrderResult:
        meta = order.metadata if isinstance(order.metadata, dict) else {}
        if str(meta.get("atm_strategy_template") or "").strip() and str(order.order_type).upper() != "STOP":
            self.orders.append(order)
            return OrderResult(
                accepted=False,
                order_id="nt-filled",
                status="rejected",
                filled_qty=int(order.quantity),
                message=FILL_BEFORE_ATM,
                raw={"rejection_reason": FILL_BEFORE_ATM},
            )
        return super().submit_order(order)


class _SlowAtm(RecordingSubmitter):
    def __init__(self, clock: _JumpClock) -> None:
        super().__init__()
        self.clock = clock

    def submit_order(self, order: Order) -> OrderResult:
        meta = order.metadata if isinstance(order.metadata, dict) else {}
        if str(meta.get("atm_strategy_template") or "").strip() and str(order.order_type).upper() != "STOP":
            self.clock.jump_ms(6000)
        return super().submit_order(order)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_fill_before_atm_without_fallback_flattens(tmp_path: Path) -> None:
    submitter = _FillBeforeAtm()
    protective = ProtectiveAttachConfig(
        templates_by_account=(("Sim101", GENERIC_ATM_TEMPLATE_NAME),),
        account="Sim101",
        fallback_companion=False,
        atm_confirm_timeout_ms=5000,
    )
    runtime = _runtime(tmp_path, submitter, protective=protective)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is None
    assert len(runtime._fill_index) == 0
    reasons = [str(o.metadata.get("reason") or "") for o in submitter.orders]
    assert "unconfirmed_protective_stop" in reasons
    bind_sim_gate(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_fill_before_atm_keeps_companion_fallback(tmp_path: Path) -> None:
    submitter = _FillBeforeAtm()
    protective = ProtectiveAttachConfig(
        templates_by_account=(("Sim101", GENERIC_ATM_TEMPLATE_NAME),),
        account="Sim101",
        fallback_companion=True,
        atm_confirm_timeout_ms=5000,
    )
    runtime = _runtime(tmp_path, submitter, protective=protective)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MNQ"))
    assert result is not None
    assert result.accepted is True
    assert any(str(o.order_type).upper() == "STOP" for o in submitter.orders)
    bind_sim_gate(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_fill_before_atm_hidden_reject_flattens(tmp_path: Path) -> None:
    submitter = _FillBeforeAtmHiddenReject()
    protective = ProtectiveAttachConfig(
        templates_by_account=(("Sim101", GENERIC_ATM_TEMPLATE_NAME),),
        account="Sim101",
        fallback_companion=False,
    )
    runtime = _runtime(tmp_path, submitter, protective=protective)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
    assert result is None
    reasons = [str(o.metadata.get("reason") or "") for o in submitter.orders]
    assert "unconfirmed_protective_stop" in reasons
    bind_sim_gate(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_atm_confirm_timeout_flattens(tmp_path: Path) -> None:
    clock = _JumpClock()
    submitter = _SlowAtm(clock)
    protective = ProtectiveAttachConfig(
        templates_by_account=(("Sim101", GENERIC_ATM_TEMPLATE_NAME),),
        account="Sim101",
        fallback_companion=False,
        atm_confirm_timeout_ms=5000,
    )
    runtime = _runtime(tmp_path, submitter, protective=protective, clock=clock)
    result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MNQ"))
    assert result is None
    reasons = [str(o.metadata.get("reason") or "") for o in submitter.orders]
    assert "unconfirmed_protective_stop" in reasons
    bind_sim_gate(None)


@pytest.mark.unit
def test_atm_confirmed_on_time_and_live_fill_helpers() -> None:
    started = T0
    tagged = OrderResult(accepted=True, order_id="a", status="accepted", raw={"protective_attach": "atm"})
    assert atm_confirmed_on_time(tagged, started=started, now=started + timedelta(milliseconds=5000), timeout_ms=5000) is True
    assert atm_confirmed_on_time(tagged, started=started, now=started + timedelta(milliseconds=5001), timeout_ms=5000) is False
    empty = OrderResult(accepted=True, order_id="f", status="filled", filled_qty=1, raw={})
    assert live_fill_without_confirmed_atm(empty) is True
    hidden = OrderResult(
        accepted=False,
        order_id="h",
        status="rejected",
        filled_qty=1,
        message=FILL_BEFORE_ATM,
        raw={"rejection_reason": FILL_BEFORE_ATM},
    )
    assert live_fill_without_confirmed_atm(hidden) is True
    assert live_fill_without_confirmed_atm(tagged) is False
    zero = from_mapping({"atm": {"atm_confirm_timeout_ms": 0, "companion_confirm_timeout_ms": 5000}})
    assert zero.atm_confirm_timeout_ms == 5000
