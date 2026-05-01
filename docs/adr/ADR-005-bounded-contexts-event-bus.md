# ADR-005: Bounded Contexts + Central Event Bus

**Status:** Accepted  
**Date:** 2026-05-01  
**Authors:** LUMINA Engineering (AI-assisted)

## Context

`lumina_core/engine/` groeide uit tot een brede verzameling van trading, risk,
evolution, safety en orchestratieverantwoordelijkheden. Dit verhoogde
cognitieve load en maakte veilige veranderingen trager.

Belangrijkste pijnpunten:

1. **Context-menging**: één map en import-surface voor verschillende domeinen.
2. **Grote orchestration-class**: `LuminaEngine` bevatte veel ongerelateerde
   details, inclusief blackboard-binding logic.
3. **Geen centrale domein-events**: pub/sub bestond vooral als blackboard-topic
   mechanisme, niet als expliciete, context-overstijgende event bus.

## Decision

Introduceer bounded contexts als duidelijke toegangspunten:

- `lumina_core/trading_engine`
- `lumina_core/evolution`
- `lumina_core/risk`
- `lumina_core/agent_orchestration`
- `lumina_core/safety`

En voeg een centrale event-driven kern toe:

- `lumina_core/agent_orchestration/event_bus.py`
  - `EventBus`
  - `DomainEvent`

Daarnaast:

1. **Container wiring naar contexts**
   - `ApplicationContainer` gebruikt context-imports voor trading/risk/orchestration.
   - `EventBus` wordt centraal aangemaakt en aan `LuminaEngine` gekoppeld.
2. **God-class reductie (targeted)**
   - Blackboard-binding handlers zijn geëxtraheerd naar
     `lumina_core/agent_orchestration/engine_bindings.py`.
   - `LuminaEngine.bind_blackboard()` delegeert nu naar die module.
3. **Event-driven bridge**
   - `LuminaEngine.set_current_dream_fields()` publiceert
     `trading_engine.dream_state.updated` op de centrale EventBus.

## Consequences

### Positive

- **Lagere cognitieve load**: domein-ingangen zijn expliciet en logisch gegroepeerd.
- **Betere evolueerbaarheid**: migratiepad naar fysieke verplaatsing zonder
  direct grote brekende wijzigingen.
- **Veilige eventgedreven uitbreiding**: contexts kunnen observeren zonder harde
  directe afhankelijkheden.
- **Backwards compatibility**: bestaande `lumina_core.engine.*` imports blijven werken.
- **Stap 2 uitgevoerd**: `RiskAllocatorMixin` en `RiskGatesMixin` zijn
  fysiek gemigreerd naar `lumina_core/risk/` met engine-compat-shims.
- **Stap 3 afgerond (breaking allowed)**: alle actieve imports gebruiken
  `lumina_core.risk.risk_controller` als canonical pad, en legacy
  `lumina_core.engine.risk_*` modules zijn verwijderd.

### Negative

- **Tijdelijke dualiteit**: zowel oude engine-imports als nieuwe context-imports
  bestaan tegelijk.
- **Graduele migratie nodig**: niet alle call-sites zijn direct omgezet.

## Backwards Compatibility

- Oude modulepaden blijven beschikbaar.
- Nieuwe contextpakketten doen in eerste fase vooral re-exports.
- `lumina_core.engine.__init__` exporteert nu ook `EventBus`/`DomainEvent` voor
  geleidelijke adoptie.

## Follow-up

1. Verplaats fysiek risk- en orchestration-modules uit `engine/` naar eigen contextmappen.
2. Definieer context events als stabiele contracts (versie + schema).
3. Verminder directe `LuminaEngine`-coupling via small interfaces/ports.
