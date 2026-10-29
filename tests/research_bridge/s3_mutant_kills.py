"""Fail-closed kill battery for S2.5 NT-PIT tape + S3 sim_gate. No pytest."""

from __future__ import annotations

import math
import os
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import PromotionCandidate
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.order_gatekeeper.ungated_place_block import (
    S0_PLACE_SOURCE_ALLOWLIST,
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
)
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.independence import (
    CORR_STRICT_MAX,
    MIN_CORR_BARS,
    d11_independent,
    independent_set,
    pairwise_correlation,
)
from lumina_core.research_bridge.market_health import healthy_closed_bar, unhealthy_market
from lumina_core.research_bridge.sim_gate import (
    RESEARCH_SIM_GATED,
    S3_INSTRUMENTS,
    SIM_INSTRUMENT_NOT_YET_RELEASED,
    LoggedHumanRelease,
    SimGateRefused,
    arm_research_place,
    bind_logged_human_release,
    bind_sim_gate,
    bound_context,
    evaluate,
    evaluate_instrument,
    logged_human_release,
    non_research_release_allows,
    supervisor_source_blocked,
)
from lumina_core.research_bridge.sim_runtime import SimRuntime
from lumina_core.risk.alarm_executor import AlarmExecutor, AlarmJob
from lumina_core.risk.live_release import SECRET_ENV
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.cycles.holdout import (
    HOLDOUT_PIN_ISO,
    HOLDOUT_PIN_NS,
    HOLDOUT_PIN_UTC,
    assert_holdout_pin_closed,
    holdout_pin_is_closed,
)
from lumina_research.validation.nt_tape import (
    MIN_CLOSED_BARS,
    NtTapeMaterializer,
    TapeRefused,
    _as_object_list,
    _as_utc,
    _require_float,
    closed_bars_from_frame,
    closed_bars_from_manager,
    closed_bars_from_rows,
    fixture_closed_mes_bars,
    materializer_from_rows,
    refuse_synthetic_as_nt_pit,
    refuse_vendor_csv_substitute,
    series_from_closed_bars,
)
from tests.research_bridge.helpers import sealed_candidate, unsigned_candidate_fields
from tests.research_bridge.s3_helpers import RecordingSubmitter, fake_engine, passing_context, survivor
from tests.risk.s1_hmac import TEST_SECRET, signed_live_release

T0 = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
TAPE_NOW = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
ANTI_LEFT = (1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0)
ANTI_RIGHT = (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0)


def _fail(message: str) -> None:
    raise AssertionError(message)


def _expect_refuse(fn: object, *args: object, **kwargs: object) -> None:
    try:
        fn(*args, **kwargs)  # type: ignore[operator]
    except TapeRefused:
        return
    _fail(f"expected TapeRefused from {getattr(fn, '__name__', fn)}")


