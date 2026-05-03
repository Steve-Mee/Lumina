# ADR-0009: Thin Engine orchestrator en verwijdering van app-shim

**Status**: Accepted

**Date**: 2026-05-03

## Context

Na ADR-0008 bleef `LuminaEngine` nog te veel mixed responsibilities dragen: state snapshot-opbouw, state persistence, operationele counters en een legacy `__getattr__/__setattr__` app-shim.

Dat botst met:

- de bounded-context discipline uit ADR-0001,
- de LUMINA missie (extreme intellectual honesty, rigoureuze testing, radicale creativiteit),
- en het Elon Musk Mindset Protocol (radicale eenvoud zonder safety-regressies).

Vooral de app-shim was risicovol: impliciete fallback naar `engine.app.*` verbergt ownership en maakt refactors foutgevoelig.

## Decision

We maken `LuminaEngine` expliciet dunner als orchestrator door:

- `EngineSnapshotService` te introduceren voor deterministische state snapshots.
- `EngineStatePersistenceService` te introduceren voor `hydrate_from_legacy`, `save_state`, `load_state`.
- `RuntimeCounters` te introduceren als eigenaar van operationele counters.
- `EngineServices` te introduceren als typed registry voor optionele container-ingespoten handles.
- `engine_state_facade.py` te introduceren voor declaratieve state/service property-proxies, zodat compat-API compact blijft.
- Legacy `__getattr__/__setattr__` app-shim te verwijderen.

Daarnaast definiëren we expliciete velden voor margin/snapshot-status op engine-account-state (`available_margin`, `positions_margin_used`, `equity_snapshot_ok`, `equity_snapshot_reason`, `admission_chain_final_arbitration_approved`) zodat REAL-paths fail-closed en transparant blijven.

## Consequences

- Positief:
  - Heldere ownership per capability; minder god-object gedrag.
  - `LuminaEngine` blijft compact (<= 350 regels) met expliciete orchestrator-rol.
  - Betere testbaarheid van snapshots/persistence/counters als losse eenheden.
  - Minder impliciete runtime-magie door verwijderen van app-shim.
  - Meer flexibiliteit om experimentele lagen toe te voegen via `EngineServices` zonder engine-kern te vervuilen.
- Negatief:
  - Meer modules en meer container-wiring.
  - Eenmalige migratiekost voor callsites die nog op shim-gedrag steunden.
- Risico's:
  - Regressie in REAL orderflow bij verkeerde field-mapping.
  - Import-cycles tussen `engine/` en `trading_engine/` als lazy imports niet bewaakt blijven.

## Alternatives Considered

- Optie A: Shim behouden met alleen warnings.
  - Afgewezen: blijft implicit fallback toestaan en vertraagt ownership-cleanup.
- Optie B: Volledige big-bang rewrite van `LuminaEngine`.
  - Afgewezen: te hoog regressierisico voor REAL-gates en te groot in één iteratie.

## Related ADRs

- ADR-0001: Bounded contexts central event bus
- ADR-0007: Promotion gate real mode
- ADR-0008: LuminaEngine service decomposition
