"""Attach the KEEP ResearchBridge to an Event Bus. Fail-closed market by default."""

from __future__ import annotations

from pathlib import Path

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.research_bridge.alerts import AlertSink
from lumina_core.research_bridge.jsonl import default_shadow_jsonl_path
from lumina_core.research_bridge.market_health import MarketHealth, unhealthy_market
from lumina_core.research_bridge.fill_index import FillIndex
from lumina_core.research_bridge.shadow_runtime import ObserveSink, ShadowRuntime, TapeKind
from lumina_core.research_bridge.sim_gate import SimGateContext, bind_sim_gate
from lumina_core.research_bridge.sim_runtime import SimRuntime, SimSubmitter
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


def attach_sim_runtime(
    bus: EventBus,
    *,
    gate_ctx: SimGateContext,
    fill_index: FillIndex | None = None,
    authority: ProvenanceAuthority | None = None,
    jsonl_path: Path | None = None,
    market: MarketHealth | None = None,
    engine: object | None = None,
    submitter: SimSubmitter | None = None,
    alert_sink: AlertSink | None = None,
) -> SimRuntime:
    """S3 gated SIM runtime. Binds boot-time sim_gate evidence (not hot-reload yaml)."""
    bind_sim_gate(gate_ctx)
    return SimRuntime(
        bus=bus,
        authority=authority if authority is not None else ProvenanceAuthority(),
        jsonl_path=jsonl_path if jsonl_path is not None else default_shadow_jsonl_path(),
        market=market if market is not None else unhealthy_market(),
        fill_index=fill_index if fill_index is not None else FillIndex(),
        gate_ctx=gate_ctx,
        engine=engine,
        submitter=submitter,
        alert_sink=alert_sink,
    )
