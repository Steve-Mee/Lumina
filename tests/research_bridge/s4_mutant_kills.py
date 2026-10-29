"""Fail-closed kill battery for S4 SIM-entry hardening. No pytest."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.broker.broker_bridge.schemas import Order
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.engine.mode_capabilities import resolve_mode_capabilities
from lumina_core.order_gatekeeper.engine_helpers import MODES_REQUIRING_EQUITY_SNAPSHOT
from lumina_core.research_bridge.alerts import TelegramAlertSink, telegram_credentials_present
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
from lumina_core.research_bridge.protective_stop import (
    UNPROTECTED_ENTRY,
    companion_stop_order,
    default_stop_price,
    require_protective_stop,
)
from lumina_core.research_bridge.sim_gate import MIN_SURVIVORS, evaluate
from lumina_core.risk.alarm_executor import AlarmExecutor
from lumina_core.risk.risk_controller import HardRiskController
from lumina_core.risk.risk_limits import RiskLimits
from lumina_research.cycles.sim_plan import SIM_MIN_SURVIVORS, SIM_TARGET_SURVIVORS
from lumina_research.validation.nt_tape import closed_bars_from_rows, fixture_closed_mes_bars
from tests.research_bridge.s3_helpers import RecordingSubmitter, passing_context, passing_meter, survivor
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
