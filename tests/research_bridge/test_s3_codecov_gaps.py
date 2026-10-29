"""Cover remaining S3 fail-closed branches (patch coverage)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.independence import independent_set, pairwise_correlation
from lumina_core.research_bridge.market_health import healthy_closed_bar
from lumina_core.research_bridge.sim_gate import (
    LoggedHumanRelease,
    SimGateRefused,
    arm_research_place,
    bind_logged_human_release,
    bind_sim_gate,
    bound_context,
    evaluate,
    logged_human_release,
    non_research_release_allows,
    supervisor_source_blocked,
)
from lumina_core.research_bridge.sim_runtime import SimRuntime
from lumina_core.risk.alarm_executor import AlarmExecutor
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.validation.nt_tape import (
    NtTapeMaterializer,
    TapeRefused,
    closed_bars_from_frame,
    closed_bars_from_manager,
    closed_bars_from_rows,
    fixture_closed_mes_bars,
    materializer_from_rows,
    refuse_vendor_csv_substitute,
    series_from_closed_bars,
)
from tests.research_bridge.helpers import sealed_candidate, unsigned_candidate_fields
from tests.research_bridge.s3_helpers import RecordingSubmitter, fake_engine, passing_context, survivor

UTC = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    bind_logged_human_release(None)
    yield
    bind_sim_gate(None)
    bind_logged_human_release(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_independence_fail_closed_series() -> None:
    assert pairwise_correlation("nope", (0.1,) * 8)[1] == "survivors_corr_unavailable"
    assert pairwise_correlation((0.1,) * 3, (0.2,) * 3)[1] == "survivors_corr_unavailable"
    assert pairwise_correlation((1.0,) * 8, (1.0,) * 8)[1] == "survivors_corr_unavailable"
    assert pairwise_correlation((float("nan"),) * 8, (0.1,) * 8)[1] == "survivors_corr_unavailable"
    chosen, reason = independent_set((survivor(tag="only", family="trend"),))
    assert chosen == ()
    assert reason == "survivors_insufficient"


@pytest.mark.unit
@pytest.mark.safety_gate
def test_sim_gate_residual_rejects() -> None:
    assert bound_context() is None
    assert logged_human_release() is None
    assert supervisor_source_blocked("") is False
    assert supervisor_source_blocked("   ") is False
    with pytest.raises(SimGateRefused):
        with arm_research_place(passing_context(boot="shadow")):
            pass
    ok, reason = evaluate(passing_context(market=False))
    assert ok is False
    assert reason == "research_sim_gated"
    ok, reason = evaluate(passing_context(connected=""))
    assert ok is False
    ok, reason = evaluate(passing_context(trade_mode="paper"))
    assert ok is False
    ok, reason = evaluate(passing_context(survivors=(replace(survivor(tag="a", family="trend"), stage="retired"), survivor(tag="b", family="meanrev"))))
    assert ok is False
    ok, reason = evaluate(
        passing_context(
            survivors=(
                replace(survivor(tag="a", family="trend"), passed_validation_gate=False),
                survivor(tag="b", family="meanrev"),
            )
        )
    )
    assert ok is False
    ok, reason = evaluate(
        passing_context(
            survivors=(
                replace(survivor(tag="a", family="trend"), expected_horizon_bars=0),
                survivor(tag="b", family="meanrev"),
            )
        )
    )
    assert ok is False
    ok, reason = evaluate(
        passing_context(
            survivors=(
                replace(survivor(tag="a", family="trend"), fill_history_bars=2),
                survivor(tag="b", family="meanrev"),
            )
        )
    )
    assert ok is False
    ok, reason = evaluate(
        passing_context(
            survivors=(
                replace(survivor(tag="a", family="trend"), validation_mac="short"),
                survivor(tag="b", family="meanrev"),
            )
        )
    )
    assert ok is False
    ok, reason = evaluate(passing_context(meter=float("nan")))
    assert ok is False
    ok, reason = evaluate(passing_context(hmac_ok=False))
    assert ok is False
    ok, reason = evaluate(passing_context(approval_required=False))
    assert ok is False
    ok, reason = evaluate(passing_context(approval_present=False))
    assert ok is False
    assert non_research_release_allows("supervisor_tick_exec") is False
    assert non_research_release_allows("operations_service_orders.place_order") is False
    bind_logged_human_release(LoggedHumanRelease(adr_path="docs/adr/0063-sim-orders-gated.md", approved_by="a", purpose="manual_place"))
    assert non_research_release_allows("operations_service_orders.place_order") is False
    bind_logged_human_release(LoggedHumanRelease(adr_path="docs/adr/0063-sim-orders-gated.md", approved_by="research_ops", purpose="manual_place"))
    assert non_research_release_allows("operations_service_orders.place_order") is False
    bind_logged_human_release(LoggedHumanRelease(adr_path="not-adr.md", approved_by="steve", purpose="manual_place"))
    assert non_research_release_allows("operations_service_orders.place_order") is False
    bind_logged_human_release(LoggedHumanRelease(adr_path="docs/adr/0063-sim-orders-gated.md", approved_by="steve", purpose="live"))
    assert non_research_release_allows("operations_service_orders.place_order") is False


@pytest.mark.unit
@pytest.mark.safety_gate
def test_sim_runtime_refuses_forged_missing_submitter_and_qty(tmp_path: Path) -> None:
    ctx = passing_context()
    bind_sim_gate(ctx)
    runtime = SimRuntime(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        jsonl_path=tmp_path / "s3.jsonl",
        market=healthy_closed_bar(close=5000.0),
        fill_index=FillIndex(),
        gate_ctx=ctx,
        engine=fake_engine(),
        submitter=RecordingSubmitter(),
    )
    bad = type(sealed_candidate(runtime._authority)).model_validate(
        {**unsigned_candidate_fields(), "issue_mac": "0" * 64}
    )
    assert runtime.on_candidate(bad) is None
    missing = SimRuntime(
        bus=EventBus(),
        authority=ProvenanceAuthority(),
        jsonl_path=tmp_path / "s3b.jsonl",
        market=healthy_closed_bar(close=5000.0),
        fill_index=FillIndex(),
        gate_ctx=ctx,
        engine=None,
        submitter=None,
    )
    assert missing.on_candidate(sealed_candidate(missing._authority)) is None
    zero = sealed_candidate(runtime._authority, quantity=0.4)
    assert runtime.on_candidate(zero) is None
    _ = runtime.issued_intents()
    _ = runtime.submitted_orders()
    _ = runtime.broker_submit_count()


@pytest.mark.unit
@pytest.mark.safety_gate
def test_alarm_executor_skips_missing_strategy_and_flat(tmp_path: Path) -> None:
    positions = LivePositionManager(app=SimpleNamespace())
    exe = AlarmExecutor(
        bus=EventBus(),
        positions=positions,
        submitter=RecordingSubmitter(),
        jsonl_path=tmp_path / "alarm.jsonl",
    )
    exe.install()
    exe._on_deweight(SimpleNamespace(payload={"instrument": "MES"}))
    exe.tick()
    positions.set_strategy_qty("hyp-flat", 0)
    exe._on_deweight(SimpleNamespace(payload={"hypothesis_id": "hyp-flat", "instrument": "MES"}))
    log = (tmp_path / "alarm.jsonl").read_text(encoding="utf-8")
    assert "strategy_id_missing" in log
    assert "already_flat" in log or "skip_flat" in log


@pytest.mark.unit
@pytest.mark.safety_gate
def test_nt_tape_refuse_branches() -> None:
    with pytest.raises(TapeRefused, match="timestamp_missing"):
        closed_bars_from_rows([{"open": 1}], now=UTC, purpose="gate")
    with pytest.raises(TapeRefused, match="bar_not_mapping"):
        closed_bars_from_rows(["nope"], now=UTC, purpose="gate")
    with pytest.raises(TapeRefused, match="unknown_tape_purpose"):
        closed_bars_from_rows(fixture_closed_mes_bars(now=UTC), now=UTC, purpose="tuning_live")
    with pytest.raises(TapeRefused, match="tape_too_short"):
        closed_bars_from_rows(fixture_closed_mes_bars(now=UTC)[:10], now=UTC, purpose="gate")
    with pytest.raises(TapeRefused, match="closed_book_empty"):
        closed_bars_from_frame(None, now=UTC)
    with pytest.raises(TapeRefused, match="closed_book_empty"):
        closed_bars_from_frame(SimpleNamespace(empty=True), now=UTC)
    rows = fixture_closed_mes_bars(now=UTC)

    class _Frame:
        empty = False

        def to_dict(self, orient: str) -> list[dict[str, object]]:
            del orient
            return list(rows)

    bars = closed_bars_from_frame(_Frame(), now=UTC, purpose="gate")
    assert len(bars) >= 241
    with pytest.raises(TapeRefused):
        closed_bars_from_manager(SimpleNamespace(ohlc_1min=None), now=UTC)
    refuse_vendor_csv_substitute("")
    with pytest.raises(TapeRefused, match="vendor_csv_substitute"):
        refuse_vendor_csv_substitute("planted_edge.csv")
    with pytest.raises(TapeRefused, match="nt_tape_subclass_forbidden"):

        class _Sub(NtTapeMaterializer):
            pass

        _Sub(bars)
    with pytest.raises(TapeRefused, match="tape_too_short"):
        NtTapeMaterializer(bars[:2])
    with pytest.raises(TapeRefused, match="tape_too_short"):
        fixture_closed_mes_bars(n=10, now=UTC)
    with pytest.raises(TapeRefused, match="holdout_pin_closed"):
        fixture_closed_mes_bars(start=datetime(2026, 2, 1, tzinfo=timezone.utc), now=UTC)
    series_from_closed_bars(bars)
    materializer_from_rows(rows, now=UTC, purpose="gate")