def _ohlc_rows(start: datetime, n: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    price = 5000.0
    for index in range(n):
        ts = start + timedelta(minutes=index)
        close = price + (0.25 if index % 17 else -0.25)
        rows.append(
            {
                "timestamp": ts,
                "open": price,
                "high": price + 0.50,
                "low": price - 0.50,
                "close": close,
                "volume": 1000 + index,
                "bar_period": "1m",
            }
        )
        price = close
    return rows


def _rows_crossing_holdout_pin() -> tuple[list[dict[str, object]], datetime]:
    start = HOLDOUT_PIN_UTC - timedelta(minutes=120)
    rows = _ohlc_rows(start, MIN_CLOSED_BARS)
    now = start + timedelta(minutes=MIN_CLOSED_BARS)
    return rows, now


def _epoch_closed_rows() -> tuple[list[dict[str, object]], datetime]:
    start = datetime(1970, 1, 1, tzinfo=timezone.utc)
    rows = _ohlc_rows(start, MIN_CLOSED_BARS)
    now = start + timedelta(minutes=MIN_CLOSED_BARS)
    return rows, now


def run() -> None:
    bind_sim_gate(None)
    bind_logged_human_release(None)
    if S0_PLACE_SOURCE_ALLOWLIST:
        _fail("allowlist must stay empty")
    if holdout_pin_is_closed() is not True:
        _fail("holdout pin opened")
    if HOLDOUT_PIN_ISO != "2026-01-28T23:00:00Z":
        _fail("holdout pin drifted")
    if S3_INSTRUMENTS != frozenset({"MES", "MNQ"}):
        _fail("S3 instruments drifted")
    if MIN_CLOSED_BARS < 241:
        _fail("tape floor lowered")
    if MIN_CORR_BARS < 8:
        _fail("corr window shortened")
    if CORR_STRICT_MAX != 0.5:
        _fail("corr cap drifted")
    if supervisor_source_blocked("supervisor_tick_exec.run_tick_exec") is not True:
        _fail("supervisor not blocked")
    if supervisor_source_blocked("") is True:
        _fail("empty source treated as supervisor")
    if bound_context() is not None:
        _fail("unbound context leaked")
    if logged_human_release() is not None:
        _fail("logged release leaked")
    ok, reason = evaluate()
    if ok is True or reason != RESEARCH_SIM_GATED:
        _fail("unbound evaluate opened the gate")

    _kill_sim_gate()
    _kill_independence()
    _kill_nt_tape()
    _kill_sim_runtime()
    _kill_alarm()
    _kill_place_block()
    bind_sim_gate(None)
    bind_logged_human_release(None)


def _kill_sim_gate() -> None:
    ok, reason = evaluate(passing_context())
    if ok is not True or reason != "research_sim_gate_ok":
        _fail(f"happy path failed {reason}")
    ok, reason = evaluate(passing_context(survivors=()))
    if ok is True or reason != "survivors_insufficient":
        _fail("zero survivors opened the gate")
    ok, reason = evaluate(passing_context(survivors=(survivor(tag="only", family="trend"),)))
    if ok is True:
        _fail("one survivor opened the gate")
    syn = passing_context(
        survivors=(
            survivor(tag="s1", family="trend", tape_kind="synthetic"),
            survivor(tag="s2", family="meanrev", tape_kind="synthetic"),
        )
    )
    ok, reason = evaluate(syn)
    if ok is True:
        _fail("synthetic survivors counted")
    shallow = passing_context(
        survivors=(
            replace(survivor(tag="a", family="trend"), fill_history_bars=19),
            replace(survivor(tag="b", family="meanrev"), fill_history_bars=19),
        )
    )
    ok, reason = evaluate(shallow)
    if ok is True:
        _fail("fill history below ADR-0058 window counted")
    ok, reason = evaluate(passing_context(instrument="ES"))
    if ok is True or reason != SIM_INSTRUMENT_NOT_YET_RELEASED:
        _fail("ES research order allowed")
    ok, reason = evaluate_instrument("NQ", passing_context(instrument="MES"))
    if ok is True or reason != SIM_INSTRUMENT_NOT_YET_RELEASED:
        _fail("NQ evaluate_instrument allowed")
    ok, reason = evaluate(passing_context(trade_mode="sim"))
    if ok is True:
        _fail("trade_mode=sim allowed")
    ok, reason = evaluate(passing_context(trade_mode="real"))
    if ok is True:
        _fail("trade_mode=real allowed")
    ok, reason = evaluate(passing_context(trade_mode="paper"))
    if ok is True:
        _fail("trade_mode=paper allowed")
    ok, reason = evaluate(passing_context(env=False))
    if ok is True:
        _fail("sim_real_guard without env allowed")
    ok, reason = evaluate(passing_context(boot="shadow", yaml_now="sim"))
    if ok is True:
        _fail("yaml sim lifted D1")
    ok, reason = evaluate(passing_context(far=None))
    if ok is True or reason != "far_unmeasured":
        _fail("unmeasured FAR allowed")
    ok, reason = evaluate(passing_context(far=0.06))
    if ok is True:
        _fail("FAR above floor allowed")
    ok, reason = evaluate(passing_context(far=float("nan")))
    if ok is True:
        _fail("NaN FAR allowed")
    ok, reason = evaluate(passing_context(stale=True, reduce_only=False))
    if ok is True:
        _fail("stale equity allowed a new order")
    ok, reason = evaluate(passing_context(stale=True, reduce_only=True))
    if ok is not True:
        _fail("stale reduce-only blocked")
    ok, reason = evaluate(passing_context(market=False))
    if ok is True:
        _fail("disconnected market allowed")
    ok, reason = evaluate(passing_context(connected=""))
    if ok is True:
        _fail("unknown account allowed")
    ok, reason = evaluate(passing_context(connected="LiveAcct"))
    if ok is True:
        _fail("live account allowed")
    ok, reason = evaluate(passing_context(hmac_ok=False))
    if ok is True:
        _fail("missing promotion hmac allowed")
    ok, reason = evaluate(passing_context(approval_required=False))
    if ok is True:
        _fail("approval not required opened the gate")
    ok, reason = evaluate(passing_context(approval_present=False))
    if ok is True:
        _fail("missing approval opened the gate")
    ok, reason = evaluate(
        passing_context(
            survivors=(
                replace(survivor(tag="a", family="trend"), stage="retired"),
                survivor(tag="b", family="meanrev"),
            )
        )
    )
    if ok is True:
        _fail("retired survivor counted")
    ok, reason = evaluate(
        passing_context(
            survivors=(
                replace(survivor(tag="a", family="trend"), passed_validation_gate=False),
                survivor(tag="b", family="meanrev"),
            )
        )
    )
    if ok is True:
        _fail("failed gate survivor counted")
    ok, reason = evaluate(
        passing_context(
            survivors=(
                replace(survivor(tag="a", family="trend"), expected_horizon_bars=0),
                survivor(tag="b", family="meanrev"),
            )
        )
    )
    if ok is True:
        _fail("zero horizon survivor counted")
    ok, reason = evaluate(
        passing_context(
            survivors=(
                replace(survivor(tag="a", family="trend"), validation_mac="short"),
                survivor(tag="b", family="meanrev"),
            )
        )
    )
    if ok is True:
        _fail("short mac survivor counted")
    try:
        with arm_research_place(passing_context(boot="off")):
            _fail("arm_research_place with boot off")
    except SimGateRefused:
        pass
    bind_logged_human_release(
        LoggedHumanRelease(adr_path="docs/adr/0063-sim-orders-gated.md", approved_by="steve", purpose="manual_place")
    )
    if non_research_release_allows("supervisor_tick_exec") is True:
        _fail("supervisor via logged release")
    if non_research_release_allows("operations_service_orders.place_order") is not True:
        _fail("logged release did not allow manual")
    bind_logged_human_release(
        LoggedHumanRelease(adr_path="docs/adr/0063-sim-orders-gated.md", approved_by="research_ops", purpose="manual_place")
    )
    if non_research_release_allows("operations_service_orders.place_order") is True:
        _fail("agent-named approver allowed")
    bind_logged_human_release(None)
    previous_secret = os.environ.get(SECRET_ENV)
    os.environ[SECRET_ENV] = TEST_SECRET
    try:
        record = signed_live_release(now=T0)
        ok, reason = evaluate(passing_context(live_release=record))
        if ok is True:
            _fail("HMAC LIVE_RELEASE mixed with first SIM")
    finally:
        if previous_secret is None:
            os.environ.pop(SECRET_ENV, None)
        else:
            os.environ[SECRET_ENV] = previous_secret


def _kill_independence() -> None:
    corr, status = pairwise_correlation(None, ANTI_LEFT)
    if corr is not None or status != "survivors_corr_unavailable":
        _fail("missing series not fail-closed")
    corr, status = pairwise_correlation("nope", ANTI_LEFT)
    if status != "survivors_corr_unavailable":
        _fail("string series counted")
    short = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
    corr, status = pairwise_correlation(short, short)
    if status != "survivors_corr_unavailable":
        _fail("series shorter than MIN_CORR_BARS counted")
    corr, status = pairwise_correlation((1.0,) * 8, (1.0,) * 8)
    if status != "survivors_corr_unavailable":
        _fail("zero-variance series counted")
    corr, status = pairwise_correlation((float("nan"),) * 8, ANTI_LEFT)
    if status != "survivors_corr_unavailable":
        _fail("NaN series counted")
    corr, status = pairwise_correlation(ANTI_LEFT, ANTI_RIGHT)
    if status != "ok" or corr is None or corr >= CORR_STRICT_MAX:
        _fail(f"anti-corr pair unavailable {corr} {status}")
    if abs(float(corr) + 1.0) > 1e-9:
        _fail(f"anti-corr pair not -1 {corr}")
    corr, status = pairwise_correlation((1.0,) * 8, ANTI_LEFT)
    if status != "survivors_corr_unavailable":
        _fail("one-sided zero-variance series counted")
    weak_right = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    corr, status = pairwise_correlation(ANTI_LEFT, weak_right)
    if status != "ok" or corr is None or corr <= 0.05 or corr >= CORR_STRICT_MAX:
        _fail(f"weak positive corr lost {corr} {status}")
    neg_right = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    corr, status = pairwise_correlation(ANTI_LEFT, neg_right)
    if status != "ok" or corr is None or corr >= -0.05 or corr <= -0.999:
        _fail(f"weak negative corr clamped {corr} {status}")
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        left_returns=None,
        right_returns=ANTI_RIGHT,
        correlation=None,
    )
    if ok is True:
        _fail("missing returns counted independent")
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        left_returns=ANTI_LEFT,
        right_returns=ANTI_RIGHT,
    )
    if ok is not True:
        _fail(f"anti-corr pair not independent {reason}")
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="trend",
        config_id="c1",
        other_config_id="c2",
        left_returns=ANTI_LEFT,
        right_returns=ANTI_RIGHT,
    )
    if ok is True:
        _fail("same family counted independent")
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c1",
        left_returns=ANTI_LEFT,
        right_returns=ANTI_RIGHT,
    )
    if ok is True:
        _fail("same config counted independent")
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        left_returns=ANTI_LEFT,
        right_returns=ANTI_LEFT,
        correlation=0.5,
    )
    if ok is True:
        _fail("corr 0.5 counted independent")
    ok, reason = d11_independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        left_returns=ANTI_LEFT,
        right_returns=ANTI_RIGHT,
        correlation=0.499,
    )
    if ok is not True:
        _fail("corr 0.499 not independent")
    chosen, reason = independent_set((survivor(tag="only", family="trend"),))
    if chosen != () or reason != "survivors_insufficient":
        _fail("single survivor set independent")
    left = survivor(tag="a", family="trend")
    clone = replace(survivor(tag="a2", family="meanrev"), config_id=left.config_id)
    chosen, reason = independent_set((left, clone))
    if len(chosen) >= 2:
        _fail("config clones formed an independent set")


