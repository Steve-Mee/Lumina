"""Fail-closed kill battery for S2 fill SSOT. No pytest."""

from __future__ import annotations

import io
import json
import logging
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research_execution import (
    FILL_TRANSLATOR_AGENT_ID,
    RESEARCH_EXECUTION_FILL_TOPIC,
    RESEARCH_EXECUTION_ORDER_TOPIC,
    RESEARCH_EXECUTION_SIGNAL_TOPIC,
)
from lumina_core.engine.trade_reconciler.schemas import FillEvent
from lumina_core.research_bridge import binding_policy as binding_mod
from lumina_core.research_bridge.binding_policy import (
    D7_CRITICAL_SLA_SECONDS,
    D7_DEFAULT_SLA_SECONDS,
    DISABLE_FLATTEN_FRACTION,
    INDEPENDENCE_CORR_MAX,
    SLA_ESCALATE_AFTER_SECONDS,
    SLA_RETRY_LIMIT,
    SUSPEND_REDUCE_FRACTION,
    BindingPolicyRefused,
    independent,
    reduce_fraction_for_stage,
    reduce_qty,
    sla_decision,
)
from lumina_core.research_bridge import fill_stamp as stamp_mod
from lumina_core.research_bridge.calibrator_rows import (
    BROKER_SOURCE,
    HYPOTHETICAL_SOURCE,
    CalibratorRowRefused,
    is_broker_source,
    is_hypothetical_source,
    live_calibrator_row,
    normalize_fill_source,
    root_of_symbol,
)
from lumina_core.research_bridge.fill_index import FillIndex, FillIndexRefused
from lumina_core.research_bridge.fill_stamp import (
    FillStampRefused,
    execution_commission,
    stamp_commission,
    stamp_slippage,
)
from lumina_core.research_bridge import fill_translator as translator_mod
from lumina_core.research_bridge.fill_translator import FillTranslator, TranslateRefused, observe_metric
from lumina_core.risk.cost_model_calibrator import load_reconciled_rows, run_daily_calibration
from lumina_research.validation.contracts import spec_for as research_spec_for
from lumina_research.validation.cost_calibrate import (
    CostCalibrateRefused,
    assert_does_not_undercut_card,
    calibrate_fills,
    calibrate_root,
    card_commission_usd,
    execution_wins,
    research_commission_usd,
    research_four_leg_usd,
    tighten_only,
    write_research_calibration,
)
from lumina_research.validation.cost_model import CostModel, MarketSnapshot
from tests.research_bridge.helpers import RecordingObserveSink

UTC = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def _fail(message: str) -> None:
    raise AssertionError(message)


def _fill(
    *,
    symbol: str = "MES",
    side: str = "BUY",
    quantity: int = 1,
    price: float = 5000.25,
    commission: float = 0.0,
    source: str = "broker",
    strategy_id: str = "",
    expected_horizon: int = 0,
    fill_id: str = "kill-1",
    client_order_id: str = "cid-1",
) -> FillEvent:
    return FillEvent(
        fill_id=fill_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        commission=commission,
        event_ts=UTC,
        raw_payload={"client_order_id": client_order_id, "source": source},
        source=source,
        strategy_id=strategy_id,
        expected_horizon=expected_horizon,
    )


