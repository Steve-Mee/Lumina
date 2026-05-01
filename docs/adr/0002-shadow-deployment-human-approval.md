# ADR-0002: Shadow Deployment en Verplichte Human Approval voor Radicale Mutaties

**Status:** Accepted  
**Date:** 2026-05-01  
**Deciders:** LUMINA Engineering (Steve + AI)

## Context

Zelfevolutie levert strategische winst op, maar radicale mutaties kunnen onverwachte regressies of risicoprofielen introduceren als ze te snel richting live trading bewegen.

Deze beslissing ondersteunt expliciet de LUMINA-missie: extreme intellectual honesty (eerst bewijs verzamelen in shadow), rigoureuze testing (productieachtig validatiepad) en radicale creativiteit (experimenteren blijft mogelijk zonder direct kapitaalrisico). Ze volgt het Elon Musk Mindset Protocol door first principles toe te passen op risicocontrole: geen promotie zonder meetbaar bewijs en menselijke bevestiging.

## Decision

We hanteren een verplichte rollout-governance voor radicale mutaties:

- Nieuwe/radicale mutaties draaien eerst in shadow deployment met productieachtige marktdatastromen.
- Promotie naar gevoelige omgevingen vereist expliciete human approval.
- Bij onvoldoende bewijs of policy-overtreding blijft de mutatie geblokkeerd (fail-closed).
- Rollout-events en promotiebesluiten worden geaudit voor forensische traceerbaarheid.

## Consequences

### Positive

- Sterk gereduceerde kans op ongecontroleerde regressies in live-achtige scenario's.
- Beter operationeel vertrouwen door expliciete menselijke beslismomenten.
- Experimenteersnelheid blijft hoog in SIM/Paper, zonder heilig kapitaalbehoud in gevaar te brengen.

### Negative

- Langere doorlooptijd tussen mutatie en promotie door extra validatiefasen.
- Meer operationele discipline nodig rond approvals en audit-trails.

## Alternatives considered

1. Volledig geautomatiseerde promotie op basis van fitnessscore — verworpen wegens onvoldoende veiligheidsmarge.
2. Alleen statische configuratielimieten zonder shadow-fase — verworpen wegens ontbrekende runtime-validatie.
3. Handmatige review zonder systematische shadow deployment — verworpen door inconsistentie en lagere reproduceerbaarheid.

## Links

- Gerelateerde ADRs: `docs/adr/0001-bounded-contexts-central-event-bus.md`, `docs/adr/0003-trading-constitution-sandboxed-mutation-executor.md`
- Gerelateerde code: `lumina_core/evolution/rollout.py`, `lumina_core/evolution/evolution_orchestrator.py`
- Gerelateerde docs: `docs/AGI_SAFETY.md`
