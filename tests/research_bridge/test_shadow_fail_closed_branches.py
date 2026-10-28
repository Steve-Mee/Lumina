"""Remaining SHADOW fail-closed branches: naive clock, fill refuse, handler errors."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.research_bridge.install import attach_shadow_runtime
from lumina_core.research_bridge.jsonl import default_shadow_jsonl_path
from lumina_core.research_bridge.market_health import LOST_CONNECTION, healthy_closed_bar, unhealthy_market
from lumina_research.agents.provenance import ProvenanceAuthority
from tests.research_bridge.helpers import make_runtime, sealed_candidate


class _FlipMarket:
    def __init__(self) -> None:
        self.calls = 0

    def allow_new_intents(self) -> tuple[bool, str]:
        self.calls += 1
        if self.calls == 1:
            return True, "ok"
        return False, LOST_CONNECTION

    def reference_price(self) -> float | None:
        return 5000.0 if self.calls == 1 else None


@pytest.mark.unit
def test_naive_clock_is_stamped_utc(tmp_path: Path) -> None:
    _bus, authority, runtime, _alerts, _observe = make_runtime(tmp_path, healthy=True)
    runtime._clock = lambda: datetime(2026, 10, 28, 12, 0)
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is not None
    assert intent.timestamp.tzinfo is not None
    assert runtime.observe_call_count() == 1


@pytest.mark.unit
def test_fill_refused_after_intent_when_market_flips(tmp_path: Path) -> None:
    _bus, authority, runtime, alerts, observe = make_runtime(tmp_path, healthy=True)
    runtime.replace_market(_FlipMarket())  # type: ignore[arg-type]
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is not None
    assert runtime.issued_fills() == ()
    assert observe.calls == []
    assert any(LOST_CONNECTION in str(item["code"]) for item in alerts.records)
    jsonl = (tmp_path / "research_shadow.jsonl").read_text(encoding="utf-8")
    assert "shadow_fill_refused" in jsonl


@pytest.mark.unit
def test_invalid_cost_inputs_refuse_fill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bus, authority, runtime, alerts, _observe = make_runtime(tmp_path, healthy=True)

    def boom(**_kwargs: object) -> object:
        raise ValueError("reference_price must be a finite number > 0")

    monkeypatch.setattr("lumina_core.research_bridge.shadow_runtime.hypothetical_execution_costs", boom)
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is not None
    assert runtime.issued_fills() == ()
    assert any("invalid_cost_inputs" in str(item["code"]) for item in alerts.records)


@pytest.mark.unit
def test_cost_discrepancy_still_uses_execution_side(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bus, authority, runtime, _alerts, _observe = make_runtime(tmp_path, healthy=True)
    monkeypatch.setattr(
        "lumina_core.research_bridge.costs._research_four_leg_usd",
        lambda **_k: 999.0,
    )
    intent = runtime.on_candidate(sealed_candidate(authority, instrument="MES"))
    assert intent is not None
    fills = runtime.issued_fills()
    assert len(fills) == 1
    assert fills[0].commission == pytest.approx(0.94)


@pytest.mark.unit
def test_assert_no_broker_submit_raises_when_counter_nonzero(tmp_path: Path) -> None:
    _bus, _authority, runtime, _alerts, _observe = make_runtime(tmp_path, healthy=True)
    runtime._broker_submits = 1
    with pytest.raises(AssertionError, match="broker submit"):
        runtime.assert_no_broker_submit()


@pytest.mark.unit
def test_bus_handler_failure_is_refused(tmp_path: Path) -> None:
    bus, _authority, runtime, alerts, _observe = make_runtime(tmp_path, healthy=True)

    def explode(_candidate: object) -> None:
        raise RuntimeError("typed payload exploded")

    runtime.on_candidate = explode  # type: ignore[method-assign]
    runtime._on_bus_candidate(SimpleNamespace())
    assert any(item["code"] == "shadow_candidate_handler_failed" for item in alerts.records)
    assert bus.history("research.execution.signal_intent") == []


@pytest.mark.unit
def test_default_jsonl_path_uses_state_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LUMINA_STATE_DIR", str(tmp_path))
    assert default_shadow_jsonl_path() == tmp_path / "research_shadow.jsonl"


@pytest.mark.unit
def test_fill_without_observe_sink_still_does_not_place(tmp_path: Path) -> None:
    bus = EventBus()
    authority = ProvenanceAuthority()
    runtime = attach_shadow_runtime(
        bus,
        authority=authority,
        jsonl_path=tmp_path / "shadow.jsonl",
        market=healthy_closed_bar(close=5000.0),
        tape_kind="synthetic",
    )
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is not None
    assert len(runtime.issued_fills()) == 1
    assert runtime.observe_call_count() == 0
    runtime.assert_no_broker_submit()


@pytest.mark.unit
def test_direct_shadow_fill_refuses_unhealthy_market(tmp_path: Path) -> None:
    _bus, authority, runtime, alerts, _observe = make_runtime(tmp_path, healthy=True)
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is not None
    runtime.replace_market(unhealthy_market())
    assert runtime.shadow_fill(intent) is None
    assert any(LOST_CONNECTION in str(item["code"]) for item in alerts.records)