def _stamp_battery() -> None:
    if abs(card_commission_usd("MES") - 0.94) > 1e-12:
        _fail("card default qty")
    usd, ticks, tick_usd = stamp_commission("MES", 1)
    if abs(usd - 0.94) > 1e-12 or usd <= 0.0:
        _fail(f"MES commission {usd}")
    if abs(tick_usd - 1.25) > 1e-12:
        _fail(f"MES tick usd {tick_usd}")
    if abs(ticks - (0.94 / 1.25)) > 1e-12:
        _fail(f"MES ticks {ticks}")
    es_usd, _es_ticks, es_tick = stamp_commission("ES", 1)
    if abs(es_usd - 2.87) > 1e-12 or es_usd == usd:
        _fail(f"ES commission {es_usd}")
    if abs(es_tick - 12.50) > 1e-12:
        _fail(f"ES tick usd {es_tick}")
    mnq_usd, _, _ = stamp_commission("MNQ", 1)
    nq_usd, _, _ = stamp_commission("NQ", 1)
    if abs(mnq_usd - 0.94) > 1e-12 or abs(nq_usd - 2.87) > 1e-12 or mnq_usd == nq_usd:
        _fail(f"MNQ/NQ {mnq_usd} {nq_usd}")
    two, _, _ = stamp_commission("MES", 2)
    if abs(two - 1.88) > 1e-12:
        _fail(f"MES qty2 {two}")
    try:
        stamp_commission("MES", 0)
        _fail("qty 0 must refuse")
    except FillStampRefused as exc:
        if "qty_invalid" not in str(exc):
            _fail(f"qty 0 wrong refuse {exc}")
    try:
        card_commission_usd("MES", 0)
        _fail("card qty 0")
    except CostCalibrateRefused as exc:
        if "qty_invalid" not in str(exc):
            _fail(f"card qty 0 {exc}")
    try:
        stamp_commission("NOTAROOT", 1)
        _fail("unknown root must refuse")
    except FillStampRefused:
        pass
    card, _t, disc = execution_commission("MES", 1, 0.0)
    if abs(card - 0.94) > 1e-12 or disc is not True:
        _fail(f"execution wins zero claim {card} {disc}")
    card2, _t2, disc2 = execution_commission("MES", 1, 0.94)
    if disc2 is not False:
        _fail("matching claim is not a discrepancy")
    card3, _t3, disc3 = execution_commission("MES", 1, None)
    if disc3 is not False or abs(card3 - 0.94) > 1e-12:
        _fail("None claim must take the card")
    try:
        execution_commission("MES", 1, float("nan"))
        _fail("nan claim must refuse")
    except FillStampRefused:
        pass
    if stamp_slippage(symbol="MES", side="BUY", fill_price=5000.0, reference_price=None, qty=1) is not None:
        _fail("omitted reference must not invent slippage")
    buy = stamp_slippage(symbol="MES", side="BUY", fill_price=5000.25, reference_price=5000.0, qty=1)
    if buy is None or abs(buy[0] - 1.0) > 1e-12 or abs(buy[1] - 1.25) > 1e-12:
        _fail(f"BUY adverse {buy}")
    sell = stamp_slippage(symbol="MES", side="SELL", fill_price=4999.75, reference_price=5000.0, qty=1)
    if sell is None or abs(sell[0] - 1.0) > 1e-12 or abs(sell[1] - 1.25) > 1e-12:
        _fail(f"SELL adverse {sell}")
    fav = stamp_slippage(symbol="MES", side="BUY", fill_price=4999.75, reference_price=5000.0, qty=1)
    if fav is None or fav[0] >= 0.0:
        _fail(f"BUY favorable must be negative {fav}")
    try:
        stamp_slippage(symbol="MES", side="HOLD", fill_price=5000.0, reference_price=5000.0, qty=1)
        _fail("HOLD side must refuse")
    except FillStampRefused:
        pass
    try:
        stamp_slippage(symbol="MES", side="BUY", fill_price=5000.0, reference_price=0.0, qty=1)
        _fail("zero reference must refuse")
    except FillStampRefused:
        pass
    try:
        stamp_slippage(symbol="NOTAROOT", side="BUY", fill_price=5000.0, reference_price=5000.0, qty=1)
        _fail("unknown root slippage")
    except FillStampRefused:
        pass


def _index_battery() -> None:
    index = FillIndex()
    try:
        index.remember("", "hyp", 8)
        _fail("empty client_order_id")
    except FillIndexRefused:
        pass
    try:
        index.remember("cid", "", 8)
        _fail("empty strategy_id")
    except FillIndexRefused:
        pass
    try:
        index.remember("cid", "hyp", 0)
        _fail("horizon 0")
    except FillIndexRefused:
        pass
    try:
        index.remember("cid", "hyp", True)  # type: ignore[arg-type]
        _fail("bool horizon")
    except FillIndexRefused:
        pass
    entry = index.remember("cid-1", "hyp-s2", 1)
    if entry.strategy_id != "hyp-s2" or entry.expected_horizon != 1:
        _fail(f"remember {entry}")
    hit = index.lookup("cid-1")
    if hit is None or hit.strategy_id != "hyp-s2":
        _fail("lookup miss")
    if index.lookup("missing") is not None or index.lookup("") is not None:
        _fail("empty/missing lookup must be None")
    if len(index) != 1:
        _fail("index length")