def _kill_nt_tape() -> None:
    refuse_synthetic_as_nt_pit("nt_pit")
    try:
        refuse_synthetic_as_nt_pit("synthetic")
        _fail("synthetic labeled nt_pit")
    except TapeRefused:
        pass
    try:
        refuse_synthetic_as_nt_pit("planted_edge")
        _fail("planted_edge labeled nt_pit")
    except TapeRefused:
        pass
    refuse_vendor_csv_substitute("")
    try:
        refuse_vendor_csv_substitute("data/yahoo_mes.csv")
        _fail("vendor csv allowed")
    except TapeRefused:
        pass
    rows = fixture_closed_mes_bars(now=TAPE_NOW)
    bars = closed_bars_from_rows(rows, now=TAPE_NOW, purpose="gate")
    if len(bars) < MIN_CLOSED_BARS:
        _fail("closed tape too short")
    if any(item.timestamp > TAPE_NOW for item in bars):
        _fail("future bar in closed tape")
    gross, positions, markets = series_from_closed_bars(bars)
    if len(gross) != len(positions) or len(gross) != len(markets):
        _fail("series length mismatch")
    if any(not math.isfinite(item) for item in gross):
        _fail("non-finite return")
    materializer = materializer_from_rows(rows, now=TAPE_NOW, purpose="gate")
    if materializer.tape_kind != "nt_pit":
        _fail("materializer tape_kind")
    materializer(None)  # type: ignore[arg-type]
    bad = list(rows)
    bad[-1] = {**bad[-1], "timestamp": TAPE_NOW + timedelta(minutes=5)}
    _expect_refuse(closed_bars_from_rows, bad, now=TAPE_NOW, purpose="gate")
    shuffled = list(rows)
    shuffled[10], shuffled[11] = shuffled[11], shuffled[10]
    _expect_refuse(closed_bars_from_rows, shuffled, now=TAPE_NOW, purpose="gate")
    _expect_refuse(closed_bars_from_rows, ["nope"], now=TAPE_NOW, purpose="gate")
    _expect_refuse(closed_bars_from_rows, rows[:10], now=TAPE_NOW, purpose="gate")
    _expect_refuse(closed_bars_from_rows, rows, now=TAPE_NOW, purpose="not_a_purpose")
    _expect_refuse(closed_bars_from_frame, None, now=TAPE_NOW)
    _expect_refuse(closed_bars_from_frame, SimpleNamespace(empty=True), now=TAPE_NOW)
    _expect_refuse(closed_bars_from_manager, SimpleNamespace(ohlc_1min=None), now=TAPE_NOW)
    _expect_refuse(fixture_closed_mes_bars, n=10, now=TAPE_NOW)
    _expect_refuse(
        fixture_closed_mes_bars,
        start=datetime(2026, 2, 1, tzinfo=timezone.utc),
        now=TAPE_NOW,
    )

    class _Frame:
        empty = False

        def to_dict(self, orient: str) -> list[dict[str, object]]:
            del orient
            return list(rows)

    framed = closed_bars_from_frame(_Frame(), now=TAPE_NOW, purpose="gate")
    if len(framed) < MIN_CLOSED_BARS:
        _fail("frame tape too short")
    try:
        assert_holdout_pin_closed(ts_ns=HOLDOUT_PIN_NS, purpose="gate")
        _fail("holdout pin opened for gate")
    except Exception:
        pass
    try:

        class _Sub(NtTapeMaterializer):
            pass

        _Sub(bars)
        _fail("subclass stamped nt_pit")
    except TapeRefused:
        pass
    _expect_refuse(NtTapeMaterializer, bars[:2])
    _expect_refuse(_as_utc, None)
    _expect_refuse(_as_utc, object())
    _expect_refuse(_as_object_list, {"not": "list"})
    _expect_refuse(_as_object_list, tuple(rows))
    _expect_refuse(_require_float, {"open": True}, "open")
    _expect_refuse(_require_float, {}, "open")
    _expect_refuse(_require_float, {"open": "nope"}, "open")
    _expect_refuse(_require_float, {"open": float("inf")}, "open")
    _expect_refuse(closed_bars_from_rows, None, now=TAPE_NOW, purpose="gate")
    _expect_refuse(closed_bars_from_rows, "abc", now=TAPE_NOW, purpose="gate")
    _expect_refuse(closed_bars_from_frame, "abc", now=TAPE_NOW)
    forming_now = rows[-1]["timestamp"] - timedelta(seconds=1)
    _expect_refuse(closed_bars_from_rows, rows, now=forming_now, purpose="gate")
    broken = list(rows)
    broken[0] = {**broken[0], "high": 1.0, "low": 9.0, "open": 5.0, "close": 5.0}
    _expect_refuse(closed_bars_from_rows, broken, now=TAPE_NOW, purpose="gate")

    class _TupleFrame:
        empty = False

        def to_dict(self, orient: str) -> tuple[dict[str, object], ...]:
            del orient
            return tuple(rows)

    _expect_refuse(closed_bars_from_frame, _TupleFrame(), now=TAPE_NOW)
    pin_rows, pin_now = _rows_crossing_holdout_pin()
    _expect_refuse(closed_bars_from_rows, pin_rows, now=pin_now, purpose="gate")
    eval_bars = closed_bars_from_rows(pin_rows, now=pin_now, purpose="evaluation")
    if len(eval_bars) < MIN_CLOSED_BARS:
        _fail("evaluation tape refused post-pin bars")
    if any(item.timestamp >= HOLDOUT_PIN_UTC for item in eval_bars) is False:
        _fail("evaluation tape lost post-pin coverage")
    epoch_rows, epoch_now = _epoch_closed_rows()
    epoch_bars = closed_bars_from_rows(epoch_rows, now=epoch_now, purpose="gate")
    if len(epoch_bars) < MIN_CLOSED_BARS:
        _fail("epoch tape refused")


