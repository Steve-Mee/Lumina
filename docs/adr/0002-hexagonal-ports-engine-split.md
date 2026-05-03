# ADR-0002: Hexagonal Ports for LuminaEngine Split

**Status**: Accepted

**Date**: 2026-05-03

## Context

`LuminaEngine` was already reduced to a thin orchestrator, but ownership boundaries were still blurred because many call sites and imports continued to depend on modules under `lumina_core/engine/` for risk, audit, evolution, broker, and reasoning capabilities.

This made dependency direction inconsistent with bounded-context rules and kept a service-bag pattern alive via broad engine proxy fields.

## Decision

We introduce a typed hexagonal contract layer and migrate ownership by context:

1. Add `lumina_core/ports/` with runtime-checkable Protocol ports:
   - `RiskPort`, `AuditPort`, `EvolutionPort`, `OrchestrationPort`
   - `BrokerPort`, `MarketDataPort`, `ExecutionPort`, `DreamStatePort`, `ReasoningPort`
2. Add `EngineServicePorts` (Pydantic v2, `extra="forbid"`) as the canonical service ownership registry on `LuminaEngine`.
3. Wire `engine.services_ports` in `ApplicationContainer` after dependency construction.
4. Move canonical import ownership to bounded contexts:
   - `lumina_core/evolution/*` for meta-agent modules
   - `lumina_core/audit/*` for decision/audit services
   - `lumina_core/risk/*` for session/regime/policy ownership
   - `lumina_core/broker/*` and `lumina_core/reasoning/*` as dedicated contexts
5. Keep an `experimental` slot on `EngineServicePorts` for emergent capabilities without modifying `LuminaEngine`.

## Consequences

- Positief:
  - Ownership per capability is explicit and type-checked.
  - `LuminaEngine` remains a coordinator instead of a god-object.
  - New experimental layers can be attached without widening engine API surface.
- Negatief:
  - Short-term migration overhead from import path changes.
  - Transitional wrappers remain until full file-by-file canonical relocation is completed.
- Risico's:
  - Runtime import regressions in older tests/callers if migration coverage is incomplete.
  - Safety-critical paths (risk/broker/reasoning) require strict fail-closed regression checks.

## Rollback Plan

If a migration step causes instability:

1. Re-point failing imports to previous canonical module path.
2. Keep `services_ports` active but set optional ports (`reasoning`, `evolution`) to `None`.
3. Re-run safety-gate tests (`risk transparency`, `order path regression`, `reasoning gateway`) before re-attempting.

## Alternatives Considered

- Keep `EngineServices` only and avoid typed ports:
  - Rejected because ownership remains implicit and easy to regress.
- Big-bang move without protocol layer:
  - Rejected due to high blast radius and weak compile-time guidance.

## Related ADRs

- `docs/adr/0001-bounded-contexts-central-event-bus.md`
- `docs/adr/0002-shadow-deployment-human-approval.md`
- `docs/adr/0008-lumina-engine-service-decomposition.md`
- `docs/adr/0009-thin-engine-orchestrator-and-app-shim-removal.md`
