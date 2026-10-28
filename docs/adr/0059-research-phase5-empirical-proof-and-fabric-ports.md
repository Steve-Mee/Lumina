# ADR-0059: Research Phase 5 empirical proof and Execution Fabric ports (no NT8 coupling)

**Status:** Accepted  
**Date:** 2026-10-28  
**Deciders:** LUMINA Engineering

## Context

Phases 1–4 put a fail-closed Validation Gate, a propose-only research factory, bounded self-evolution, and live-vs-OOS decay monitoring in `lumina_research/`. Steve's Phase 5 goal is empirical proof of that stack (independent generators, economic templates on real data, guardian/weekly floors) plus a written SIM plan.

A separate 2026-10-28 note from the plan authors describes how this layer will later sit next to the existing program: Event Bus / ports into the Execution Fabric (gRPC), not a rewrite. This ADR records that alignment. **This PR does not implement NT8 coupling and does not place SIM or live orders.**

First principles:

- Capital preservation stays outside the evolutionary path. The live Risk Core (`lumina_core/risk/`), the packaged research Risk Core, gate floors, NT8 AddOn, Fabric proto, data ingest, and order state machine are not research parameters.
- Truth-seeking: independent seeds and processes, not the Phase 4 tuning set. Real market data or a documented stop — never a fabricated tape.
- Adaptation rate only counts if the Validation Gate still kills noise and monitoring still meets Steve's floors.
- Extreme intellectual honesty, rigorous testing, and radical creativity: shadow-log signals; do not open a skip-gate path through gRPC, SIM, or LIVE_RELEASE.

This supports the mission: a self-evolving research loop that remains fail-closed when it later touches the Fabric.

## Decision

### Separate layer, no rewrite

- `lumina_research/` stays a bounded context beside the existing program. Integration is additive Event Bus topics and research-side ports.
- Keep: NT8 AddOn / Execution Fabric (`protos/lumina/execution/v1/fabric.proto`, ADR-0035/0040), live Risk Core, data ingest, order state machine, typed contracts.
- Isolate `archive/birth-v1/` and any birth/evolution path that would skip the Validation Gate. Isolation tests fail closed on those imports. Phase 3 `lumina_research/evolution/` remains propose-only through the Phase 2 event flow.

### Research-side Fabric ports (interfaces only)

Coupling, when it is implemented in a later ADR, goes through the existing Execution Fabric. Phase 5 types the research-side messages and refuses the wire:

| Research contract | Topic | Later Fabric mapping |
|---|---|---|
| `SignalIntent` | `research.signal.intent` | strategy intent before admission |
| `ResearchOrderIntent` | `research.order.intent` | `PlaceOrderCommand` (not `lumina_core.risk.schemas.OrderIntent`) |
| `ResearchFillEvent` | `research.fill.observed` | `OrderEvent` FILLED → fill SSOT |
| `ExecutionAlert` | `research.execution.alert` | fail-closed / SafetyAlert |

Required intent fields: `strategy_id`, `direction`, `size`, `timestamp`, `expected_horizon`. Required fill fields: `fill_price`, `qty`, `slippage`, `commission`. `FillSink` is the one source of truth for decay monitoring and cost calibration. Phase 5 accepts `source=cost_model` hypotheticals only. `source=fabric` and `connect_fabric()` raise `PortRefused`.

HMAC-guarded producers: `research_shadow_agent`, `research_fill_agent`, `research_sim_safety_agent`. Rogue producers cannot publish.

### Shadow first, then SIM, then live

1. **Shadow (this PR, allowed in Fase 5):** log `SignalIntent` / `ResearchOrderIntent`; hypothetical fills via `CostModel`; **no orders**.
2. **Real SIM orders:** only after ≥2–3 independent Validation Gate survivors and the empirical thresholds in the P3 plan (`lumina_research/cycles/sim_plan.py`). Not started here.
3. **Live:** requires a **manual, logged `LIVE_RELEASE` plus a dedicated ADR**. Packaged Phase 5 config is `live_release=False`, `allowed_modes={shadow}`, empty SIM whitelist. Constructors refuse any weakening. Research agents cannot mutate this config. Tests prove there is no bypass.