def _translator_battery() -> None:
    observe = RecordingObserveSink()
    index = FillIndex()
    index.remember("cid-1", "hyp-s2", 8)
    with tempfile.TemporaryDirectory(prefix="s2kill-") as tmp:
        root = Path(tmp)
        refuse = root / "refuse.jsonl"
        jsonl = root / "live.jsonl"
        bus = EventBus()
        translator = FillTranslator(
            index=index,
            observe_sink=observe,
            calibrator_jsonl=jsonl,
            refuse_jsonl=refuse,
            bus=bus,
        )
        mapped = translator.ingest(_fill(), client_order_id="cid-1", reference_price=5000.0)
        if mapped.observed is not True or mapped.calibrated is not True or mapped.published is not True:
            _fail(f"mapped fan-out {mapped}")
        if abs(mapped.fill.commission - 0.94) > 1e-12:
            _fail(f"card stamp {mapped.fill.commission}")
        if abs(mapped.fill.slippage_ticks - 1.0) > 1e-12:
            _fail(f"slip ticks {mapped.fill.slippage_ticks}")
        if abs(mapped.fill.slippage_usd - 1.25) > 1e-12:
            _fail(f"slip usd {mapped.fill.slippage_usd}")
        if observe.calls != [("hyp-s2", observe_metric(mapped.fill))]:
            _fail(f"observe {observe.calls}")
        metric = observe_metric(mapped.fill)
        if metric >= 0.0 or not math.isfinite(metric):
            _fail(f"observe metric {metric}")
        fills = bus.history(RESEARCH_EXECUTION_FILL_TOPIC, limit=5)
        if len(fills) != 1 or fills[0].producer != FILL_TRANSLATOR_AGENT_ID:
            _fail("fill_translator must publish fill")
        if fills[0].payload.get("source") != BROKER_SOURCE:
            _fail("published source")
        try:
            bus.publish(topic=RESEARCH_EXECUTION_SIGNAL_TOPIC, producer=FILL_TRANSLATOR_AGENT_ID, payload={"x": 1})
            _fail("fill_translator published signal")
        except PermissionError:
            pass
        try:
            bus.publish(topic=RESEARCH_EXECUTION_ORDER_TOPIC, producer=FILL_TRANSLATOR_AGENT_ID, payload={"x": 1})
            _fail("fill_translator published order")
        except PermissionError:
            pass
        translator.assert_no_broker_submit()

        unmapped_obs = RecordingObserveSink()
        unmapped = FillTranslator(
            index=FillIndex(),
            observe_sink=unmapped_obs,
            calibrator_jsonl=root / "unmapped.jsonl",
            refuse_jsonl=root / "unmapped_refuse.jsonl",
            bus=bus,
        )
        uresult = unmapped.ingest(_fill(client_order_id="nope", fill_id="u1"), client_order_id="nope")
        if uresult.observed is not False or uresult.published is not False or uresult.calibrated is not True:
            _fail(f"unmapped {uresult}")
        if unmapped_obs.calls:
            _fail("unmapped must not observe")
        refuse_text = (root / "unmapped_refuse.jsonl").read_text(encoding="utf-8") if (root / "unmapped_refuse.jsonl").exists() else ""
        if "observe_failed" in refuse_text:
            _fail("unmapped must not look like observe failure")

        hyp = translator.ingest(_fill(source=HYPOTHETICAL_SOURCE, fill_id="h1"), client_order_id="cid-1")
        if hyp.calibrated is not False:
            _fail("hypothetical must not live-calibrate")
        if any(row.get("source") == HYPOTHETICAL_SOURCE for row in translator.calibrator_rows()):
            _fail("hypothetical row leaked")

        cheap = translator.ingest(_fill(commission=0.01, fill_id="cheap"), client_order_id="cid-1")
        if abs(cheap.fill.commission - 0.94) > 1e-12:
            _fail("execution-side must overwrite cheap commission")
        try:
            translator.ingest(_fill(source="research_four_leg"))
            _fail("unknown source ingest")
        except TranslateRefused:
            pass
        try:
            translator.ingest({"symbol": "MES", "side": "BUY", "qty": 1, "source": "broker"})
            _fail("missing price")
        except TranslateRefused:
            pass
        try:
            translator.ingest(
                {
                    "symbol": "MES",
                    "side": "BUY",
                    "qty": 0,
                    "fill_price": 5000.0,
                    "source": "broker",
                    "ts": UTC.isoformat(),
                }
            )
            _fail("qty 0")
        except TranslateRefused:
            pass
        clocked = FillTranslator(
            index=index,
            observe_sink=observe,
            bus=bus,
            clock=lambda: UTC,
        )
        timed = clocked.ingest(
            {
                "fill_id": "clock-1",
                "symbol": "MES",
                "side": "BUY",
                "qty": 1,
                "fill_price": 5000.0,
                "source": "broker",
                "client_order_id": "cid-1",
            },
            client_order_id="cid-1",
        )
        if timed.fill.event_ts != UTC:
            _fail(f"clock unused {timed.fill.event_ts}")


