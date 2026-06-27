---
name: constitution-guard
description: >
  Handhaaft de LUMINA Trading Constitution bij alle code- en architectuurwijzigingen.
  Blokkeert wijzigingen die in strijd zijn met kapitaalbehoud, fail-closed design,
  bounded contexts en typed contracts.
---

# Constitution Guard Skill (v2.0)

**Doel**: Zorgt dat **geen enkele** wijziging in strijd komt met de Trading Constitution van Lumina.

**Primaire bron**: `project-dna/lumina/constitution.md` + `project-dna/lumina/AGENTS.md`

**Wanneer gebruiken**: Bij elke grotere wijziging (automatisch of via `/constitution-check`).

---

## Kernregels (Nooit Breken)

1. **Kapitaalbehoud eerst** — Geen enkele order mag REAL kapitaal in gevaar brengen zonder human approval + shadow deployment.
2. **Fail-closed** — Bij twijfel = reject.
3. **Geen god-classes** — Risico, Constitution, Event Bus en Agent Orchestration zijn strikt gescheiden bounded contexts.
4. **Typed contracts** — Alle events gaan via Pydantic modellen (`extra=forbid`).
5. **Transparantie** — Iedere reject of violation wordt gelogd met agent_id, reden en timestamp.
6. **Evolutie met rem** — Agents mogen alleen voorstellen doen. Final Arbitration beslist.
7. **Testbaarheid** — Elke regel moet unit-testbaar zijn.

---

## Slimme Logica

- Bij impact op `PromotionPolicy`, `RiskDecision`, `REAL mode`, `shadow` of `fail-closed` → **hoge prioriteit** + extra blokkade.
- Bij potentiële overtreding → stel concrete mitigations voor.
- Bij score < 7 → forceer extra review + mogelijke blokkade.
- Werk altijd samen met `risk-safety-review` en `aperture-mission-control` bij risk-gerelateerde wijzigingen.

---

## Actie bij Overtreding

1. Blokkeer de change.
2. Publiceer een `ConstitutionViolation` event.
3. Eis een ADR + human review voordat de change alsnog kan.

*Versie 2.0 — Sterker geïntegreerd met centrale AGENTS.md en aperture track (juni 2026)*