def _kill_sim_runtime() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = Path(tmp) / "s3.jsonl"
        ctx = passing_context()
        bind_sim_gate(ctx)
        submitter = RecordingSubmitter()
        runtime = SimRuntime(
            bus=EventBus(),
            authority=ProvenanceAuthority(),
            jsonl_path=jsonl,
            market=healthy_closed_bar(close=5000.0),
            fill_index=FillIndex(),
            gate_ctx=ctx,
            engine=fake_engine(),
            submitter=submitter,
            pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
        )
        if runtime.issued_intents() != ():
            _fail("intents before candidate")
        if runtime.submitted_orders() != ():
            _fail("orders before candidate")
        if runtime.broker_submit_count() != 0:
            _fail("broker count before candidate")
        result = runtime.on_candidate(sealed_candidate(runtime._authority, instrument="MES"))
        if result is None or result.accepted is not True:
            _fail("happy sim_runtime did not submit")
        if runtime.broker_submit_count() < 1:
            _fail("broker submit not counted")
        if not runtime.submitted_orders():
            _fail("submitted_orders empty")
        if not runtime.issued_intents():
            _fail("issued_intents empty")
        if len(runtime._fill_index) < 1:
            _fail("accepted fill not indexed")
        forged = type(sealed_candidate(runtime._authority)).model_validate(
            {**unsigned_candidate_fields(), "issue_mac": "0" * 64}
        )
        if runtime.on_candidate(forged) is not None:
            _fail("forged candidate submitted")
        if runtime.on_candidate(sealed_candidate(runtime._authority, instrument="ES")) is not None:
            _fail("ES candidate submitted")
        missing = SimRuntime(
            bus=EventBus(),
            authority=ProvenanceAuthority(),
            jsonl_path=Path(tmp) / "missing.jsonl",
            market=healthy_closed_bar(close=5000.0),
            fill_index=FillIndex(),
            gate_ctx=ctx,
            engine=None,
            submitter=None,
            pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
        )
        if missing.on_candidate(sealed_candidate(missing._authority)) is not None:
            _fail("missing submitter still submitted")
        unhealthy = SimRuntime(
            bus=EventBus(),
            authority=ProvenanceAuthority(),
            jsonl_path=Path(tmp) / "unhealthy.jsonl",
            market=unhealthy_market(),
            fill_index=FillIndex(),
            gate_ctx=ctx,
            engine=fake_engine(),
            submitter=RecordingSubmitter(),
            pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
        )
        if unhealthy.on_candidate(sealed_candidate(unhealthy._authority)) is not None:
            _fail("unhealthy market submitted")
        blocked = SimRuntime(
            bus=EventBus(),
            authority=ProvenanceAuthority(),
            jsonl_path=Path(tmp) / "blocked.jsonl",
            market=healthy_closed_bar(close=5000.0),
            fill_index=FillIndex(),
            gate_ctx=ctx,
            engine=fake_engine(),
            submitter=RecordingSubmitter(),
            pre_trade_gate=lambda *args, **kwargs: (False, "constitution_blocked"),
        )
        if blocked.on_candidate(sealed_candidate(blocked._authority)) is not None:
            _fail("admission reject still submitted")
        if blocked.broker_submit_count() != 0:
            _fail("admission reject counted a submit")
        if runtime._on_bus_candidate(SimpleNamespace()) is not None:
            _fail("invalid bus candidate returned a value")
        fractional = sealed_candidate(runtime._authority, quantity=0.4)
        if runtime.on_candidate(fractional) is not None:
            _fail("qty < 1 submitted")
        fields = unsigned_candidate_fields(expected_horizon_bars=0)
        horizon_mac = runtime._authority.seal_issue(fields)
        horizon_zero = PromotionCandidate.model_construct(**{**fields, "issue_mac": horizon_mac})
        if runtime.on_candidate(horizon_zero) is not None:
            _fail("horizon 0 submitted")
        shadow = SimRuntime(
            bus=EventBus(),
            authority=ProvenanceAuthority(),
            jsonl_path=Path(tmp) / "shadow.jsonl",
            market=healthy_closed_bar(close=5000.0),
            fill_index=FillIndex(),
            gate_ctx=passing_context(boot="shadow"),
            engine=fake_engine(),
            submitter=RecordingSubmitter(),
            pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
        )
        if shadow.on_candidate(sealed_candidate(shadow._authority, instrument="MES")) is not None:
            _fail("shadow boot submitted MES")
        half = SimRuntime(
            bus=EventBus(),
            authority=ProvenanceAuthority(),
            jsonl_path=Path(tmp) / "half.jsonl",
            market=healthy_closed_bar(close=5000.0),
            fill_index=FillIndex(),
            gate_ctx=ctx,
            engine=fake_engine(),
            submitter=None,
            pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
        )
        if half.on_candidate(sealed_candidate(half._authority)) is not None:
            _fail("submitter-only-missing submitted")
        risked = SimRuntime(
            bus=EventBus(),
            authority=ProvenanceAuthority(),
            jsonl_path=Path(tmp) / "risk.jsonl",
            market=healthy_closed_bar(close=5000.0),
            fill_index=FillIndex(),
            gate_ctx=ctx,
            engine=fake_engine(),
            submitter=RecordingSubmitter(),
            pre_trade_gate=lambda *args, **kwargs: (
                (False, "risk_nonzero") if float(kwargs.get("proposed_risk", 1.0)) != 0.0 else (True, "ok")
            ),
        )
        if risked.on_candidate(sealed_candidate(risked._authority)) is None:
            _fail("zero proposed_risk blocked")
        rejected = RecordingSubmitter(accept=False)
        reject_index = FillIndex()
        denying = SimRuntime(
            bus=EventBus(),
            authority=ProvenanceAuthority(),
            jsonl_path=Path(tmp) / "deny.jsonl",
            market=healthy_closed_bar(close=5000.0),
            fill_index=reject_index,
            gate_ctx=ctx,
            engine=fake_engine(),
            submitter=rejected,
            pre_trade_gate=lambda *args, **kwargs: (True, "ok"),
        )
        deny_result = denying.on_candidate(sealed_candidate(denying._authority))
        if deny_result is None or deny_result.accepted is True:
            _fail("rejected submit not returned")
        if len(reject_index) != 0:
            _fail("rejected submit was indexed")