def _calibrator_battery() -> None:
    if normalize_fill_source("") != BROKER_SOURCE or normalize_fill_source("broker") != BROKER_SOURCE:
        _fail("empty source is broker")
    if normalize_fill_source(HYPOTHETICAL_SOURCE) != HYPOTHETICAL_SOURCE:
        _fail("hypothetical token")
    try:
        normalize_fill_source("research_four_leg")
        _fail("unknown source must refuse")
    except CalibratorRowRefused:
        pass
    if is_hypothetical_source(HYPOTHETICAL_SOURCE) is not True:
        _fail("is_hypothetical")
    if is_broker_source("research_four_leg") is not False:
        _fail("unknown is not broker")
    if is_broker_source("") is not True:
        _fail("empty is broker")
    hyp_row = live_calibrator_row(_fill(source=HYPOTHETICAL_SOURCE))
    if hyp_row is not None:
        _fail("hypothetical live row")
    broker_row = live_calibrator_row(_fill(commission=0.94, price=5000.25))
    if broker_row is None:
        _fail("broker row missing")
    if broker_row.get("event") != "reconciled" or broker_row.get("source") != BROKER_SOURCE:
        _fail(f"broker row {broker_row}")
    if broker_row.get("root") != "MES" or broker_row.get("qty") != 1:
        _fail(f"root/qty {broker_row}")
    if abs(float(broker_row["fill_price"]) - 5000.25) > 1e-12:
        _fail("fill_price")
    with tempfile.TemporaryDirectory(prefix="s2kill-cal-") as tmp:
        audit = Path(tmp) / "audit.jsonl"
        rows = [
            {
                "event": "reconciled",
                "ts": "2026-05-01T10:00:00+00:00",
                "symbol": "MES",
                "quantity": 1,
                "commission": 0.94,
                "source": HYPOTHETICAL_SOURCE,
            },
            {
                "event": "reconciled",
                "ts": "2026-05-01T11:00:00+00:00",
                "symbol": "MES",
                "quantity": 1,
                "commission": 0.94,
                "source": "research_four_leg",
            },
            {
                "event": "reconciled",
                "ts": "2026-05-01T12:00:00+00:00",
                "symbol": "MES",
                "quantity": 1,
                "commission": 0.94,
                "source": BROKER_SOURCE,
            },
        ]
        audit.write_text("\n".join(json.dumps(item) for item in rows) + "\n", encoding="utf-8")
        loaded = load_reconciled_rows(audit)
        if len(loaded) != 1 or loaded[0].get("source") != BROKER_SOURCE:
            _fail(f"load_reconciled_rows {loaded}")


def _binding_battery() -> None:
    if SUSPEND_REDUCE_FRACTION != 0.5 or DISABLE_FLATTEN_FRACTION != 1.0:
        _fail("D9 fractions")
    if SLA_RETRY_LIMIT != 1 or SLA_ESCALATE_AFTER_SECONDS != 600:
        _fail("D10 constants")
    if INDEPENDENCE_CORR_MAX != 0.5:
        _fail("D11 corr cap")
    if reduce_fraction_for_stage("suspended") != 0.5 or reduce_fraction_for_stage("deweighted") != 0.5:
        _fail("suspend map")
    if reduce_fraction_for_stage("retired") != 1.0 or reduce_fraction_for_stage("critical") != 1.0:
        _fail("flatten map")
    if reduce_fraction_for_stage("disabled") != 1.0 or reduce_fraction_for_stage("hard_limit") != 1.0:
        _fail("disable map")
    if reduce_qty("suspended", 2) != 1 or reduce_qty("retired", 2) != 2:
        _fail("reduce_qty")
    try:
        reduce_qty("suspended", 1)
        _fail("50% of 1 must refuse")
    except BindingPolicyRefused:
        pass
    try:
        reduce_fraction_for_stage("increase")
        _fail("increase stage")
    except BindingPolicyRefused:
        pass
    if sla_decision(1, 10.0) != "retry":
        _fail("first miss retry")
    if sla_decision(2, 10.0) != "escalate":
        _fail("second miss escalate")
    if sla_decision(1, 600.0) != "retry":
        _fail("exactly 10 min is retry")
    if sla_decision(1, 601.0) != "escalate":
        _fail(">10 min escalate")
    try:
        sla_decision(0, 1.0)
        _fail("miss 0")
    except BindingPolicyRefused:
        pass
    ok, reason = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=0.3,
    )
    if ok is not True or reason != "independent":
        _fail(f"independent {ok} {reason}")
    same_f, why = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="trend",
        config_id="c1",
        other_config_id="c2",
        correlation=0.2,
    )
    if same_f is not False or why != "survivors_same_family":
        _fail(f"same family {same_f} {why}")
    high, why2 = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=0.5,
    )
    if high is not False or why2 != "survivors_corr_not_independent":
        _fail(f"corr cap {high} {why2}")
    clone, why3 = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="same",
        other_config_id="same",
        correlation=0.1,
    )
    if clone is not False or why3 != "survivors_same_config":
        _fail(f"clone {clone} {why3}")
    missing, why4 = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=None,
    )
    if missing is not False or why4 != "survivors_corr_unavailable":
        _fail(f"corr none {missing} {why4}")
    try:
        sla_decision(1, True)  # type: ignore[arg-type]
        _fail("bool elapsed")
    except BindingPolicyRefused:
        pass
    nan_ok, nan_why = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=float("nan"),
    )
    if nan_ok is not False or nan_why != "survivors_corr_unavailable":
        _fail(f"nan corr {nan_ok} {nan_why}")
    bool_ok, bool_why = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=True,  # type: ignore[arg-type]
    )
    if bool_ok is not False or bool_why != "survivors_corr_unavailable":
        _fail(f"bool corr {bool_ok} {bool_why}")
    wide_ok, wide_why = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=1.5,
    )
    if wide_ok is not False or wide_why != "survivors_corr_unavailable":
        _fail(f"wide corr {wide_ok} {wide_why}")
    orig_frac = SUSPEND_REDUCE_FRACTION
    binding_mod.SUSPEND_REDUCE_FRACTION = 2.0
    try:
        try:
            reduce_qty("suspended", 2)
            _fail("non-partial reduce")
        except BindingPolicyRefused as exc:
            if "reduce_qty_not_partial" not in str(exc):
                _fail(str(exc))
    finally:
        binding_mod.SUSPEND_REDUCE_FRACTION = orig_frac


