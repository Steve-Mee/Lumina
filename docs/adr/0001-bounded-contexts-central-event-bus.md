# ADR-0001: Introductie van Bounded Contexts en Centrale Event Bus

**Status:** Accepted  
**Date:** 2026-05-01  
**Deciders:** LUMINA Engineering (Steve + AI)

## Context

De eerdere architectuur concentreerde meerdere domeinen in brede engine-oppervlakken, wat leidde tot hoge cognitieve belasting, impliciete koppelingen en trage, risicovolle refactors.

Deze beslissing is direct gekoppeld aan de LUMINA-kernmissie: extreme intellectual honesty (transparante verantwoordelijkheden), rigoureuze testing (duidelijke grenzen per context) en radicale creativiteit (sneller veilig evolueren). Ze volgt ook het Elon Musk Mindset Protocol door first principles toe te passen op domeinverantwoordelijkheid en radicale eenvoud in modulegrenzen af te dwingen.

## Decision

We introduceren bounded contexts als leidende domeinstructuur binnen `lumina_core/` en gebruiken een centrale event bus voor context-overstijgende communicatie.

- Canonieke contexten: `risk`, `trading_engine`, `evolution`, `safety`, `agent_orchestration`.
- Contextgrenzen worden expliciet gemaakt via import-paden en publieke API-oppervlakken.
- Context-overstijgende signalering loopt via een centrale event bus in plaats van directe, fragiele koppelingen.
- Kritieke event-stromen zijn fail-closed: bij contractschending of ongeautoriseerde publisher wordt geblokkeerd en geaudit.

## Consequences

### Positive

- Lagere onderhoudskosten door heldere domeingrenzen en minder verborgen afhankelijkheden.
- Hogere testbaarheid: contexten kunnen met gerichte unit/integration tests worden gevalideerd.
- Betere evolueerbaarheid: nieuwe features kunnen via event-driven extensies worden toegevoegd zonder god-class groei.

### Negative

- Tijdelijke complexiteit tijdens migratie doordat oude en nieuwe importpatronen naast elkaar kunnen bestaan.
- Discipline vereist: nieuwe features moeten actief binnen contextgrenzen en event-contracten blijven.

## Alternatives considered

1. Flat `engine/`-structuur behouden — verworpen door oplopende complexiteit en onderhoudsrisico.
2. Alleen interne codestijl-afspraken zonder architectuurgrenzen — verworpen, onvoldoende afdwingbaar.
3. Directe synchronische context-calls zonder event bus — verworpen door sterke koppeling en lagere schaalbaarheid.

## Links

- Gerelateerde ADRs: `docs/adr/0002-shadow-deployment-human-approval.md`, `docs/adr/0003-trading-constitution-sandboxed-mutation-executor.md`
- Legacy ADRs: `docs/adr/ADR-002-bounded-contexts.md`, `docs/adr/ADR-003-event-bus-contract.md`, `docs/adr/ADR-005-bounded-contexts-event-bus.md`
- Gerelateerde code: `lumina_core/agent_orchestration/event_bus.py`, `lumina_core/container.py`
