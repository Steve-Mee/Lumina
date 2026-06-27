---
name: risk-safety-review
description: >
  Reviewt elke codewijziging op naleving van "Kapitaalbehoud is heilig in REAL mode".
  Geeft een duidelijke veiligheidsscore (0-10) met concrete verbeterpunten.
  Gebruik bij risk, trading, order-flow, constitution of real-mode gerelateerde wijzigingen.
---

# Risk Safety Review Skill (v2.0)

**Doel**: Review elke codewijziging die risk, trading, constitution of REAL mode raakt op kapitaalbehoud en fail-closed design.

**Primaire bron**: `project-dna/lumina/constitution.md` + `project-dna/lumina/AGENTS.md`

**Wanneer gebruiken**: Bij elke wijziging die risk, trading of real-mode raakt (automatisch of via `/risk-review`).

---

## Standaard Checklist

Controleer altijd de volgende punten:

1. **Fail-closed design**
   - Is er een expliciet "reject" pad bij elke validatie?
   - Kan een order ooit "per ongeluk" goedgekeurd worden?

2. **REAL mode strengheid**
   - Zijn de limieten in REAL mode strenger dan in Paper/Sim?
   - Is er een extra `require_margin_buffer` of `require_constitution_check`?

3. **Geen optimistische assumpties**
   - Wordt er ergens aangenomen dat een prijs positief is, een agent trusted is, of dat een edge case "niet zal voorkomen"?

4. **Constitution check**
   - Wordt een `ConstitutionViolation` event gepubliceerd bij overtreding?
   - Is er een blokkade voor agents met recente violations?

5. **Logging & Traceability**
   - Wordt elke reject gelogd met een duidelijke reden, agent_id en timestamp?

---

## Output Formaat (Verplicht)

Gebruik altijd dit formaat:

```markdown
**Risk Safety Review** (Score: X/10)

✅ Fail-closed: Ja / Nee
✅ REAL mode stricter: Ja / Nee
✅ ConstitutionViolation event: Ja / Nee
✅ Logging + traceability: Ja / Nee

⚠️ Waarschuwingen:
- ...

🔧 Verbeterpunten:
- ...

**Conclusie**: Change kan door / Change geblokkeerd tot onderstaande punten zijn opgelost.
```

---

## Regels

- Bij een score **lager dan 6** → **blokkeer** de change en eis aanpassingen.
- Bij een score tussen **6 en 7** → waarschuw sterk en stel concrete fixes voor.
- Werk samen met `constitution-guard` bij constitutionele impact.
- Werk samen met `aperture-mission-control` bij wijzigingen die de aperture track raken.

---

*Versie 2.0 — Geoptimaliseerd voor centrale AGENTS.md en betere integratie met andere skills (juni 2026)*