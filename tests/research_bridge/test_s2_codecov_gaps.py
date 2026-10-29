"""Cover remaining S2 fail-closed patch lines (Codecov 30-line residual)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("grpc")

from lumina_core.broker.ninjatrader import fabric_mapper as mapper
from lumina_core.broker.ninjatrader.generated import fabric_pb2
from lumina_core.engine.trade_reconciler.fill_normalization_mixin import FillNormalizationMixin
from lumina_core.research_bridge import calibrator_rows as rows_mod
from lumina_core.research_bridge import fill_stamp as stamp_mod
from lumina_core.research_bridge.binding_policy import (
    BindingPolicyRefused,
    independent,
    reduce_qty,
    sla_decision,
)
from lumina_core.research_bridge.calibrator_rows import (
    CalibratorRowRefused,
    event_ts_now,
    live_calibrator_row,
    root_of_symbol,
)
from lumina_core.research_bridge.fill_index import FillIndexEntry
from lumina_core.research_bridge.fill_stamp import FillStampRefused, stamp_slippage
from lumina_core.research_bridge.fill_translator import TranslateRefused, observe_metric
from lumina_core.risk.cost_model import TradeExecutionCostModel
from lumina_core.risk.cost_model_calibrator import (
    compute_exit_leg_costs,
    row_instrument_root,
    run_daily_calibration,
)
from tests.research_bridge.s2_helpers import broker_fill, make_translator


@pytest.mark.unit
@pytest.mark.safety_gate
def test_hold_side_mapped_fill_is_not_published(tmp_path: Path) -> None:
    translator, _observe, _index, bus = make_translator(tmp_path, with_bus=True)
    assert bus is not None
    result = translator.ingest(broker_fill(side="HOLD"), client_order_id="cid-1")
    assert result.published is False
    assert result.calibrated is True
    text = (tmp_path / "s2_refuse.jsonl").read_text(encoding="utf-8")
    assert "side_invalid" in text


@pytest.mark.unit
def test_publish_refuses_zero_horizon_mapped_entry(tmp_path: Path) -> None:
    translator, _observe, _index, _bus = make_translator(tmp_path, with_bus=True)
    published = translator._maybe_publish(
        broker_fill(),
        FillIndexEntry(strategy_id="hyp-s2", expected_horizon=0),
    )
    assert published is False
    assert "expected_horizon_missing" in (tmp_path / "s2_refuse.jsonl").read_text(encoding="utf-8")


@pytest.mark.unit
def test_observe_metric_non_finite_refused() -> None:
    fill = broker_fill(slippage_usd=float("inf"))
    with pytest.raises(TranslateRefused, match="observe_metric_non_finite"):
        observe_metric(fill)


@pytest.mark.unit
def test_client_order_id_falls_back_to_fill_id(tmp_path: Path) -> None:
    translator, observe, index, _bus = make_translator(tmp_path, remember=("fill-mes-1", "hyp-s2", 8))
    fill = broker_fill()
    fill.raw_payload = {}
    result = translator.ingest(fill, client_order_id="")
    assert result.observed is True
    assert observe.calls[0][0] == "hyp-s2"
    assert index.lookup("fill-mes-1") is not None


@pytest.mark.unit
def test_row_numeric_and_timestamp_fail_closed(tmp_path: Path) -> None:
    translator, _o, _i, _b = make_translator(tmp_path)
    with pytest.raises(TranslateRefused, match="row_numeric_invalid"):
        translator.ingest(
            {
                "symbol": "MES",
                "side": "BUY",
                "qty": "x",
                "fill_price": 5000.0,
                "source": "broker",
                "ts": "2026-10-29T12:00:00+00:00",
            }
        )
    with pytest.raises(TranslateRefused, match="timestamp_invalid"):
        translator.ingest(
            {
                "symbol": "MES",
                "side": "BUY",
                "qty": 1,
                "fill_price": 5000.0,
                "source": "broker",
                "ts": "not-a-timestamp",
            }
        )


@pytest.mark.unit
@pytest.mark.safety_gate
def test_stamp_slippage_unknown_root_and_zero_tick() -> None:
    with pytest.raises(FillStampRefused, match="root_not_on_card"):
        stamp_slippage(symbol="NOTAROOT", side="BUY", fill_price=5000.0, reference_price=5000.0, qty=1)
    orig = stamp_mod.spec_for

    class _ZeroTick:
        tick_size = 0.0
        point_value_usd = 5.0

    stamp_mod.spec_for = lambda symbol: _ZeroTick()  # type: ignore[assignment]
    try:
        with pytest.raises(FillStampRefused, match="tick_value_invalid"):
            stamp_slippage(symbol="MES", side="BUY", fill_price=5000.0, reference_price=5000.0, qty=1)
    finally:
        stamp_mod.spec_for = orig


@pytest.mark.unit
@pytest.mark.safety_gate
def test_binding_policy_refuse_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(BindingPolicyRefused, match="elapsed_invalid"):
        sla_decision(1, True)  # type: ignore[arg-type]
    nan_ok, nan_why = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=float("nan"),
    )
    assert nan_ok is False
    assert nan_why == "survivors_corr_unavailable"
    bool_ok, bool_why = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=True,  # type: ignore[arg-type]
    )
    assert bool_ok is False
    assert bool_why == "survivors_corr_unavailable"
    out_ok, out_why = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=1.5,
    )
    assert out_ok is False
    assert out_why == "survivors_corr_unavailable"
    monkeypatch.setattr("lumina_core.research_bridge.binding_policy.SUSPEND_REDUCE_FRACTION", 2.0)
    with pytest.raises(BindingPolicyRefused, match="reduce_qty_not_partial"):
        reduce_qty("suspended", 2)


@pytest.mark.unit
def test_calibrator_row_qty_zero_and_unknown_after_normalize() -> None:
    with pytest.raises(CalibratorRowRefused, match="qty_invalid"):
        live_calibrator_row(broker_fill(quantity=0))
    now = event_ts_now()
    assert now.tzinfo is not None
    orig = rows_mod.normalize_fill_source
    rows_mod.normalize_fill_source = lambda value: "other"  # type: ignore[assignment]
    try:
        with pytest.raises(CalibratorRowRefused, match="unknown_fill_source"):
            live_calibrator_row(broker_fill())
    finally:
        rows_mod.normalize_fill_source = orig
    with pytest.raises(CalibratorRowRefused):
        root_of_symbol("NOTAROOT")


@pytest.mark.unit
def test_live_calibrator_skips_unknown_root_and_uses_ticks(tmp_path: Path) -> None:
    assert row_instrument_root({"symbol": "NOTAROOT"}) is None
    model = TradeExecutionCostModel.from_config({}, instrument="MES")
    real_usd, _model_usd, tick_value = compute_exit_leg_costs(
        {
            "symbol": "MES",
            "qty": 1,
            "commission": 0.94,
            "slippage_ticks": 1.0,
            "fill_price": 5000.0,
        },
        model,
    )
    assert tick_value == pytest.approx(1.25)
    assert real_usd == pytest.approx(0.94 + 1.25)
    audit = tmp_path / "audit.jsonl"
    audit.write_text(
        '{"event":"reconciled","ts":"2026-05-01T10:00:00+00:00","symbol":"NOTAROOT","quantity":1,'
        '"commission":0.94,"slippage_usd":1.25,"source":"broker"}\n',
        encoding="utf-8",
    )
    bogus = run_daily_calibration(
        audit_path=audit,
        state_path=tmp_path / "bogus.json",
        instrument="NOTAROOT",
    )
    assert bogus.sample_count == 0
    skipped = run_daily_calibration(
        audit_path=audit,
        state_path=tmp_path / "mes.json",
        instrument="MES",
    )
    assert skipped.sample_count == 0


@pytest.mark.unit
def test_mapper_invalid_reference_does_not_invent_fill() -> None:
    event = fabric_pb2.OrderEvent(
        client_order_id="c1",
        nt_order_id="nt1",
        state=fabric_pb2.ORDER_STATE_FILLED,
        filled_qty=1,
        avg_fill_price=5000.0,
        instrument="MES",
        action=fabric_pb2.ORDER_ACTION_BUY,
        timestamp_unix_ms=1_700_000_000_000,
    )
    assert mapper.order_event_to_fill(event, reference_price=0.0) is None
    unknown_side = fabric_pb2.OrderEvent(
        client_order_id="c1",
        nt_order_id="nt1",
        state=fabric_pb2.ORDER_STATE_FILLED,
        filled_qty=1,
        avg_fill_price=5000.0,
        instrument="MES",
        action=fabric_pb2.ORDER_ACTION_UNSPECIFIED,
        timestamp_unix_ms=1_700_000_000_000,
    )
    assert mapper.order_event_to_fill(unknown_side, reference_price=5000.0) is None


@pytest.mark.unit
def test_normalize_fill_event_copies_ssot_fields_and_refuses_bad_horizon() -> None:
    fill = FillNormalizationMixin._normalize_fill_event(
        {
            "type": "fill",
            "symbol": "MES",
            "quantity": 1,
            "fillPrice": 5000.25,
            "side": "BUY",
            "commission": 0.94,
            "slippage_ticks": 1.0,
            "slippage_usd": 1.25,
            "commission_ticks": 0.752,
            "source": "broker",
            "strategy_id": "hyp-s2",
            "expected_horizon": "nope",
        }
    )
    assert fill is not None
    assert fill.slippage_ticks == pytest.approx(1.0)
    assert fill.slippage_usd == pytest.approx(1.25)
    assert fill.strategy_id == "hyp-s2"
    assert fill.expected_horizon == 0
    assert fill.source == "broker"
