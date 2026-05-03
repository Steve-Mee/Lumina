# ADR-0008: LuminaEngine service decomposition

**Status**: Accepted

**Date**: 2026-05-02

## Context

`LuminaEngine` groeide uit tot een brede klasse met gemengde verantwoordelijkheden: dream-state updates, technical analysis, risk sizing/orchestration en RL execution-routing. Deze concentratie verhoogde regressierisico, maakte unit-testing zwaarder en stond haaks op de bounded-context principes.

Daarnaast bestond al een `MarketDataService` voor websocket/historical ingest, terwijl we ook een domeinservice voor market-data analyse nodig hebben binnen de engine-laag.

## Decision

We splitsen de engine-verantwoordelijkheden in expliciete services met compatibele façade-methodes op `LuminaEngine`:

- `DreamStateManager`
- `MarketDataService` (domain helpers)
- `TechnicalAnalysisService`
- `RiskOrchestrator`
- `ExecutionService`

`LuminaEngine` blijft de orchestrator en delegatiepunt voor bestaande call sites.

Om naamconflict te voorkomen hernoemen we de ingest-implementatie naar `MarketDataIngestService` in `market_data_service.py` en introduceren we `MarketDataDomainService` voor de engine-domeinlaag.

## Consequences

- Positief:
  - Betere testbaarheid van risk/analysis/execution zonder volledige runtime bootstrap.
  - Duidelijkere servicegrenzen en minder god-object gedrag in `LuminaEngine`.
  - Backward-compatible publieke engine-methodes behouden bestaande integraties.
- Negatief:
  - Meer modules en wiring in container/exports.
  - Extra discipline nodig in imports (`MarketDataIngestService` versus `MarketDataDomainService`).
- Risico's:
  - Importverwarring bij nieuwe code als ingest/domain classnamen niet expliciet worden gekozen.
  - Regressierisico in REAL-mode sizing bij onvolledige parity-tests.

## Alternatives Considered

- Optie A: `LuminaEngine` volledig herschrijven met state-verplaatsing naar aparte state store.
  - Afgewezen: te groot migratierisico en niet nodig voor deze iteratie.
- Optie B: Alleen helperfuncties verplaatsen zonder services.
  - Afgewezen: onvoldoende expliciete grenzen, testbaarheid blijft beperkt.

## Related ADRs

- ADR-0001: Bounded contexts central event bus
- ADR-0007: Promotion gate real mode
- ADR-0009: Thin Engine orchestrator en verwijdering van app-shim