The live Risk Core remains the future enforcement point for the SIM whitelist and LIVE_RELEASE. This PR does not write `lumina_core/risk/`. The research-side `SimSafetyGate` is the typed contract those checks must match. Any account not on the explicit SIM whitelist is refused; live is refused without LIVE_RELEASE.

### Fail-closed

| Condition | New orders | Position | Full close |
|---|---|---|---|
| Stale data or lost connection | refused | server-side stops / protect; broker is SoT; reconcile on reconnect | no |
| Monitor alarm with open position | refused | de-weight / reduce | no |
| Hard Risk Core limit | refused | flatten **recommended** only | research never sends flatten |

Everything is logged and alerted (`ExecutionAlert`). `ShadowBook.place_order` / `submit_order` / `flatten` / `connect_fabric` raise `PortRefused`.

### Empirical proof (P1, P2, P4, P5 costs)

- **P1:** independent verification suite (`lumina_research/proof/`). Phase 1 gate must kill overfit/noise and may pass a planted healthy tape. Phase 4 floors stay frozen in `acceptance.py`. Additive two-horizon reporting: short TTD ≤ 15 trading days; medium/slow 30–60 day ramps TTD ≤ 45 (target 40). FAR ≤ 5% normal / ≤ 10% high-vol hard cap (12% is not a pass). Detection ≥ 85%. Independent seeds disjoint from Phase 4.
- **P2:** 12 registered economic templates, 24 pre-registered variants. No free-form LLM generation. Real ES/NQ/MES/MNQ data or a graceful stop that documents data requirements. Kill-rate >90% is a diagnostic, not a hard gate.
- **P4:** daily Guardian asserts Risk Core hash untouched, sealed gate passage on active signals, and mutation kill rate ≥ 0.80. Weekly metrics: hypothesis kill/survive, FAR/TTD by horizon, capital-preservation violations (must be 0).
- **P5 costs:** existing four-leg `CostModel`; briefed bands ES/NQ 0.5–1.5 ticks, MES/MNQ 1–2.5 ticks (reporting, not gate floors). Limit fills: trade-through + volume. SIM plan written, not started.

If a floor fails, tune only the detector. Do not loosen gate floors or Risk Core.

## Consequences

### Positive

- Research can prove itself without touching capital paths.
- Later NT8 coupling has a typed, HMAC-guarded port instead of an ad-hoc rewrite.
- SIM/LIVE_RELEASE cannot be flipped by a research agent.

### Negative

- Shadow hypothetical fills are not broker fills. Cost calibration stays conservative until SIM exists.
- Real-data P2 stops until ES/NQ/MES/MNQ bars are on disk. That is honest, not a skip.

## Alternatives considered

1. Implement NT8/gRPC coupling in this PR — rejected: plan authors forbade it; no orders.
2. Rewrite Brain/Fabric around `lumina_research` — rejected: keep the existing program; ports only.
3. Reuse `lumina_core.risk.schemas.OrderIntent` as the research intent — rejected: that contract is Final Arbitration; research intents are additive and must not look like a live order.
4. Let research agents expand the SIM whitelist or set LIVE_RELEASE in config — rejected: no bypass.
5. Monitor alarm → flatten — rejected: full close only on a hard Risk Core limit.
6. Fabricate synthetic tapes when real data is missing — rejected: RESEARCH_CHARTER / intellectual honesty.
7. Reuse `archive/birth-v1/` for P2 hypotheses — rejected: skip-gate isolation.

## Links

- Charter: `RESEARCH_CHARTER.md`
- Fabric: `docs/adr/0035-execution-fabric-grpc.md`, `docs/adr/0040-fabric-only-foundation-and-sentinel.md`
- Phase 4 floors: `docs/adr/0058-research-continuity-live-monitoring.md`
- Phase 3 bounds: `docs/adr/0057-research-self-evolution-within-bounds.md`
- Ports: `lumina_research/ports/`, `lumina_core/agent_orchestration/schemas_research_ports.py`
- Proof CLI: `python -m lumina_research.proof verify|research|weekly`
