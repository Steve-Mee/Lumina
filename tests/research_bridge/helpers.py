"""Shared SHADOW test helpers. Synthetic tape only."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import PromotionCandidate
from lumina_core.research_bridge.alerts import RecordingAlertSink
from lumina_core.research_bridge.market_health import healthy_closed_bar, unhealthy_market
from lumina_core.research_bridge.shadow_runtime import ShadowRuntime
from lumina_research.agents.provenance import ProvenanceAuthority

_HEX = "a" * 64


class RecordingObserveSink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def observe(self, signal_id: str, metric: object) -> object:
        self.calls.append((signal_id, metric))
        return metric


def unsigned_candidate_fields(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "research.promotion.candidate.v1",
        "hypothesis_id": "hyp-s0",
        "config_id": "cfg-s0",
        "trial_id": 1,
        "agent_id": "promotion_agent",
        "instrument": "MES",
        "direction": "BUY",
        "decision_kind": "approved",
        "scaled": False,
        "quantity": 1.0,
        "notional": 5000.0,
        "risk_reason": "approved",
        "expected_horizon_bars": 8,
        "validation_report_sha256": _HEX,
        "validation_mac": _HEX,
    }
    body.update(overrides)
    return body


def sealed_candidate(authority: ProvenanceAuthority, **overrides: object) -> PromotionCandidate:
    unsigned = unsigned_candidate_fields(**overrides)
    mac = authority.seal_issue(unsigned)
    return PromotionCandidate.model_validate({**unsigned, "issue_mac": mac})


def make_runtime(
    tmp_path: Path,
    *,
    healthy: bool = True,
    close: float = 5000.0,
    tape_kind: str = "synthetic",
) -> tuple[EventBus, ProvenanceAuthority, ShadowRuntime, RecordingAlertSink, RecordingObserveSink]:
    bus = EventBus()
    authority = ProvenanceAuthority()
    alerts = RecordingAlertSink()
    observe = RecordingObserveSink()
    market = healthy_closed_bar(close=close) if healthy else unhealthy_market()
    runtime = ShadowRuntime(
        bus=bus,
        authority=authority,
        jsonl_path=tmp_path / "research_shadow.jsonl",
        market=market,
        tape_kind="synthetic" if tape_kind == "synthetic" else "nt_pit",
        observe_sink=observe,
        alert_sink=alerts,
        clock=lambda: datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
    )
    return bus, authority, runtime, alerts, observe