def _kill_alarm() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = Path(tmp) / "alarm.jsonl"
        positions = LivePositionManager(app=SimpleNamespace())
        positions.set_strategy_qty("hyp-a", 2)
        positions.set_strategy_qty("hyp-b", 3)
        submitter = RecordingSubmitter()
        exe = AlarmExecutor(
            bus=EventBus(),
            positions=positions,
            submitter=submitter,
            jsonl_path=jsonl,
            clock=lambda: T0,
        )
        exe.install()
        exe._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-a", "instrument": "MES"}))
        if not submitter.orders or submitter.orders[0].quantity != 1:
            _fail("deweight did not reduce 50%")
        if submitter.orders[0].metadata.get("reduce_only") is not True:
            _fail("deweight not reduce_only")
        stack = "\n".join(submitter.stack_at_submit)
        if "lumina_research/" in stack:
            if any("lumina_research" in line and "tests" not in line for line in submitter.stack_at_submit):
                _fail("research in submit stack")
        if positions.strategy_qty("hyp-a") != 1:
            _fail("deweight book not updated")
        exe._on_retire(SimpleNamespace(payload={"hypothesis_id": "hyp-b", "instrument": "MES"}))
        last = submitter.orders[-1]
        if last.quantity != 3:
            _fail("retire did not flatten strategy qty")
        if positions.strategy_qty("hyp-b") != 0:
            _fail("retire left qty")
        exe._on_deweight(SimpleNamespace(payload={"instrument": "MES"}))
        exe.tick()
        exe.tick(T0)
        positions.set_strategy_qty("hyp-flat", 0)
        exe._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-flat", "instrument": "MES"}))
        exe._on_guardian(
            SimpleNamespace(payload={"hypothesis_id": "hyp-g", "severity": "info", "instrument": "MES"})
        )
        positions.set_strategy_qty("hyp-g2", 2)
        exe._on_guardian(
            SimpleNamespace(
                payload={"hypothesis_id": "hyp-g2", "severity": "critical", "instrument": "MNQ"}
            )
        )
        if positions.strategy_qty("hyp-g2") != 0:
            _fail("critical guardian did not flatten")
        rejector = RecordingSubmitter(accept=False)
        clock = {"now": T0}

        def _clock() -> datetime:
            return clock["now"]

        positions2 = LivePositionManager(app=SimpleNamespace())
        positions2.set_strategy_qty("hyp-sla", 2)
        sla = AlarmExecutor(
            bus=EventBus(),
            positions=positions2,
            submitter=rejector,
            jsonl_path=Path(tmp) / "sla.jsonl",
            clock=_clock,
        )
        sla._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-sla", "instrument": "MES"}))
        clock["now"] = T0 + timedelta(seconds=301)
        sla.tick(clock["now"])
        if sla.jobs[0].retried is not True:
            _fail("first SLA miss did not retry")
        clock["now"] = T0 + timedelta(seconds=601)
        sla.tick(clock["now"])
        if sla.jobs[0].closed is not True:
            _fail("second SLA miss did not close")
        after = len(rejector.orders)
        clock["now"] = T0 + timedelta(seconds=1200)
        sla.tick(clock["now"])
        sla.tick(clock["now"])
        if len(rejector.orders) != after:
            _fail("SLA retried forever")
        if exe.reconciles != 0:
            _fail("reconciles defaulted away from zero")
        exe.reconcile_on_reconnect()
        if exe.reconciles != 1:
            _fail("reconcile not counted once")
        extra_orders = len(submitter.orders)
        exe.tick(T0)
        exe.tick(T0)
        if len(submitter.orders) != extra_orders:
            _fail("executed alarm retried on later tick")
        positions.set_strategy_qty("hyp-mnq", 4)
        exe._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-mnq", "instrument": "MNQ"}))
        mnq_jobs = [job for job in exe.jobs if job.strategy_id == "hyp-mnq"]
        if not mnq_jobs or mnq_jobs[-1].instrument != "MNQ":
            _fail("MNQ alarm coerced off MNQ")
        if exe._on_deweight(SimpleNamespace(payload={"instrument": "MES"})) is not None:
            _fail("missing strategy_id returned a value")
        if exe._propose(SimpleNamespace(payload={"instrument": "MES"}), stage="deweighted") is not None:
            _fail("missing strategy_id _propose returned a value")
        positions.set_strategy_qty("hyp-suspend", 2)
        exe._on_guardian(
            SimpleNamespace(
                payload={
                    "hypothesis_id": "hyp-suspend",
                    "severity": "info",
                    "suspend_proposed": True,
                    "instrument": "MES",
                }
            )
        )
        if positions.strategy_qty("hyp-suspend") != 1:
            _fail("suspend_proposed did not reduce")
        clock_far = {"now": T0}

        def _far_clock() -> datetime:
            return clock_far["now"]

        positions3 = LivePositionManager(app=SimpleNamespace())
        positions3.set_strategy_qty("hyp-now", 2)
        far = AlarmExecutor(
            bus=EventBus(),
            positions=positions3,
            submitter=RecordingSubmitter(accept=False),
            jsonl_path=Path(tmp) / "far.jsonl",
            clock=_far_clock,
        )
        far._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-now", "instrument": "MES"}))
        clock_far["now"] = T0 + timedelta(hours=3)
        far.tick(T0)
        if far.jobs[0].miss_count != 0:
            _fail("tick(now=) ignored explicit now")
        clock61 = {"now": T0}

        def _clock61() -> datetime:
            return clock61["now"]

        positions4 = LivePositionManager(app=SimpleNamespace())
        positions4.set_strategy_qty("hyp-61", 2)
        slow = AlarmExecutor(
            bus=EventBus(),
            positions=positions4,
            submitter=RecordingSubmitter(accept=False),
            jsonl_path=Path(tmp) / "slow.jsonl",
            clock=_clock61,
        )
        slow._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-61", "instrument": "MES"}))
        if slow.jobs[0].miss_count != 0:
            _fail("first deweight counted as SLA miss")
        clock61["now"] = T0 + timedelta(seconds=61)
        slow.tick(clock61["now"])
        if slow.jobs[0].miss_count != 0:
            _fail("deweight 61s treated as SLA miss")
        clock_ret = {"now": T0}

        def _clock_ret() -> datetime:
            return clock_ret["now"]

        positions_ret = LivePositionManager(app=SimpleNamespace())
        positions_ret.set_strategy_qty("hyp-crit61", 2)
        retired = AlarmExecutor(
            bus=EventBus(),
            positions=positions_ret,
            submitter=RecordingSubmitter(accept=False),
            jsonl_path=Path(tmp) / "ret.jsonl",
            clock=_clock_ret,
        )
        retired._on_retire(SimpleNamespace(payload={"hypothesis_id": "hyp-crit61", "instrument": "MES"}))
        clock_ret["now"] = T0 + timedelta(seconds=61)
        retired.tick(clock_ret["now"])
        if retired.jobs[0].miss_count < 1:
            _fail("retired 61s not an SLA miss")
        positions5 = LivePositionManager(app=SimpleNamespace())
        positions5.set_strategy_qty("hyp-10m", 2)
        clock10 = {"now": T0}

        def _clock10() -> datetime:
            return clock10["now"]

        escalate = AlarmExecutor(
            bus=EventBus(),
            positions=positions5,
            submitter=RecordingSubmitter(accept=False),
            jsonl_path=Path(tmp) / "ten.jsonl",
            clock=_clock10,
        )
        escalate._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-10m", "instrument": "MES"}))
        clock10["now"] = T0 + timedelta(seconds=601)
        escalate.tick(clock10["now"])
        if escalate.jobs[0].closed is not True:
            _fail("first 10min miss did not escalate")
        if escalate.jobs[0].retried is True:
            _fail("first 10min miss retried instead of escalate")
        positions6 = LivePositionManager(app=SimpleNamespace())
        positions6.set_strategy_qty("hyp-4", 4)
        submit4 = RecordingSubmitter()
        exe4 = AlarmExecutor(
            bus=EventBus(),
            positions=positions6,
            submitter=submit4,
            jsonl_path=Path(tmp) / "qty4.jsonl",
            clock=lambda: T0,
        )
        exe4._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-4", "instrument": "MES"}))
        if not submit4.orders or submit4.orders[-1].quantity != 2:
            _fail("50% of 4 is not 2")
        n4 = len(submit4.orders)
        exe4.tick(T0)
        if len(submit4.orders) != n4:
            _fail("executed reduce retried on later tick")
        if positions6.strategy_qty("hyp-4") != 2:
            _fail("qty drifted after extra tick")
        done_job = exe4.jobs[0]
        later = T0 + timedelta(seconds=400)
        if exe4._advance(done_job, later) is not None:
            _fail("_advance returned a value after execute")
        if len(submit4.orders) != n4:
            _fail("_advance resubmitted an executed job")
        if exe4._advance(done_job, later) is not None:
            _fail("second _advance returned a value")
        positions7 = LivePositionManager(app=SimpleNamespace())
        positions7.set_strategy_qty("hyp-imm", 2)
        imm = AlarmExecutor(
            bus=EventBus(),
            positions=positions7,
            submitter=RecordingSubmitter(accept=False),
            jsonl_path=Path(tmp) / "imm.jsonl",
            clock=lambda: T0,
        )
        imm_job = AlarmJob(strategy_id="hyp-imm", stage="deweighted", instrument="MES", proposed_at=T0)
        if imm._advance(imm_job, T0) is not None:
            _fail("immediate _advance returned a value")
        clock_r = {"now": T0}

        def _clock_r() -> datetime:
            return clock_r["now"]

        positions8 = LivePositionManager(app=SimpleNamespace())
        positions8.set_strategy_qty("hyp-r", 2)
        retrying = AlarmExecutor(
            bus=EventBus(),
            positions=positions8,
            submitter=RecordingSubmitter(accept=False),
            jsonl_path=Path(tmp) / "retry.jsonl",
            clock=_clock_r,
        )
        retrying._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-r", "instrument": "MES"}))
        clock_r["now"] = T0 + timedelta(seconds=301)
        if retrying._advance(retrying.jobs[0], clock_r["now"]) is not None:
            _fail("retry _advance returned a value")


def _kill_place_block() -> None:
    bind_sim_gate(passing_context())
    allowed, freeze = assert_validation_gate_or_block(
        "supervisor_tick_exec.run_tick_exec",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="research_bridge",
    )
    if allowed is True or freeze != UNGATED_PLACE_BLOCK_REASON:
        _fail("supervisor placed after sim_gate")
    allowed, gate_reason = assert_validation_gate_or_block(
        "ninjatrader.broker.submit_order",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="research_bridge",
    )
    if allowed is not True:
        _fail("research_bridge blocked after sim_gate")
    allowed, reason = assert_validation_gate_or_block(
        "operations_service_orders.place_order",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="operations_service",
    )
    if allowed is True:
        _fail("manual place opened without release")
    bind_sim_gate(None)
    if RESEARCH_SIM_GATED != "research_sim_gated":
        _fail("gated reason renamed")


if __name__ == "__main__":
    run()