def _research_calibrate_battery() -> None:
    if abs(card_commission_usd("MES", 1) - 0.94) > 1e-12:
        _fail("card MES")
    if abs(card_commission_usd("ES", 1) - 2.87) > 1e-12:
        _fail("card ES")
    assert_does_not_undercut_card("MES", research_commission_usd("MES", 1), 1)
    try:
        assert_does_not_undercut_card("MES", 0.93, 1)
        _fail("undercut allowed")
    except CostCalibrateRefused:
        pass
    if abs(tighten_only(0.10, 0.20) - 0.20) > 1e-12:
        _fail("tighten up")
    if abs(tighten_only(0.10, 0.05) - 0.10) > 1e-12:
        _fail("never cheapen")
    kept, flagged = execution_wins(3.0, 0.94)
    if abs(kept - 0.94) > 1e-12 or flagged is not True:
        _fail(f"execution wins {kept} {flagged}")
    with tempfile.TemporaryDirectory(prefix="s2kill-res-") as tmp:
        live = Path(tmp) / "cost_model_calibration.json"
        try:
            write_research_calibration(live, {"x": 1})
            _fail("wrote live calibration")
        except CostCalibrateRefused:
            pass
        out = Path(tmp) / "research_cost_calibration.json"
        payload = calibrate_fills(
            [
                {
                    "symbol": "MES",
                    "qty": 1,
                    "commission": 0.94,
                    "slippage_usd": 1.25,
                    "source": HYPOTHETICAL_SOURCE,
                },
                {
                    "symbol": "MES",
                    "qty": 1,
                    "commission": 0.94,
                    "slippage_usd": 1.25,
                    "source": BROKER_SOURCE,
                },
                {
                    "symbol": "ES",
                    "qty": 1,
                    "commission": 2.87,
                    "slippage_usd": 12.50,
                    "source": BROKER_SOURCE,
                },
            ],
            output=out,
        )
        if payload.get("winner") != "execution_side":
            _fail("winner")
        if payload["by_root"]["MES"]["sample_count"] != 1:
            _fail("hypothetical counted")
        if payload["by_root"]["MES"]["research_commission_usd"] + 1e-12 < 0.94:
            _fail("MES undercut after calibrate")
        if payload["by_root"]["ES"]["research_commission_usd"] + 1e-12 < 2.87:
            _fail("ES undercut after calibrate")
        if live.exists():
            _fail("live file created")
        if not out.is_file():
            _fail("research file missing")


