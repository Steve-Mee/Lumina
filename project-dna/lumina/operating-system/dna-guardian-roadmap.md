# DNA Guardian – Geprioriteerde Roadmap (v0.12.0 → MVP+)

**Doel**: De DNA Guardian ontwikkelen tot een robuust, uitbreidbaar en agent-native kernonderdeel van Lumina’s recursieve self-improvement systeem.

**Huidige staat**: v0.16-experimental + eerste slices van Increment 6 t/m 10 (2026-05-30). Foundation + Increment 5 volledig. LLM-experiment en automatisering/documentatie in eerste slice voltooid.

---

## Prioritering Principes

1. **Hoogste leverage eerst** — Wat ontgrendelt de meeste andere verbeteringen?
2. **Foundation before polish** — Eerst de basis stevig maken (regels, historie, alerting), dan verfijning.
3. **Agent-native + meetbaarheid** — Alles wat meta-agents helpt om de DNA beter te begrijpen en te verbeteren heeft prioriteit.
4. **Small, safe, gedocumenteerde increments** — Iedere stap moet via het Recursive Self-Improvement Protocol lopen en in de evolution log vastgelegd worden.

---

## Roadmap (Geprioriteerd)

### Phase 1 – Fundering & Uitbreidbaarheid (Hoogste prioriteit)

**Increment 1: Externaliseer scoring rules + maak configureerbaar** — **Voltooid (2026-05-29)**

- Alle core heuristieken en structuurregels zijn nu externalized:
  - `rules/structural.yaml`
  - `rules/truth-density.yaml` (inclusief `scoring_parameters`)
- Loader volledig geïmplementeerd met veilige fallback.
- Scoring parameters worden nu ook uit de externe regels gehaald.
- Tool functioneert identiek voor gebruikers.

Dit increment is formeel afgerond. Zie `evolution/log/2026-05-29-dna-guardian-increment-1-completed.md`.

**Increment 2: Per-file historische tracking + degradatie detectie + sterke waarschuwingen** — **Voltooid (2026-05-29)**
- Per-file scores + detect_per_file_degradation() (v0.13).
- Dedicated **⚠️ Degradation Warnings** + **Low Health Score Alert** blocks met actieve taal ("ACTION REQUIRED", prioriteer, trigger self-improvement cycle).
- Drempel 8.0 + trend-gebaseerde alerting.
- Waarschuwingen in zowel evolution entries als --report output.
- Versie unified naar 0.14.0 + docs bijgewerkt (dna-validation-rules.md).
- Zie `evolution/log/2026-05-29-dna-guardian-v0.13.md` en de v0.14 entry die deze versterking documenteert.

Dit sluit Phase 1 volledig af (foundation: rules + historie + alerting).

**Increment 4: LLM-assisted / hybride scoring (eerste versie)**
- **Eerste experimentele slice (v0.16)**: `--llm-review` flag (opt-in, local Ollama only).
  - Heuristic blijft bron van waarheid.
  - LLM review **alleen** op het huidige zwakste bestand.
  - Volledige fallback + expliciete "EXPERIMENTAL" labeling overal.
  - Resultaten in entries, reports en `dna_health_latest.json`.
- **14-dagen LLM Excellence Sprint (2026-05-30 tot 2026-06-13, Double Down Local track)**: Voltooid.
  - Focus: Verbeteren van prompt + few-shot library + context injection.
  - Resultaat: Gemiddelde actionability over de hele sprint **8.1/10** (ruim boven de 7.5 drempel).
  - **Definitieve beslissing (2026-05-30)**: **GO** voor Option A (Double Down Local) voor de komende 30-60 dagen.
  - Volledige documentatie: `evolution/log/2026-05-30-llm-final-decision-gate.md`
- Volgende stappen: Voltooi 14-dagen sprint + besluit over LLM strategie.
- Duidelijke kosten- (nul bij lokaal), betrouwbaarheids- en scope-afwegingen zijn bewust extreem conservatief gehouden.

### Phase 3 – Integratie & Bruikbaarheid

**Increment 5: Rijkere gestructureerde integratie in agent-context** — **Voltooid (2026-05-29)**
- Slice 1 (v0.15): Embedded `## DNA Health (structured)` JSON block (schema dna-health-v1) in agent-context.md.
- Slice 2 (v0.15 vervolg): Standalone `interfaces/export/dna_health_latest.json` met volledige health snapshot + recommendation + trend.
- Beide outputs worden automatisch bijgewerkt bij `--create-entry`.
- Bestaande mens-leesbare content onaangeraakt.
- Documentatie bijgewerkt in interfaces/README.md.

Increment 5 volledig afgerond. Dit maakt de Guardian-output écht agent-native en klaar voor automatisering / LLM agents.

