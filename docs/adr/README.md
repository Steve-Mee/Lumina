# Architecture Decision Records (ADR)

Deze map bevat de canonieke ADR-reeks voor LUMINA.  
Doel: architectuurbeslissingen expliciet, toetsbaar en mission-aligned vastleggen volgens `.cursorrules`.

## Canonieke reeks

**Nieuwe ADR:** `python scripts/new_adr.py "Jouw titel"` — zie [CONTRIBUTING.md](../../CONTRIBUTING.md) (sectie *Een nieuwe ADR aanmaken*).

Nieuwe ADR's gebruiken het formaat `000x-title.md`.  
De kernmissie (extreme intellectual honesty, rigoureuze testing, radicale creativiteit) en het Elon Musk Mindset Protocol moeten expliciet worden benoemd in iedere ADR.

## Overzicht

| Nummer | Titel | Status | Datum | Link |
|---|---|---|---|---|
| 0000 | ADR Template | Proposed | 2026-05-01 | [0000-template.md](./0000-template.md) |
| 0001 | Introductie van Bounded Contexts en Centrale Event Bus | Accepted | 2026-05-01 | [0001-bounded-contexts-central-event-bus.md](./0001-bounded-contexts-central-event-bus.md) |
| 0002 | Shadow Deployment en Verplichte Human Approval voor Radicale Mutaties | Accepted | 2026-05-01 | [0002-shadow-deployment-human-approval.md](./0002-shadow-deployment-human-approval.md) |
| 0003 | Trading Constitution en Sandboxed Mutation Executor | Accepted | 2026-05-01 | [0003-trading-constitution-sandboxed-mutation-executor.md](./0003-trading-constitution-sandboxed-mutation-executor.md) |
| 0004 | Purged Cross-Validation, Order Book Replay en Reality Gap Penalty | Accepted | 2026-05-01 | [0004-backtest-realism-purged-cv-orderbook-replay-reality-gap.md](./0004-backtest-realism-purged-cv-orderbook-replay-reality-gap.md) |
| 0005 | Test Suite Overhaul met Markers, Timeouts en Isolated Fixtures | Proposed | 2026-05-01 | [0005-test-suite-overhaul-markers-timeouts-isolated-fixtures.md](./0005-test-suite-overhaul-markers-timeouts-isolated-fixtures.md) |
| 0006 | State Manager Cross-Process Locks en Busy Timeout | Accepted | 2026-05-02 | [0006-state-manager-cross-process-locks-and-busy-timeout.md](./0006-state-manager-cross-process-locks-and-busy-timeout.md) |
| 0007 | Promotion Gate voor REAL mode | Accepted | 2026-05-02 | [0007-promotion-gate-real-mode.md](./0007-promotion-gate-real-mode.md) |
| 0008 | LuminaEngine service decomposition | Accepted | 2026-05-02 | [0008-lumina-engine-service-decomposition.md](./0008-lumina-engine-service-decomposition.md) |
| 0009 | Thin Engine orchestrator en verwijdering van app-shim | Accepted | 2026-05-03 | [0009-thin-engine-orchestrator-and-app-shim-removal.md](./0009-thin-engine-orchestrator-and-app-shim-removal.md) |

## Legacy notitie

Historische `ADR-00x-*` documenten blijven voorlopig aanwezig voor bestaande referenties.  
Nieuwe beslissingen worden uitsluitend toegevoegd aan de `000x`-reeks.
