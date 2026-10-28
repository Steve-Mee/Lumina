"""Attach the KEEP ResearchBridge to an Event Bus. Fail-closed market by default."""

from __future__ import annotations

from pathlib import Path

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.research_bridge.alerts import AlertSink
from lumina_core.research_bridge.jsonl import default_shadow_jsonl_path
from lumina_core.research_bridge.market_health import MarketHealth, unhealthy_market
from lumina_core.research_bridge.shadow_runtime import ObserveSink, ShadowRuntime, TapeKind
from lumina_research.agents.provenance import ProvenanceAuthority


def attach_shadow_runtime(
    bus: EventBus,
    *,
    authority: ProvenanceAuthority | None = None,
    jsonl_path: Path | None = None,
    market: MarketHealth | None = None,
    tape_kind: TapeKind = "nt_pit",
    observe_sink: ObserveSink | None = None,
    alert_sink: AlertSink | None = None,
) -> ShadowRuntime:
    """Subscribe to sealed PromotionCandidates. Default market is unhealthy (no intents)."""
    return ShadowRuntime(
        bus=bus,
        authority=authority if authority is not None else ProvenanceAuthority(),
        jsonl_path=jsonl_path if jsonl_path is not None else default_shadow_jsonl_path(),
        market=market if market is not None else unhealthy_market(),
        tape_kind=tape_kind,
        observe_sink=observe_sink,
        alert_sink=alert_sink,
    )
