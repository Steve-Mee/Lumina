---
name: constitution-guard
description: >-
  Handhaaft de LUMINA Trading Constitution bij code- en architectuurwijzigingen:
  kapitaalbehoud, fail-closed, bounded contexts, typed events, transparantie,
  FinalArbitration, testbaarheid. Gebruik bij grotere wijzigingen, risk/order-flow,
  event bus, agents, of wanneer de gebruiker constitution-guard, constitution-check
  of Trading Constitution noemt.
---

# Constitution Guard Skill (v1.1)

**Doel**: Zorgt dat **geen enkele** code wijziging in strijd is met de Trading Constitution van LUMINA.

**Wanneer gebruiken**: Bij elke grotere wijziging (automatisch of via `/constitution-check`).

---

## Slimme logica (automatisch toepassen)

**1. Auto-detect impact**
- Als change `PromotionPolicy`, `RiskDecision`, `ConstitutionalGuard`, `shadow`, `veto`, `REAL mode` of `fail-closed` raakt → **hoge prioriteit** + extra blokkade.

**2. Auto-suggest mitigations**
- Bij potentiële overtreding → stel concrete aanpassingen voor (bijv. "Voeg human approval + shadow deployment toe").

**3. Auto-escalatie**
- Bij score < 7 → forceer extra review + mogelijke blokkade.

---

**De 7 Heilige Regels van de LUMINA Trading Constitution** (nooit breken):

1. **Kapitaalbehoud eerst** — Geen enkele order mag REAL kapitaal in gevaar brengen zonder expliciete human approval + shadow deployment.

2. **Fail-closed** — Bij twijfel = reject. Nooit "fail-open".

3. **Geen god-classes** — Risico, Constitution, Event Bus en Agent Orchestration zijn strikt gescheiden bounded contexts.

4. **Typed contracts** — Alle events gaan via Pydantic modellen. Raw dicts zijn alleen toegestaan tijdens migratie.

5. **Transparantie** — Iedere reject of violation wordt gelogd met agent_id, reden en timestamp.

6. **Evolutie met rem** — Self-evolving agents mogen alleen voorstellen doen. De FinalArbitration laag beslist.

7. **Testbaarheid** — Elke regel moet unit-testbaar zijn met een duidelijke "gegeven → wanneer → dan" structuur.

**Actie bij overtreding**:
- Blokkeer de change
- Schrijf een `ConstitutionViolation` event
- Eis een ADR + human review voordat de change alsnog kan