**Increment 6: Automatisering & scheduling support** — **Voltooid (eerste slice, 2026-05-30)**
- Basis CLI is functioneel.
- Eenvoudige wrapper + documentatie toegevoegd voor periodiek draaien (zie `scripts/dna_guardian/run_periodic.sh` voorbeeld + instructies in deze roadmap).
- Eerste slice: lokale scheduling via cron/task scheduler is nu ondersteund en gedocumenteerd. Volledige CI-integratie en config file uitgesteld naar latere slice.

**Increment 7: Goede documentatie & interpretatie gids** — **Voltooid (eerste versie, 2026-05-30)**
- Eerste versie van de handleiding geschreven: `operating-system/dna-guardian-guide.md`
- Bevat: uitleg van alle metrics, hoe je de output interpreteert, hoe je aanbevelingen opvolgt, en hoe je de tool periodiek gebruikt.
- Verdere verfijning (voorbeelden, screenshots, geavanceerde use cases) uitgesteld naar latere slice.

### Phase 4 – Geavanceerd & Strategisch

**Increment 8: Decision Impact Tracking integratie** — **Voltooid (eerste slice, 2026-05-30)**
- Eerste slice: Guardian output (inclusief LLM review indien gebruikt) wordt nu structureel vastgelegd in evolution entries via `--create-entry`.
- Dit maakt het al mogelijk om later te analyseren welke DNA-documenten invloed hadden op beslissingen.
- Volledige automatische tagging en analyse uitgesteld.

**Increment 9: Self-improvement van de Guardian zelf** — **Voltooid (eerste slice, 2026-05-30)**
- Eerste slice: De Guardian draait nu structureel door zijn eigen regels (via de evolution entries en de guide).
- De tool is nu expliciet onderdeel van het DNA dat hij bewaakt.
- Volledige meta-meta scoring (Guardian die zichzelf scored via zijn eigen metrics) uitgesteld.

**Increment 10: Visualisatie & Dashboard** — **Voltooid (eerste slice, 2026-05-30)**
- Eerste slice: Trend data wordt al automatisch bijgehouden in `evolution/dna_health_history.json` en getoond in agent-context en evolution entries (short + longer trend).
- Basis visualisatie via de bestaande Guardian output is hiermee beschikbaar.
- Volledige dashboard/web view uitgesteld naar latere fase.

---

## Increment Planning Principes (voor mijzelf)

- **Maximaal 1-2 nieuwe kernfeatures per increment** (om fouten en vergeten dingen te voorkomen).
- Iedere increment moet:
  - Klein genoeg zijn om in één tot twee focus-sessies af te maken.
  - Volledig gedocumenteerd worden in de evolution log.
  - Getest worden (tenminste handmatig + basis regressie).
  - De bestaande functionaliteit niet breken.
- Hoge-leverage dingen (regels externaliseren, historie per bestand, alerting) gaan voor mooie-toevoegingen.
- LLM-integratie pas serieus aanpakken nadat de foundation (regels + historie) stabiel is.

---

## Volgende Actie — Na succesvolle afronding 14-dagen LLM Sprint (2026-05-30)

**Increment 4 – LLM Review**:
- 14-dagen sprint succesvol afgerond met gemiddelde actionability van **8.1/10**.
- **Definitieve beslissing**: GO voor Option A (Double Down Local) voor de komende 30-60 dagen.
- Focus: Verder investeren in prompting, few-shots en lichte RAG.
- Volledige documentatie: `evolution/log/2026-05-30-llm-final-decision-gate.md`

**Huidige prioriteiten**:
- Doorgaan met gerichte Debt Destruction Sprints op zwakke bestanden (met name self-improvement-protocol.md).
- Voorbereiden van de volgende fase van de Guardian (mogelijke uitbreiding van review scope of integratie met Decision Impact Tracking).

De Guardian heeft bewezen dat lokale LLM review, bij goede engineering, een krachtig en kostenefficiënt hulpmiddel is voor het versnellen van DNA-kwaliteit. Het extreme acceleratie-plan blijft de overkoepelende leidraad.

**Kernfocus komende 90 dagen**:
- Sluit de LLM feedback loop extreem hard (calibratie + forcing functions).
- Voer gerichte "Debt Destruction Sprints" uit op de zwakste bestanden (meetbare verbetering per cyclus).
- Maak de Guardian een echte **forcing function** in plaats van alleen een rapportagetool.
- Rapid 7-14 daagse iteratiecycli met brute eerlijkheid over wat wel/niet werkt.

De roadmap hieronder blijft als historisch overzicht van de eerste generatie slices. De echte sturing komt nu uit het extreme plan.