def _gap_battery() -> None:
    if D7_DEFAULT_SLA_SECONDS != 300 or D7_CRITICAL_SLA_SECONDS != 60:
        _fail("D7 SLA constants")
    if abs(research_commission_usd("MES") - research_commission_usd("MES", 1)) > 1e-12:
        _fail("research default qty")
    if abs(research_commission_usd("MES", 2) - 2.0 * research_commission_usd("MES", 1)) > 1e-12:
        _fail("research qty product")
    try:
        research_commission_usd("MES", 0)
        _fail("research qty 0")
    except CostCalibrateRefused as exc:
        if "qty_invalid" not in str(exc):
            _fail(str(exc))
    try:
        research_commission_usd("MES", True)  # type: ignore[arg-type]
        _fail("bool qty")
    except CostCalibrateRefused:
        pass
    try:
        card_commission_usd("NOTAROOT")
        _fail("unknown root card")
    except CostCalibrateRefused as exc:
        if "root_not_on_card" not in str(exc):
            _fail(str(exc))
    try:
        root_of_symbol("NOTAROOT")
        _fail("root_of_symbol")
    except CalibratorRowRefused:
        pass
    if is_hypothetical_source("research_four_leg") is not False:
        _fail("unknown is not hypothetical")
    try:
        live_calibrator_row(_fill(quantity=0))
        _fail("qty 0 row")
    except CalibratorRowRefused as exc:
        if "qty_invalid" not in str(exc):
            _fail(str(exc))
    try:
        live_calibrator_row(_fill(symbol="NOTAROOT"))
        _fail("unknown root row")
    except CalibratorRowRefused:
        pass
    naive = _fill()
    naive.event_ts = datetime(2026, 10, 29, 12, 0)
    row = live_calibrator_row(naive)
    if row is None or "+" not in str(row["ts"]) and "Z" not in str(row["ts"]):
        _fail(f"naive ts {None if row is None else row.get('ts')}")
    tagged = live_calibrator_row(_fill(strategy_id="hyp-s2"))
    if tagged is None or tagged.get("strategy_id") != "hyp-s2":
        _fail("strategy wiped")
    if abs(float(tagged["slippage_points"])) > 1e-12:
        pass
    slipped = _fill()
    slipped.slippage_ticks = 1.0
    slipped.slippage_usd = 1.25
    srow = live_calibrator_row(slipped)
    if srow is None or abs(float(srow["slippage_points"]) - 0.25) > 1e-12:
        _fail(f"slippage_points {None if srow is None else srow.get('slippage_points')}")
    try:
        reduce_qty("suspended", True)  # type: ignore[arg-type]
        _fail("bool open_qty")
    except BindingPolicyRefused:
        pass
    try:
        reduce_qty("suspended", 0)
        _fail("open_qty 0")
    except BindingPolicyRefused as exc:
        if "open_qty_invalid" not in str(exc):
            _fail(str(exc))
    try:
        sla_decision(1, float("nan"))
        _fail("nan elapsed")
    except BindingPolicyRefused:
        pass
    missing, why = independent(
        hypothesis_id="",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=0.1,
    )
    if missing is not False or why != "survivors_identity_missing":
        _fail(f"empty hypothesis {missing} {why}")
    try:
        assert_does_not_undercut_card("MES", float("nan"))
        _fail("nan research commission")
    except CostCalibrateRefused:
        pass
    try:
        execution_wins(float("nan"), 0.94)
        _fail("nan research total")
    except CostCalibrateRefused:
        pass
    same, flagged = execution_wins(0.94, 0.94)
    if flagged is not False or abs(same - 0.94) > 1e-12:
        _fail(f"matching totals {same} {flagged}")
    try:
        tighten_only(float("nan"), 0.2)
        _fail("nan old coeff")
    except CostCalibrateRefused:
        pass
    try:
        tighten_only(0.2, float("nan"))
        _fail("nan new coeff")
    except CostCalibrateRefused:
        pass
    try:
        stamp_slippage(symbol="MES", side="BUY", fill_price=5000.0, reference_price=5000.0, qty=0)
        _fail("slip qty 0")
    except FillStampRefused as exc:
        if "qty_invalid" not in str(exc):
            _fail(str(exc))
    try:
        stamp_slippage(symbol="MES", side="BUY", fill_price=5000.0, reference_price=5000.0, qty=True)  # type: ignore[arg-type]
        _fail("slip bool qty")
    except FillStampRefused:
        pass
    half = stamp_slippage(symbol="MES", side="BUY", fill_price=0.5, reference_price=0.5, qty=1)
    if half is None:
        _fail("0.5 fill/ref must be allowed vs zero-guard")
    try:
        stamp_slippage(symbol="MES", side="BUY", fill_price=0.0, reference_price=5000.0, qty=1)
        _fail("zero fill_price")
    except FillStampRefused:
        pass
    spec = research_spec_for("MES")
    engine = CostModel()
    market = MarketSnapshot(volume=1000.0, average_volume=1000.0, volatility_price=spec.tick_size * 4.0)
    want = float(engine.ticks_for_fill(spec=spec, quantity=1.0, market=market).total_usd)
    if abs(research_four_leg_usd("MES", 1, engine) - want) > 1e-9:
        _fail("four-leg uses tick*4 snapshot")
    fat = CostModel(slippage_coefficient=9.0, impact_coefficient=9.0)
    if abs(research_four_leg_usd("MES", 1, fat) - research_four_leg_usd("MES", 1, CostModel())) < 1e-9:
        _fail("custom model ignored")
    calibrated = calibrate_root(root="MES", execution_commission_usd=0.94, execution_slippage_usd=1.25)
    if calibrated.sample_count != 1 or abs(calibrated.execution_commission_usd - 0.94) > 1e-12:
        _fail("calibrate_root defaults")
    try:
        calibrate_root(root="MES", execution_commission_usd=0.94, execution_slippage_usd=0.0, sample_count=0)
        _fail("sample_count 0")
    except CostCalibrateRefused as exc:
        if "sample_count_invalid" not in str(exc):
            _fail(str(exc))
    orig_spec = stamp_mod.spec_for
    orig_all_in = stamp_mod.all_in_per_side_usd

    class _ZeroTick:
        tick_size = 0.25
        point_value_usd = 0.0

    stamp_mod.spec_for = lambda symbol: _ZeroTick()  # type: ignore[assignment]
    try:
        try:
            stamp_commission("MES", 1)
            _fail("zero tick allowed")
        except FillStampRefused as exc:
            if "tick_value_invalid" not in str(exc):
                _fail(str(exc))
    finally:
        stamp_mod.spec_for = orig_spec
    stamp_mod.all_in_per_side_usd = lambda *args, **kwargs: 0.0  # type: ignore[assignment]
    try:
        try:
            stamp_commission("MES", 1)
            _fail("zero commission allowed")
        except FillStampRefused as exc:
            if "commission_zero" not in str(exc):
                _fail(str(exc))
    finally:
        stamp_mod.all_in_per_side_usd = orig_all_in

    index = FillIndex()
    index.remember("cid-1", "hyp-s2", 8)
    bus = EventBus()
    translator = FillTranslator(index=index, bus=bus)
    nosink = translator.ingest(_fill(), client_order_id="cid-1")
    if nosink.observed is not False:
        _fail("no observe sink")
    try:
        translator.ingest(object())  # type: ignore[arg-type]
        _fail("unsupported payload")
    except (TranslateRefused, TypeError):
        pass
    try:
        translator.ingest(_fill(symbol="NOTAROOT"), client_order_id="cid-1")
        _fail("unknown root ingest")
    except TranslateRefused:
        pass
    try:
        translator.ingest(_fill(), client_order_id="cid-1", reference_price=0.0)
        _fail("zero reference ingest")
    except TranslateRefused:
        pass
    t = FillTranslator()
    t._broker_submits = 1
    try:
        t.assert_no_broker_submit()
    except AssertionError as exc:
        if "fill_translator recorded a broker submit" not in str(exc):
            raise
    else:
        _fail("broker submit silent")
    assert_does_not_undercut_card("MES", research_commission_usd("MES"))
    log = logging.getLogger("lumina.research_bridge.fill_translator")
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    log.addHandler(handler)
    prev = log.level
    log.setLevel(logging.WARNING)
    try:
        match_t = FillTranslator(index=index, bus=bus)
        match_t.ingest(_fill(commission=0.94, fill_id="match"), client_order_id="cid-1")
        if "cost_discrepancy" in buf.getvalue():
            _fail("matching card must not log discrepancy")
        buf.truncate(0)
        buf.seek(0)
        match_t.ingest(_fill(commission=0.01, fill_id="cheap-log"), client_order_id="cid-1")
        if "cost_discrepancy" not in buf.getvalue():
            _fail("cheap claim must log discrepancy")
    finally:
        log.removeHandler(handler)
        log.setLevel(prev)
    orig_row = translator_mod.live_calibrator_row

    def _boom_row(fill: FillEvent) -> dict[str, object]:
        raise RuntimeError("row boom")

    translator_mod.live_calibrator_row = _boom_row  # type: ignore[assignment]
    try:
        boom_cal = FillTranslator()
        boom_res = boom_cal.ingest(_fill(fill_id="boom-row"))
        if boom_res.calibrated is not False or boom_cal.calibrator_rows():
            _fail("calibrator exception must not calibrate")
    finally:
        translator_mod.live_calibrator_row = orig_row
    translator_mod.live_calibrator_row = lambda fill: None  # type: ignore[assignment]
    try:
        none_cal = FillTranslator()
        none_res = none_cal.ingest(_fill(fill_id="none-row"))
        if none_res.calibrated is not False or none_cal.calibrator_rows():
            _fail("None calibrator row must not calibrate")
    finally:
        translator_mod.live_calibrator_row = orig_row

    class Boom:
        def observe(self, signal_id: str, metric: object) -> object:
            raise RuntimeError("monitor_down")

    boom_index = FillIndex()
    boom_index.remember("cid-1", "hyp-s2", 8)
    boom = FillTranslator(index=boom_index, observe_sink=Boom())  # type: ignore[arg-type]
    boom_result = boom.ingest(_fill(), client_order_id="cid-1")
    if boom_result.observed is not False or boom.observed_metrics():
        _fail("observe failure must not record")

    mapped_index = FillIndex()
    direct = FillTranslator(index=mapped_index, observe_sink=RecordingObserveSink())
    on_fill = _fill(strategy_id="hyp-direct", expected_horizon=8, client_order_id="absent")
    dres = direct.ingest(on_fill, client_order_id="")
    if dres.observed is not True:
        _fail("strategy on fill must map")
    if direct.observed_metrics()[0][0] != "hyp-direct":
        _fail("wrong mapped id")
    hz0 = FillTranslator(index=FillIndex(), observe_sink=RecordingObserveSink())
    zres = hz0.ingest(_fill(strategy_id="hyp-z", expected_horizon=0), client_order_id="")
    if zres.observed is not False:
        _fail("horizon 0 must not map from fill")
    hz8 = FillTranslator(index=FillIndex(), observe_sink=RecordingObserveSink())
    h8 = hz8.ingest(_fill(strategy_id="hyp-8", expected_horizon=8), client_order_id="")
    if h8.observed is not True:
        _fail("horizon 8 on fill must map")
    empty_sid = FillTranslator(index=FillIndex(), observe_sink=RecordingObserveSink(), bus=EventBus())
    eres = empty_sid.ingest(_fill(strategy_id="", expected_horizon=8), client_order_id="")
    if eres.observed is not False:
        _fail("empty strategy_id must not map")
    split = FillIndex()
    split.remember("cid-1", "hyp-s2", 8)
    split_t = FillTranslator(index=split, observe_sink=RecordingObserveSink())
    raw_other = _fill(client_order_id="other")
    sres = split_t.ingest(raw_other, client_order_id="cid-1")
    if sres.observed is not True:
        _fail("explicit client_order_id must win over raw")
    with tempfile.TemporaryDirectory(prefix="s2cal-") as cal_tmp:
        cal_root = Path(cal_tmp)
        audit = cal_root / "audit.jsonl"
        audit.write_text(
            '{"event":"reconciled","ts":"2026-05-01T10:00:00+00:00","symbol":"NOTAROOT",'
            '"quantity":1,"commission":0.94,"slippage_usd":1.25,"source":"broker"}\n',
            encoding="utf-8",
        )
        unknown_inst = run_daily_calibration(
            audit_path=audit,
            state_path=cal_root / "unknown.json",
            instrument="NOTAROOT",
        )
        if unknown_inst.sample_count != 0:
            _fail("unknown instrument must not calibrate")
    try:
        observe_metric(_fill(price=5000.25))
    except TranslateRefused:
        _fail("finite observe metric")
    inf_fill = _fill()
    inf_fill.slippage_usd = float("inf")
    try:
        observe_metric(inf_fill)
        _fail("inf observe metric")
    except TranslateRefused as exc:
        if "observe_metric_non_finite" not in str(exc):
            _fail(str(exc))
    hold_index = FillIndex()
    hold_index.remember("cid-1", "hyp-s2", 8)
    hold_t = FillTranslator(index=hold_index, bus=EventBus())
    hold_res = hold_t.ingest(_fill(side="HOLD"), client_order_id="cid-1")
    if hold_res.published is not False:
        _fail("HOLD must not publish")
    try:
        FillTranslator().ingest(
            {
                "symbol": "MES",
                "side": "BUY",
                "qty": "x",
                "fill_price": 5000.0,
                "source": "broker",
                "ts": "2026-10-29T12:00:00+00:00",
            }
        )
        _fail("qty x")
    except TranslateRefused:
        pass
    try:
        FillTranslator().ingest(
            {
                "symbol": "MES",
                "side": "BUY",
                "qty": 1,
                "fill_price": 5000.0,
                "source": "broker",
                "ts": "not-a-timestamp",
            }
        )
        _fail("bad ts")
    except TranslateRefused:
        pass


def run() -> None:
    _stamp_battery()
    _index_battery()
    _translator_battery()
    _calibrator_battery()
    _binding_battery()
    _research_calibrate_battery()
    _gap_battery()


if __name__ == "__main__":
    run()
