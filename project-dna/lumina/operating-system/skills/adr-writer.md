---
name: adr-writer
description: >-
  Schrijft Architecture Decision Records (ADR) in het correcte LUMINA-formaat.
  Gebruik bij belangrijke architectuurkeuzes (nieuwe laag, pattern, technology
  switch, enz.), bij ADR-documentatie, of wanneer de gebruiker ADR of adr-writer noemt.
---

# ADR Writer Skill (v1.1)

**Doel**: Schrijf Architecture Decision Records (ADR) in het correcte LUMINA formaat.

**Wanneer gebruiken**: Bij elke belangrijke architectuurkeuze (nieuwe laag, pattern, technology switch, etc.).

---

## Slimme logica (automatisch toepassen)

**1. Auto-decide of ADR nodig is**
- Bij > 3 nieuwe bestanden of architectuurwijziging → ADR verplicht
- Bij pure refactoring zonder contract/safety impact → alleen docs/architecture.md (geen ADR)

**2. Auto-suggest titel & context**
- Genereert een voorstel voor de titel en de "Context" sectie op basis van de change.

**3. Auto-vul template**
- Vult het template alvast in met de juiste structuur.

---

**Standaard ADR template**:

```markdown
# ADR-XXX: [Korte titel]

**Status**: Proposed / Accepted / Deprecated

**Date**: 2026-05-02

## Context
Wat is het probleem dat we proberen op te lossen? Welke krachten werken in?

## Decision
Wat hebben we besloten te doen?

## Consequences
- Positief: ...
- Negatief: ...
- Risico's: ...

## Alternatives Considered
- Optie A: ...
- Optie B: ...

## Related ADRs
- ADR-012: ...
```

**Regels**:
- Houd ADR's kort (max 1 A4)
- Gebruik "we" in plaats van "ik"
- Leg uit **waarom** de beslissing genomen is (niet alleen wat)
- Update de status als de beslissing verandert
- Plaats ADR's in `docs/adr/`