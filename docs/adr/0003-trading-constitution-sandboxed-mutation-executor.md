# ADR-0003: Trading Constitution en Sandboxed Mutation Executor

**Status:** Accepted  
**Date:** 2026-05-01  
**Deciders:** LUMINA Engineering (Steve + AI)

## Context

Een zelf-evoluerend trading-systeem heeft een hard, machine-enforceable veiligheidscontract nodig. Zonder constitutionele guardrails en geïsoleerde uitvoering kan een mutatie systeem- of kapitaalrisico introduceren voordat blokkades actief worden.

Deze keuze is expliciet mission-aligned: extreme intellectual honesty (veiligheidsregels zijn toetsbaar en niet impliciet), rigoureuze testing (adversarial checks en audit trails), radicale creativiteit (innovatie binnen veilige grenzen). Volgens het Elon Musk Mindset Protocol reduceren we het probleem tot first principles: bescherm kapitaal en systeemintegriteit via fail-closed controlelagen.

## Decision

We standaardiseren AGI-safety op twee complementaire bouwstenen:

- **Trading Constitution:** set van machine-enforceable principes die mutaties valideren op risicolimieten, approvals en gedrag.
- **Sandboxed Mutation Executor:** mutatiescores worden in een geïsoleerde uitvoercontext berekend om side effects op runtime-state te voorkomen.
- Integratie via een constitutionele guard-flow met pre-mutation en pre-promotion checks.
- Overtredingen blokkeren promotie automatisch en worden geaudit.

## Consequences

### Positive

- Defence-in-depth: meerdere onafhankelijke safety-gates verkleinen kans op doorbraakfouten.
- Betere forensische traceerbaarheid via consistente audit-events.
- Veiligere innovatie: agressieve experimenten blijven mogelijk zonder directe impact op kritieke runtime.

### Negative

- Extra overhead in evolution-cycli door sandbox-executie en extra checks.
- Meer onderhoudsdruk op constitutionele regels om false positives/negatives te minimaliseren.

## Alternatives considered

1. Alleen post-promotion monitoring — verworpen; schade kan optreden vóór rollback.
2. Alleen sandboxing zonder constitutionele principes — verworpen; ontbreekt beleidsafdwinging.
3. Alleen constitutionele check zonder sandbox — verworpen; runtime side effects blijven risico.

## Links

- Gerelateerde ADRs: `docs/adr/0002-shadow-deployment-human-approval.md`, `docs/adr/0004-backtest-realism-purged-cv-orderbook-replay-reality-gap.md`
- Legacy ADRs: `docs/adr/ADR-001-constitutional-principles.md`, `docs/adr/ADR-004-agi-safety-system.md`
- Gerelateerde code: `lumina_core/safety/trading_constitution.py`, `lumina_core/safety/sandboxed_executor.py`, `lumina_core/safety/constitutional_guard.py`
