"""Fail-closed kill battery for S4 SIM-entry hardening. No pytest."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.broker.broker_bridge.schemas import Order, OrderResult
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.engine.mode_capabilities import resolve_mode_capabilities
from lumina_core.order_gatekeeper.engine_helpers import MODES_REQUIRING_EQUITY_SNAPSHOT
from lumina_core.research_bridge.alerts import RecordingAlertSink, TelegramAlertSink, telegram_credentials_present
from lumina_core.research_bridge.binding_policy import reduce_qty
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.market_health import healthy_closed_bar
from lumina_core.research_bridge.continuity_meter import (
    FAR_MAX,
    POWER_MIN,
    PRODUCED_BY,
    TTD_FAST_MAX_DAYS,
    TTD_SLOW_MAX_DAYS,
    ContinuityMeterRefused,
    _floor_reason,
    fixture_closed_mes_daily_bars,
    measure_continuity,
    measure_fixture_daily,
)
from lumina_core.research_bridge.protective_attach import (
    ATM_STOP_ATR_MULTIPLE,
    ATM_UNCONFIRMED,
    ATTACH_ATM,
    COMPANION_UNCONFIRMED,
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
from lumina_core.research_bridge.protective_stop import (
    UNPROTECTED_ENTRY,
    companion_stop_order,
    default_stop_price,
    require_protective_stop,
)
from lumina_core.research_bridge.sim_gate import MIN_SURVIVORS, bind_sim_gate, evaluate
from lumina_core.research_bridge.sim_runtime import SimRuntime
from lumina_core.risk.alarm_executor import AlarmExecutor
from lumina_core.risk.risk_controller import HardRiskController
from lumina_core.risk.risk_limits import RiskLimits
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.cycles.sim_plan import SIM_MIN_SURVIVORS, SIM_TARGET_SURVIVORS
from lumina_research.validation.nt_tape import closed_bars_from_rows, fixture_closed_mes_bars
from tests.research_bridge.helpers import sealed_candidate
from tests.research_bridge.s3_helpers import RecordingSubmitter, fake_engine, passing_context, passing_meter, survivor
from tests.research_bridge.s3_mutant_kills import run as run_s3_kills

T0 = datetime(2026, 10, 29, 15, 39, tzinfo=timezone.utc)
TAPE_NOW = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


def _fail(message: str) -> None:
    raise AssertionError(message)


def run() -> None:
    run_s3_kills()
    _kill_floors()
    _kill_meter()
    _kill_duck_typed_meter()
    _kill_protective_stop()
    _kill_protective_attach()
    _kill_telegram()
    _kill_caps()
    _kill_stale_sim()
    _kill_prolonged()


def _kill_floors() -> None:
    if FAR_MAX != 0.10:
        _fail("FAR_MAX drifted")
    if TTD_FAST_MAX_DAYS != 15.0:
        _fail("TTD_FAST_MAX_DAYS drifted")
    if TTD_SLOW_MAX_DAYS != 45.0:
        _fail("TTD_SLOW_MAX_DAYS drifted")
    if POWER_MIN != 0.85:
        _fail("POWER_MIN drifted")
    if PRODUCED_BY != "continuity_meter.measure":
        _fail("PRODUCED_BY drifted")
    if MIN_SURVIVORS != 2:
        _fail("gate min survivors drifted")
    if SIM_MIN_SURVIVORS != 2:
        _fail("plan min survivors drifted")
    if SIM_TARGET_SURVIVORS != 3:
        _fail("plan target survivors drifted")
    if _floor_reason(0.11, 7.0, 17.0, 1.0) != "far_above_floor":
        _fail("FAR 0.11 passed floor")
    if _floor_reason(0.0, 16.0, 17.0, 1.0) != "ttd_fast_above_floor":
        _fail("TTD fast 16d passed floor")
    if _floor_reason(0.0, 7.0, 46.0, 1.0) != "ttd_slow_above_floor":
        _fail("TTD slow 46d passed floor")
    if _floor_reason(0.0, 7.0, 17.0, 0.84) != "power_below_floor":
        _fail("power 0.84 passed floor")
    if _floor_reason(0.10, 15.0, 45.0, 0.85) != "ok":
        _fail("boundary floors rejected")
    if _floor_reason(float("nan"), 7.0, 17.0, 1.0) != "far_unmeasured":
        _fail("NaN FAR measured")


def _kill_meter() -> None:
    report = measure_fixture_daily(instrument="MES")
    if report.produced_by != PRODUCED_BY or report.tape_kind != "nt_pit":
        _fail("fixture meter provenance")
    if report.passed is not True or report.reason != "ok":
        _fail(f"fixture meter failed {report.reason}")
    if report.far > FAR_MAX or report.ttd_fast_days > TTD_FAST_MAX_DAYS:
        _fail("fixture meter above floor")
    if report.ttd_slow_days > TTD_SLOW_MAX_DAYS or report.power < POWER_MIN:
        _fail("fixture meter power/slow floor")
    if len(report.bar_sha256) != 64:
        _fail("meter hash unbound")
    try:
        measure_continuity([], instrument="MES")
        _fail("empty bars measured")
    except ContinuityMeterRefused:
        pass
    try:
        measure_continuity("nope")  # type: ignore[arg-type]
        _fail("string bars measured")
    except ContinuityMeterRefused:
        pass
    bars = closed_bars_from_rows(fixture_closed_mes_bars(now=TAPE_NOW), now=TAPE_NOW, purpose="gate")
    try:
        measure_continuity(bars, instrument="MES")
        _fail("1m tape counted as TTD days")
    except ContinuityMeterRefused:
        pass
    try:
        measure_continuity(bars, instrument="ES")
        _fail("ES continuity measured")
    except ContinuityMeterRefused:
        pass
    try:
        fixture_closed_mes_daily_bars(n=10)
        _fail("short daily fixture allowed")
    except ContinuityMeterRefused:
        pass
    naive = datetime(2025, 1, 2, 21, 0)
    try:
        fixture_closed_mes_daily_bars(start=naive, now=TAPE_NOW)
        _fail("naive start allowed")
    except ContinuityMeterRefused:
        pass
    try:
        fixture_closed_mes_daily_bars(
            start=datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc),
            now=datetime(2025, 1, 2, 21, 0, tzinfo=timezone.utc),
        )
        _fail("future start allowed")
    except ContinuityMeterRefused:
        pass
    try:
        fixture_closed_mes_daily_bars(
            start=datetime(2025, 1, 2, 21, 0, tzinfo=timezone.utc),
            now=datetime(2025, 6, 1, 21, 0, tzinfo=timezone.utc),
        )
        _fail("short window produced 241 bars")
    except ContinuityMeterRefused:
        pass
    rows = fixture_closed_mes_daily_bars(now=TAPE_NOW)
    if float(rows[0]["close"]) != 5010.0 or float(rows[1]["close"]) != 4990.0:
        _fail("daily fixture close polarity drifted")
    if float(rows[0]["open"]) != 4990.0 or float(rows[1]["open"]) != 5010.0:
        _fail("daily fixture open polarity drifted")
    default_rows = fixture_closed_mes_daily_bars()
    if len(default_rows) < 241:
        _fail("default daily fixture too short")
    if abs(float(rows[0]["high"]) - max(float(rows[0]["open"]), float(rows[0]["close"])) - 0.5) > 1e-9:
        _fail("daily fixture high wick drifted")
    if abs(min(float(rows[0]["open"]), float(rows[0]["close"])) - 0.5 - float(rows[0]["low"])) > 1e-9:
        _fail("daily fixture low wick drifted")
    if int(rows[-1]["volume"]) != 1000 + (len(rows) - 1):
        _fail("daily fixture volume drifted")
    ok, reason = evaluate(passing_context(survivors=(survivor(tag="only", family="trend"),)))
    if ok is True or reason != "survivors_insufficient":
        _fail("one survivor opened S4 gate")
    ok, reason = evaluate(passing_context(meter=passing_meter()))
    if ok is not True:
        _fail(f"measured meter did not open gate {reason}")
    ok, reason = evaluate(passing_context(connected="Sim999", whitelist=("Sim101",)))
    if ok is True:
        _fail("non-whitelist sim allowed")


def _kill_duck_typed_meter() -> None:
    fake = SimpleNamespace(
        produced_by=PRODUCED_BY,
        tape_kind="nt_pit",
        bar_sha256="a" * 64,
        far=0.0,
        ttd_fast_days=7.0,
        ttd_slow_days=17.0,
        power=1.0,
        passed=True,
        reason="ok",
    )
    ok, reason = evaluate(passing_context(meter=fake))
    if ok is True or reason != "continuity_unmeasured":
        _fail("duck-typed continuity meter allowed")


def _kill_protective_stop() -> None:
    naked = Order(
        symbol="MES",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        metadata={"mode_context": "sim_real_guard"},
    )
    ok, reason = require_protective_stop(naked)
    if ok is True or reason != UNPROTECTED_ENTRY:
        _fail("unprotected sim_real_guard allowed")
    meta_only = Order(
        symbol="MES",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        metadata={"mode_context": "sim_real_guard", "stop_price": 4950.0},
    )
    ok, reason = require_protective_stop(meta_only)
    if ok is not True:
        _fail("metadata stop_price ignored")
    for raw in (True, "4950", float("nan")):
        bad = Order(
            symbol="MES",
            side="BUY",
            quantity=1,
            order_type="MARKET",
            metadata={"mode_context": "sim_real_guard", "stop_price": raw},
        )
        ok, reason = require_protective_stop(bad)
        if ok is True:
            _fail(f"invalid stop_price counted {raw!r}")
    paper = Order(
        symbol="MES",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        metadata={"mode_context": "paper"},
    )
    ok, reason = require_protective_stop(paper)
    if ok is not True:
        _fail("paper mode required a stop")
    emerg = Order(
        symbol="MES",
        side="SELL",
        quantity=1,
        order_type="MARKET",
        metadata={"mode_context": "sim_real_guard", "emergency": True},
    )
    ok, reason = require_protective_stop(emerg)
    if ok is not True:
        _fail("emergency required a stop")
    flatten = Order(
        symbol="MES",
        side="SELL",
        quantity=1,
        order_type="MARKET",
        metadata={"mode_context": "sim_real_guard", "reason": "flatten"},
    )
    ok, reason = require_protective_stop(flatten)
    if ok is not True:
        _fail("flatten reason required a stop")
    reduce = Order(
        symbol="MES",
        side="SELL",
        quantity=1,
        order_type="MARKET",
        metadata={"mode_context": "sim_real_guard", "reduce_only": True},
    )
    ok, reason = require_protective_stop(reduce)
    if ok is not True:
        _fail("reduce-only required a stop")
    buy_stop = default_stop_price(side="BUY", reference=5000.0)
    if buy_stop >= 5000.0:
        _fail("BUY stop not below entry")
    sell_stop = default_stop_price(side="SELL", reference=5000.0)
    if sell_stop <= 5000.0:
        _fail("SELL stop not above entry")
    try:
        default_stop_price(side="HOLD", reference=5000.0)
        _fail("HOLD side produced a stop")
    except ValueError:
        pass
    try:
        default_stop_price(side="BUY", reference=0.0)
        _fail("zero reference produced a stop")
    except ValueError:
        pass
    tiny = default_stop_price(side="BUY", reference=0.5)
    if tiny <= 0.0 or tiny >= 0.5:
        _fail("tiny reference stop lost")
    entry = Order(
        symbol="MES",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        stop_loss=4950.0,
        metadata={"mode_context": "sim_real_guard", "stop_price": 4950.0},
    )
    companion = companion_stop_order(entry, client_order_id="c-stop")
    if companion.order_type != "STOP" or companion.side != "SELL":
        _fail("companion stop not STOP SELL")
    if companion.metadata.get("protected") is not True or companion.metadata.get("reduce_only") is not True:
        _fail("companion stop not protected reduce_only")
    tagged = Order(
        symbol="MES",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        stop_loss=4950.0,
        metadata={"mode_context": "sim_real_guard", "stop_price": 4950.0, "strategy_id": "hyp-a"},
    )
    tagged_stop = companion_stop_order(tagged, client_order_id="c-tag")
    if tagged_stop.metadata.get("strategy_id") != "hyp-a":
        _fail("companion dropped strategy_id")
    tiny_entry = Order(
        symbol="MES",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        stop_loss=0.5,
        metadata={"mode_context": "sim_real_guard", "stop_price": 0.5},
    )
    tiny_stop = companion_stop_order(tiny_entry, client_order_id="c-tiny")
    if float(tiny_stop.stop_loss) != 0.5:
        _fail("tiny companion stop refused")
    ok, reason = require_protective_stop(tiny_entry)
    if ok is not True:
        _fail("tiny stop_price refused")
    try:
        companion_stop_order(naked, client_order_id="c-none")
        _fail("companion built without stop")
    except ValueError:
        pass
    sell_entry = Order(
        symbol="MES",
        side="SELL",
        quantity=2,
        order_type="MARKET",
        stop_loss=5050.0,
        metadata={"mode_context": "real", "stop_price": 5050.0},
    )
    cover = companion_stop_order(sell_entry, client_order_id="c-cover")
    if cover.side != "BUY" or int(cover.quantity) != 2:
        _fail("SELL companion not BUY same qty")
    atm_tagged = Order(
        symbol="MES",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        stop_loss=4950.0,
        metadata={
            "mode_context": "sim_real_guard",
            "stop_price": 4950.0,
            "atm_strategy_template": "LuminaProtective",
        },
    )
    atm_comp = companion_stop_order(atm_tagged, client_order_id="c-atm")
    if atm_comp.metadata.get("atm_strategy_template"):
        _fail("companion kept ATM template")
    if atm_comp.metadata.get("protective_attach") != "companion":
        _fail("companion missing attach tag")
    emerg_reason = Order(
        symbol="MES",
        side="SELL",
        quantity=1,
        order_type="MARKET",
        metadata={"mode_context": "sim_real_guard", "reason": "unconfirmed_protective_stop"},
    )
    ok, reason = require_protective_stop(emerg_reason)
    if ok is not True:
        _fail("unconfirmed_protective_stop flatten required a stop")


def _kill_protective_attach() -> None:
    if DEFAULT_COMPANION_CONFIRM_TIMEOUT_MS != 5000:
        _fail("companion timeout drifted")
    if DEFAULT_ATM_CONFIRM_TIMEOUT_MS != 5000:
        _fail("ATM timeout drifted")
    if GENERIC_ATM_TEMPLATE_NAME != "LuminaProtective":
        _fail("generic ATM template name drifted")
    if GENERIC_ATM_INSTRUMENTS != ("ES", "NQ", "MES", "MNQ"):
        _fail("generic ATM markets drifted")
    if ATM_STOP_ATR_MULTIPLE != 1.5:
        _fail("ATM ATR stop multiple drifted")
    if PATH_ATM != "atm" or PATH_COMPANION != "companion" or PATH_REFUSED != "refused":
        _fail("attach path labels drifted")
    if ATTACH_ATM != "atm":
        _fail("ATM attach tag drifted")
    named = from_mapping(None, account="LiveAcct")
    if named.account != "LiveAcct":
        _fail("from_mapping replaced a real account with Sim101")
    cfg_empty = from_mapping(None, account="Sim101")
    if resolve_atm_template(cfg_empty) != "":
        _fail("empty mapping invented a template")
    plan_c = plan_protective_attach(cfg_empty)
    if plan_c.path != PATH_COMPANION or "second order" not in plan_c.residual_risk:
        _fail("empty template did not take C with residual")
    conn_off = from_mapping(
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
    if resolve_atm_template(conn_off) != "":
        _fail("empty connection map lost to account template")
    if plan_protective_attach(conn_off).path != PATH_COMPANION:
        _fail("connection ATM-off did not fall to C")
    acct = from_mapping(
        {"atm": {"templates_by_account": {"Sim101": "LuminaProtective"}}},
        account="Sim101",
    )
    plan_a = plan_protective_attach(acct)
    if plan_a.path != PATH_ATM or plan_a.atm_template != "LuminaProtective":
        _fail("account template did not select A")
    refused = from_mapping({"atm": {"fallback_companion": False}}, account="Sim101")
    plan_r = plan_protective_attach(refused)
    if plan_r.path != PATH_REFUSED or plan_r.reason != PROTECTIVE_REFUSED:
        _fail("no ATM and no C opened an entry")
    zero = from_mapping({"atm": {"companion_confirm_timeout_ms": 0}})
    if zero.companion_confirm_timeout_ms != 5000:
        _fail("timeout 0 not fail-closed to default")
    bad = from_mapping({"atm": {"companion_confirm_timeout_ms": "nope"}})
    if bad.companion_confirm_timeout_ms != 5000:
        _fail("invalid timeout not defaulted")
    if plan_protective_attach(acct, reduce_only=True).path != PATH_REFUSED:
        _fail("reduce_only took ATM")
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
    if plan_protective_attach(engine_cfg).path != PATH_ATM:
        _fail("from_engine account template ignored")
    live_engine = from_engine(
        SimpleNamespace(
            nt_connected_account="LiveAcct",
            nt_connection="playback",
            config=SimpleNamespace(
                ninjatrader={
                    "atm": {
                        "templates_by_account": {"LiveAcct": "AcctTpl"},
                        "templates_by_connection": {"playback": ""},
                        "fallback_companion": True,
                    }
                }
            ),
        )
    )
    if live_engine.account != "LiveAcct":
        _fail("from_engine dropped LiveAcct")
    if plan_protective_attach(live_engine).path != PATH_COMPANION:
        _fail("from_engine connection ATM-off ignored")
    object_nt = from_engine(
        SimpleNamespace(
            nt_connected_account="Sim101",
            config=SimpleNamespace(
                ninjatrader=SimpleNamespace(
                    templates_by_account={"Sim101": "LuminaProtective"},
                    templates_by_connection={},
                    atm_strategy_template="",
                    atm_fallback_companion=True,
                    companion_confirm_timeout_ms=5000,
                )
            ),
        )
    )
    if plan_protective_attach(object_nt).path != PATH_ATM:
        _fail("from_engine object nt_cfg ignored")
    object_conn = from_engine(
        SimpleNamespace(
            nt_connected_account="Sim101",
            nt_connection="playback",
            config=SimpleNamespace(
                ninjatrader=SimpleNamespace(
                    templates_by_account={"Sim101": "AcctTpl"},
                    templates_by_connection={"playback": "ConnTpl"},
                    atm_strategy_template="DefaultTpl",
                    atm_fallback_companion=True,
                    companion_confirm_timeout_ms=5000,
                )
            ),
        )
    )
    object_plan = plan_protective_attach(object_conn)
    if object_plan.path != PATH_ATM or object_plan.atm_template != "ConnTpl":
        _fail("from_engine object connection template ignored")
    object_default = from_engine(
        SimpleNamespace(
            nt_connected_account="Sim101",
            config=SimpleNamespace(
                ninjatrader=SimpleNamespace(
                    templates_by_account={},
                    templates_by_connection={},
                    atm_strategy_template="DefaultTpl",
                    atm_fallback_companion=True,
                    companion_confirm_timeout_ms=5000,
                )
            ),
        )
    )
    default_plan = plan_protective_attach(object_default)
    if default_plan.path != PATH_ATM or default_plan.atm_template != "DefaultTpl":
        _fail("from_engine object default template ignored")
    nested_nt = from_engine(
        SimpleNamespace(
            nt_connected_account="Sim101",
            config=SimpleNamespace(ninjatrader=SimpleNamespace(atm={"templates_by_account": {"Sim101": "LuminaProtective"}})),
        )
    )
    if plan_protective_attach(nested_nt).path != PATH_ATM:
        _fail("from_engine nested atm mapping ignored")
    if plan_protective_attach(from_engine(None)).path != PATH_COMPANION:
        _fail("from_engine None did not fall to C")
    ok_res = OrderResult(accepted=True, order_id="a", status="accepted", raw={"protective_attach": "atm"})
    if atm_confirmed(ok_res) is not True:
        _fail("ATM tag not confirmed")
    if atm_confirmed(OrderResult(accepted=True, order_id="a", status="accepted", raw={})) is True:
        _fail("empty raw counted as ATM")
    if atm_confirmed(None) is True or atm_confirmed(OrderResult(accepted=False, order_id="", status="rejected")) is True:
        _fail("rejected ATM counted confirmed")
    started = T0
    if atm_confirmed_on_time(ok_res, started=started, now=started + timedelta(milliseconds=5001), timeout_ms=5000) is True:
        _fail("late ATM tag counted on-time")
    hidden_fill = OrderResult(
        accepted=False,
        order_id="h",
        status="rejected",
        filled_qty=1,
        message=FILL_BEFORE_ATM,
        raw={"rejection_reason": FILL_BEFORE_ATM},
    )
    if live_fill_without_confirmed_atm(hidden_fill) is not True:
        _fail("fill-before-ATM hidden reject not live")
    if live_fill_without_confirmed_atm(ok_res) is True:
        _fail("confirmed ATM counted as live unconfirmed fill")
    ok_stop = OrderResult(accepted=True, order_id="s", status="accepted")
    if companion_confirmed(ok_stop, started=started, now=started + timedelta(milliseconds=5000), timeout_ms=5000) is not True:
        _fail("timeout boundary 5000ms rejected")
    if companion_confirmed(ok_stop, started=started, now=started + timedelta(milliseconds=5001), timeout_ms=5000) is True:
        _fail("timeout 5001ms confirmed")
    if companion_confirmed(OrderResult(accepted=False, order_id="", status="rejected"), started=started, now=started, timeout_ms=5000) is True:
        _fail("rejected companion confirmed")
    flat = emergency_flatten_order(instrument="MES", entry_side="BUY", quantity=2, strategy_id="hyp-a")
    if flat.side != "SELL" or flat.metadata.get("reason") != "unconfirmed_protective_stop":
        _fail("emergency flatten not opposite reduce_only")
    if emergency_flatten_order(instrument="MNQ", entry_side="SELL", quantity=1, strategy_id="h").side != "BUY":
        _fail("SELL flatten not BUY")
    if reduce_qty("unconfirmed_protective_stop", 2) != 2:
        _fail("unconfirmed stop did not flatten full qty")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        def _rt(
            submitter: RecordingSubmitter,
            protective: ProtectiveAttachConfig,
            clock=None,
            jsonl: str = "atm.jsonl",
        ) -> SimRuntime:
            ctx = passing_context()
            bind_sim_gate(ctx)
            return SimRuntime(
                bus=EventBus(),
                authority=ProvenanceAuthority(),
                jsonl_path=root / jsonl,
                market=healthy_closed_bar(close=5000.0),
                fill_index=FillIndex(),
                gate_ctx=ctx,
                engine=fake_engine(),
                submitter=submitter,
                pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
                protective=protective,
                clock=clock,
            )

        atm_cfg = ProtectiveAttachConfig(
            templates_by_account=(("Sim101", "LuminaProtective"),),
            account="Sim101",
        )
        atm_sub = RecordingSubmitter()
        atm_rt = _rt(atm_sub, atm_cfg)
        atm_res = atm_rt.on_candidate(sealed_candidate(atm_rt._authority, instrument="MES"))
        if atm_res is None or atm_confirmed(atm_res) is not True or len(atm_sub.orders) != 1:
            _fail("ATM path submitted companion or missed ATM tag")
        if atm_sub.orders[0].metadata.get("atm_strategy_template") != "LuminaProtective":
            _fail("ATM template missing on entry")
        if isinstance(atm_res.raw, dict) and atm_res.raw.get("nt_child") != "atm-stop":
            _fail("ATM raw child tag dropped")
        if atm_rt.broker_submit_count() != 1:
            _fail("ATM path submit count drifted")
        if len(atm_rt._fill_index) != 1:
            _fail("ATM fill not indexed")
        bind_sim_gate(None)

        class _RejectAtm(RecordingSubmitter):
            def submit_order(self, order: Order) -> OrderResult:
                meta = order.metadata if isinstance(order.metadata, dict) else {}
                if str(meta.get("atm_strategy_template") or "").strip():
                    self.orders.append(order)
                    return OrderResult(accepted=False, order_id="", status="rejected", message="atm_attach_failed")
                return super().submit_order(order)

        reject = _RejectAtm()
        reject_rt = _rt(
            reject,
            ProtectiveAttachConfig(
                templates_by_account=(("Sim101", "LuminaProtective"),),
                account="Sim101",
                fallback_companion=True,
            ),
            jsonl="atm-reject.jsonl",
        )
        reject_res = reject_rt.on_candidate(sealed_candidate(reject_rt._authority, instrument="MES"))
        if reject_res is not None and reject_res.accepted is True:
            _fail("ATM reject retried a second entry")
        if len(reject_rt._fill_index) != 0:
            _fail("ATM reject indexed a fill")
        reject_text = (root / "atm-reject.jsonl").read_text(encoding="utf-8")
        if "atm_attach_failed" not in reject_text:
            _fail("ATM reject dropped the host message")
        if any(str(o.order_type).upper() == "STOP" for o in reject.orders):
            _fail("ATM reject placed a companion after no fill")
        bind_sim_gate(None)

        class _AcceptAtmUnconfirmed(RecordingSubmitter):
            def submit_order(self, order: Order) -> OrderResult:
                meta = order.metadata if isinstance(order.metadata, dict) else {}
                if str(meta.get("atm_strategy_template") or "").strip() and str(order.order_type).upper() != "STOP":
                    self.orders.append(order)
                    return OrderResult(accepted=True, order_id="sim-atm", status="accepted", message="ok", raw={})
                return super().submit_order(order)

        live_c = _AcceptAtmUnconfirmed()
        live_rt = _rt(live_c, ProtectiveAttachConfig(
            templates_by_account=(("Sim101", "LuminaProtective"),),
            account="Sim101",
            fallback_companion=True,
        ))
        live_res = live_rt.on_candidate(sealed_candidate(live_rt._authority, instrument="MES"))
        if live_res is None or live_res.accepted is not True:
            _fail("live unconfirmed ATM did not attach C")
        if not any(str(o.order_type).upper() == "STOP" for o in live_c.orders):
            _fail("live unconfirmed ATM skipped companion STOP")
        bind_sim_gate(None)

        live_flat = _AcceptAtmUnconfirmed()
        live_flat_rt = _rt(
            live_flat,
            ProtectiveAttachConfig(
                templates_by_account=(("Sim101", "LuminaProtective"),),
                account="Sim101",
                fallback_companion=False,
            ),
            jsonl="live-flat.jsonl",
        )
        if live_flat_rt.on_candidate(sealed_candidate(live_flat_rt._authority, instrument="MES")) is not None:
            _fail("live unconfirmed ATM without C kept the fill")
        reasons = [str(o.metadata.get("reason") or "") for o in live_flat.orders]
        if "unconfirmed_protective_stop" not in reasons:
            _fail("live unconfirmed ATM without C skipped flatten")
        live_flat_text = (root / "live-flat.jsonl").read_text(encoding="utf-8")
        if ATM_UNCONFIRMED not in live_flat_text:
            _fail("live unconfirmed ATM without C used the C refuse code")
        if COMPANION_UNCONFIRMED in live_flat_text:
            _fail("live unconfirmed ATM without C logged companion unconfirmed")
        bind_sim_gate(None)

        class _JumpClock:
            def __init__(self) -> None:
                self.now = T0

            def __call__(self) -> datetime:
                return self.now

            def jump_ms(self, ms: int) -> None:
                self.now = self.now + timedelta(milliseconds=int(ms))

        class _SlowStop(RecordingSubmitter):
            def __init__(self, clock: _JumpClock) -> None:
                super().__init__()
                self.clock = clock

            def submit_order(self, order: Order) -> OrderResult:
                if str(order.order_type).upper() == "STOP":
                    self.clock.jump_ms(6000)
                return super().submit_order(order)

        clock = _JumpClock()
        slow = _SlowStop(clock)
        slow_rt = _rt(
            slow,
            ProtectiveAttachConfig(fallback_companion=True, companion_confirm_timeout_ms=5000, account="Sim101"),
            clock=clock,
            jsonl="slow.jsonl",
        )
        if slow_rt.on_candidate(sealed_candidate(slow_rt._authority, instrument="MES")) is not None:
            _fail("slow companion kept the entry")
        if len(slow_rt._fill_index) != 0:
            _fail("unconfirmed companion indexed a fill")
        slow_reasons = [str(o.metadata.get("reason") or "") for o in slow.orders]
        if "unconfirmed_protective_stop" not in slow_reasons:
            _fail("unconfirmed companion skipped flatten")
        slow_text = (root / "slow.jsonl").read_text(encoding="utf-8")
        if COMPANION_UNCONFIRMED not in slow_text:
            _fail("slow companion used the ATM refuse code")
        bind_sim_gate(None)

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
                        raw={},
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

        race = _FillBeforeAtm()
        race_rt = _rt(
            race,
            ProtectiveAttachConfig(
                templates_by_account=(("Sim101", GENERIC_ATM_TEMPLATE_NAME),),
                account="Sim101",
                fallback_companion=False,
                atm_confirm_timeout_ms=5000,
            ),
            jsonl="fill-before-atm.jsonl",
        )
        if race_rt.on_candidate(sealed_candidate(race_rt._authority, instrument="MES")) is not None:
            _fail("fill-before-ATM without C kept the fill")
        race_reasons = [str(o.metadata.get("reason") or "") for o in race.orders]
        if "unconfirmed_protective_stop" not in race_reasons:
            _fail("fill-before-ATM without C skipped flatten")
        bind_sim_gate(None)

        atm_clock = _JumpClock()
        slow_atm = _SlowAtm(atm_clock)
        slow_atm_rt = _rt(
            slow_atm,
            ProtectiveAttachConfig(
                templates_by_account=(("Sim101", GENERIC_ATM_TEMPLATE_NAME),),
                account="Sim101",
                fallback_companion=False,
                atm_confirm_timeout_ms=5000,
            ),
            clock=atm_clock,
            jsonl="slow-atm.jsonl",
        )
        if slow_atm_rt.on_candidate(sealed_candidate(slow_atm_rt._authority, instrument="MNQ")) is not None:
            _fail("slow ATM confirm kept the fill")
        slow_atm_reasons = [str(o.metadata.get("reason") or "") for o in slow_atm.orders]
        if "unconfirmed_protective_stop" not in slow_atm_reasons:
            _fail("slow ATM confirm skipped flatten")
        bind_sim_gate(None)

        none_sub = RecordingSubmitter()
        none_rt = _rt(none_sub, ProtectiveAttachConfig(account="Sim101", fallback_companion=False))
        if none_rt.on_candidate(sealed_candidate(none_rt._authority, instrument="MES")) is not None:
            _fail("no ATM no C placed")
        if none_sub.orders:
            _fail("no ATM no C submitted before refuse")
        bind_sim_gate(None)

        c_sub = RecordingSubmitter()
        c_rt = _rt(c_sub, ProtectiveAttachConfig(account="Sim101", fallback_companion=True))
        c_res = c_rt.on_candidate(sealed_candidate(c_rt._authority, instrument="MES"))
        if c_res is None or len(c_sub.orders) != 2 or str(c_sub.orders[1].order_type).upper() != "STOP":
            _fail("C fallback did not submit MARKET+STOP")
        if c_rt.broker_submit_count() != 2:
            _fail("C fallback submit count drifted")
        bind_sim_gate(None)

        alarm_sub = RecordingSubmitter()
        alarm_pos = LivePositionManager(app=SimpleNamespace())
        alarm_pos.set_strategy_qty("hyp-a", 2)
        alarm_sink = RecordingAlertSink()
        alarm = AlarmExecutor(
            bus=EventBus(),
            positions=alarm_pos,
            submitter=alarm_sub,
            jsonl_path=root / "alarm-unconfirmed.jsonl",
            clock=lambda: T0,
            alert_sink=alarm_sink,
        )
        alarm.flatten_unconfirmed_protective_stop(instrument="MES", strategy_id="hyp-a", qty=2)
        if not alarm_sub.orders or alarm_sub.orders[-1].quantity != 2:
            _fail("unconfirmed flatten skipped qty 2")
        if alarm_pos.strategy_qty("hyp-a") != 0:
            _fail("unconfirmed flatten left hyp-a qty")
        if not any(str(row.get("code") or "") == "unconfirmed_protective_stop_flatten" for row in alarm_sink.records):
            _fail("unconfirmed flatten skipped alert sink")
        zero_sub = RecordingSubmitter()
        zero = AlarmExecutor(
            bus=EventBus(),
            positions=LivePositionManager(app=SimpleNamespace()),
            submitter=zero_sub,
            jsonl_path=root / "alarm-zero.jsonl",
            clock=lambda: T0,
        )
        zero.flatten_unconfirmed_protective_stop(instrument="MES", strategy_id="hyp-z", qty=0)
        if zero_sub.orders:
            _fail("qty 0 unconfirmed flatten submitted")
        seeded_sub = RecordingSubmitter()
        seeded_pos = LivePositionManager(app=SimpleNamespace())
        seeded_pos.set_strategy_qty("hyp-z", 2)
        seeded = AlarmExecutor(
            bus=EventBus(),
            positions=seeded_pos,
            submitter=seeded_sub,
            jsonl_path=root / "alarm-seeded.jsonl",
            clock=lambda: T0,
        )
        seeded.flatten_unconfirmed_protective_stop(instrument="MES", strategy_id="hyp-z", qty=0)
        if not seeded_sub.orders or seeded_sub.orders[-1].quantity != 2:
            _fail("qty 0 did not flatten seeded strategy qty")
        bind_sim_gate(None)
        blocked = RecordingSubmitter()
        blocked_rt = _rt(blocked, ProtectiveAttachConfig(account="Sim101"), jsonl="ungated.jsonl")
        bind_sim_gate(None)
        blocked_order = Order(
            symbol="MES",
            side="BUY",
            quantity=1,
            order_type="MARKET",
            metadata={"mode_context": "sim_real_guard", "source_agent": "research_bridge"},
        )
        blocked_res = blocked_rt._submit_entry(blocked_order)
        if blocked_res is not None:
            _fail("unbound sim_gate still submitted an entry")
        if blocked.orders:
            _fail("unbound sim_gate reached the submitter")


def _kill_telegram() -> None:
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ.pop("TELEGRAM_CHAT_ID", None)
    if telegram_credentials_present() is True:
        _fail("empty telegram env counted as credentials")
    os.environ["TELEGRAM_BOT_TOKEN"] = "tok"
    os.environ.pop("TELEGRAM_CHAT_ID", None)
    if telegram_credentials_present() is True:
        _fail("token-only counted as credentials")
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ["TELEGRAM_CHAT_ID"] = "123"
    if telegram_credentials_present() is True:
        _fail("chat-only counted as credentials")
    os.environ["TELEGRAM_BOT_TOKEN"] = "tok"
    os.environ["TELEGRAM_CHAT_ID"] = "123"
    if telegram_credentials_present() is not True:
        _fail("real credentials ignored")
    os.environ["TELEGRAM_BOT_TOKEN"] = "${TOKEN}"
    if telegram_credentials_present() is True:
        _fail("placeholder token counted")
    os.environ["TELEGRAM_BOT_TOKEN"] = "tok"
    os.environ["TELEGRAM_CHAT_ID"] = "${CHAT}"
    if telegram_credentials_present() is True:
        _fail("placeholder chat counted")
    source = (ROOT / "lumina_core/research_bridge/alerts.py").read_text(encoding="utf-8")
    if "urllib" in source or "requests" in source or "http.client" in source:
        _fail("telegram sink grew a network client")
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ.pop("TELEGRAM_CHAT_ID", None)
    with tempfile.TemporaryDirectory() as tmp:
        journal = Path(tmp) / "tg.jsonl"
        sink = TelegramAlertSink(kind="ops", path=journal)
        sink.alert(code="research_sim_gated", message="gated", details={"hypothesis_id": "hyp-a"})
        text = journal.read_text(encoding="utf-8")
        if "research_sim_gated" not in text or "no_credentials" not in text:
            _fail("telegram journal missing drop_reason")
        os.environ["TELEGRAM_BOT_TOKEN"] = "tok"
        os.environ["TELEGRAM_CHAT_ID"] = "123"
        creds_journal = Path(tmp) / "tg-creds.jsonl"
        TelegramAlertSink(kind="evolution", path=creds_journal, source="alarm_executor").alert(
            code="alarm_executor.gated",
            message="gated",
            details={"strategy_id": "hyp-b"},
        )
        creds_text = creds_journal.read_text(encoding="utf-8")
        if "no_credentials" in creds_text:
            _fail("credentials still dropped")
        if "hyp-b" not in creds_text:
            _fail("strategy_id not journaled")
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("TELEGRAM_CHAT_ID", None)


def _kill_caps() -> None:
    if resolve_mode_capabilities("sim").risk_enforced is not True:
        _fail("desk sim caps not enforced")
    limits = RiskLimits(sim_mode=True, daily_loss_cap=-150.0, enforce_session_guard=False)
    controller = HardRiskController(limits, enforce_rules=True)
    controller.state.daily_pnl = -2000.0
    allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
    if allowed is True:
        _fail(f"sim_mode bypassed daily cap {reason}")
    advisory = HardRiskController(limits, enforce_rules=False)
    advisory.state.daily_pnl = -2000.0
    allowed, reason = advisory.check_can_trade("MES", "trending_up", 100.0)
    if allowed is not True:
        _fail("advisory path closed")
    if "all caps bypassed" in reason.lower():
        _fail("advisory path still advertises SIM caps-bypass")


def _kill_stale_sim() -> None:
    if "sim" not in MODES_REQUIRING_EQUITY_SNAPSHOT:
        _fail("sim missing from equity snapshot modes")
    ok, reason = evaluate(passing_context(stale=True, reduce_only=False))
    if ok is True:
        _fail("stale equity allowed a new SIM order")
    ok, reason = evaluate(passing_context(stale=True, reduce_only=True))
    if ok is not True:
        _fail("stale reduce-only blocked")


def _kill_prolonged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        positions = LivePositionManager(app=SimpleNamespace())
        positions.set_strategy_qty("hyp-a", 2)
        submitter = RecordingSubmitter()
        exe = AlarmExecutor(
            bus=EventBus(),
            positions=positions,
            submitter=submitter,
            jsonl_path=Path(tmp) / "alarm.jsonl",
            clock=lambda: T0,
        )
        if exe.prolonged_flattens != 0 or exe.reconciles != 0:
            _fail("prolonged counters defaulted away from zero")
        exe.flatten_on_prolonged_disconnect(instrument="MES")
        if exe.reconciles != 1:
            _fail("prolonged disconnect skipped reconcile")
        if exe.prolonged_flattens < 1:
            _fail("prolonged disconnect skipped flatten")
        if positions.strategy_qty("hyp-a") != 0:
            _fail("prolonged disconnect left qty")
        if not submitter.orders or submitter.orders[-1].quantity != 2:
            _fail("prolonged disconnect did not flatten 2")
        if submitter.orders[-1].symbol != "MES":
            _fail("MES flatten coerced off MES")
        positions_mnq = LivePositionManager(app=SimpleNamespace())
        positions_mnq.set_strategy_qty("hyp-mnq", 2)
        mnq = RecordingSubmitter()
        exe_mnq = AlarmExecutor(
            bus=EventBus(),
            positions=positions_mnq,
            submitter=mnq,
            jsonl_path=Path(tmp) / "alarm-mnq.jsonl",
            clock=lambda: T0,
        )
        exe_mnq.flatten_on_prolonged_disconnect(instrument="MNQ")
        if not mnq.orders or mnq.orders[-1].symbol != "MNQ":
            _fail("MNQ flatten coerced off MNQ")
        positions_one = LivePositionManager(app=SimpleNamespace())
        positions_one.set_strategy_qty("hyp-one", 1)
        one = RecordingSubmitter()
        exe_one = AlarmExecutor(
            bus=EventBus(),
            positions=positions_one,
            submitter=one,
            jsonl_path=Path(tmp) / "alarm-one.jsonl",
            clock=lambda: T0,
        )
        exe_one.flatten_on_prolonged_disconnect(instrument="MES")
        if not one.orders or one.orders[-1].quantity != 1:
            _fail("qty 1 skipped flatten")
        positions_live = LivePositionManager(app=SimpleNamespace())
        positions_live._pos.live_position_qty = 1
        live = RecordingSubmitter()
        exe_live = AlarmExecutor(
            bus=EventBus(),
            positions=positions_live,
            submitter=live,
            jsonl_path=Path(tmp) / "alarm-live.jsonl",
            clock=lambda: T0,
        )
        exe_live.flatten_on_prolonged_disconnect(instrument="MES")
        if not live.orders or live.orders[-1].quantity != 1:
            _fail("broker SoT qty 1 skipped flatten")
        positions_flat = LivePositionManager(app=SimpleNamespace())
        flat = AlarmExecutor(
            bus=EventBus(),
            positions=positions_flat,
            submitter=RecordingSubmitter(),
            jsonl_path=Path(tmp) / "alarm-flat.jsonl",
            clock=lambda: T0,
        )
        if flat.flatten_on_prolonged_disconnect() is not None:
            _fail("flat flatten returned a value")


if __name__ == "__main__":
    run()
