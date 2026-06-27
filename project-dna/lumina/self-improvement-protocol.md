# Recursive Self-Improvement Protocol (v2.0)

**Doel**: Dit is het verplichte mechanisme waarmee Lumina zijn eigen instructies, principes, architectuur en processen verbetert — op een kleine, meetbare, falsifieerbare en omkeerbare manier.

Dit protocol is strenger dan de minimale v1 versie. Het is geen suggestie; het is de motor.

## Scope
Van toepassing op alle verbeteringen aan:
- Alles onder `project-dna/lumina/`
- Root `AGENTS.md`, `.cursorrules`, `CONTRIBUTING.md`
- Kern-skills die agent-gedrag rond architectuur, risico, evolutie of besluitvorming beïnvloeden

Niet van toepassing op pure feature-ontwikkeling of trading-strategie wijzigingen.

## Verplichte Stappen (geen uitzonderingen)

### 1. Plan Mode (altijd)
Iedere meta-wijziging start in Plan Mode. Geen shortcuts.

**Plan Mode** = een verplichte, afgebakende analysefase vóór implementatie. Doel: volledige hypothese, falsifieerbare voorspellingen en risico-analyse vastleggen. Bij voorkeur in read-only planning context.

### 2. Impact Classificatie
- **Small**: Verduidelijking of kleine correctie zonder structurele impact. (Evolution entry sterk aanbevolen.)
- **Medium**: Significante wijziging in één of meerdere DNA-onderdelen. (Verplicht: Plan Mode + hypothese + evolution entry.)
- **Large**: Fundamentele verandering in governance, principes of het zelfverbeteringsproces. (Verplicht: Plan Mode + hypothese + human review + evolution entry. Overweeg constitution-guard en risk-safety-review.)

Classificatie wordt door de initiator gemaakt en vastgelegd. Bij twijfel: hogere classificatie.

### 3. Hypothese + Falsifieerbare Voorspelling (verplicht)
Voor iedere wijziging formuleer je:
- Wat is het huidige probleem / de huidige beperking?
- Wat verandert er precies?
- Wat is de concrete, meetbare voorspelling over 30 / 90 / 180 dagen?
- Hoe gaan we meten of de voorspelling uitkomt?

Zonder falsifieerbare hypothese mag de wijziging niet door.

### 4. Evolution Log Entry
Direct na (of tijdens) implementatie voeg je een entry toe in `evolution/log/` met:
- Hypotheses + voorspelling
- Reden en verwachte impact op evolueerbaarheid
- Hoe de wijziging ongedaan gemaakt of bijgestuurd kan worden

### 5. DNA Review Gate
- Small: Expliciete zelf-review met hypothese.
- Medium: Volg het protocol + overweeg extra review.
- Large: Verplicht human review + toepassing van `constitution-guard` en `risk-safety-review` indien relevant voor governance/risk.

## Extra Eisen voor DNA 2.0

- Iedere meta-wijziging moet expliciet evalueren wat de impact is op de **Evolvability Score** van het systeem.
- "We doen dit omdat het logisch voelt" is geen geldige reden meer.
- Nieuwe lagen of complexiteit mogen alleen toegevoegd worden als er een aantoonbare, meetbare verbetering in waarheidsdichtheid of evolueerbaarheid tegenover staat.

### Evolvability Score (definitie & meting)
De Evolvability Score (0-10) meet hoe makkelijk het voor toekomstige versies van onszelf is om dit onderdeel te verbeteren zonder grote risico's of contextverlies.

**Ruw rekenmodel** (te verfijnen):
- +2 tot +3 als er expliciete hypotheses + falsifieerbare voorspellingen staan.
- +1 tot +2 als er meetbare success criteria / metrics staan.
- +1 als er een duidelijke rollback-strategie staat.
- -1 tot -3 bij vage claims, impliciete boundaries of ontbrekende context.
- Basislijn = 5.0 (neutraal).

Dit is een subjectieve maar verplichte inschatting die in de evolution entry moet worden vastgelegd.

### Conflict Resolution (verplicht bij Medium/Large wijzigingen)
Bij Medium of Large meta-wijzigingen moet expliciet worden beschreven hoe conflicterende hypotheses of prioriteiten worden opgelost.

**Aanbevolen mechanismen** (kies er minstens één en documenteer):
- Tijdelijk parallel experiment in SIM met duidelijke meetcriteria.
- A/B test of shadow deployment met vooraf gedefinieerde success metrics.
- Expliciete prioritering op basis van verwachte impact op Evolvability Score + risico.
- Tijdelijke "pilot" met strikte time-box en rollback trigger.

Voorbeeld: Bij het introduceren van een nieuwe laag in de architecture, beschrijf je hoe je beslist tussen twee concurrerende bounded context designs (bijv. via 2-week experiment in SIM met Guardian score + runtime metrics als besliscriteria).

## Rollback & Superseding

Een meta-wijziging wordt teruggedraaid door:
1. De bestanden terug te zetten of te vervangen.
2. Een nieuwe evolution-log entry toe te voegen die expliciet aangeeft dat de vorige wijziging is gesuperseded, met reden en nieuwe voorspelling.

---

## Evidence Contract (Guardian / Truth Density)

Dit blok maakt het protocol **falsifieerbaar en meetbaar** voor de dagelijkse DNA Guardian-heuristiek. Het verandert geen procesregels; het voegt expliciete **evidence** en **metric**-ankers toe.

**Hypothesis**: Meta-wijzigingen die Plan Mode + gedocumenteerde **hypothesis** + **prediction** + rollback volgen, verhogen de gemiddelde Truth Density en Evolvability Score van `project-dna/lumina/` zonder extra governance-lagen.

**Falsifiable predictions**:
| Horizon | Voorspelling | Meet-signaal |
|---------|--------------|--------------|
| 30 dagen | `self-improvement-protocol.md` Truth Density ≥ 9.0 | Guardian `--report` per-file score |
| 90 dagen | Protocol Adherence Rate ≥ 90% op meta-entries in `evolution/log/` | Steekproef: Plan Mode + hypothesis + rollback aanwezig |
| 180 dagen | Geen structurele regressie: Guardian structural health ≥ 9.5 | `dna_health_latest.json` trend |

**Measurable metrics** (verplicht in elke evolution entry):
- Guardian **score** (`truth_density_avg`, structural health, aperture integrity)
- Protocol Adherence Rate (meta-entries / totaal meta-entries, rolling 90d)
- Evolvability Score delta (voor/na, 0–10 inschatting per entry)
- Rollback trigger: expliciete metric-drempel of datum (time-box)

**Evidence / reproduce** (na elke Medium/Large meta-wijziging):
```bash
python scripts/dna_guardian/validate_dna.py --report
python scripts/phase3_perfection_gate_verify.py
```

**Rollback**: Verwijder dit Evidence Contract-blok en herstel de vorige versie; processtappen 1–5 blijven leidend. Documenteer superseding in `evolution/log/`.

---

## Voorbeeld van toepassing (case study)

**Voorbeeld**: Verbetering van `current-reality/evolutionary-debt.md` op 2026-05-30.

- **Probleem**: Het bestand scoorde consistent laag (7.0 heuristiek / 6.0 LLM) omdat claims vaag en niet-falsifieerbaar waren.
- **Actie**: Per debt item werden hypotheses + meetbare signalen toegevoegd. Vage termen ("recently", "gedeeltelijk") werden grotendeels verwijderd.
- **Resultaat**: Truth Density steeg van 7.0 → 9.4 binnen één cyclus. Het bestand was daarna niet meer het structureel zwakste.
- **Les**: Het toevoegen van expliciete hypotheses + meetbare targets heeft een veel groter effect op bruikbaarheid dan alleen het opschonen van taal.

Dit voorbeeld toont aan waarom de structuur (hypothese + falsifieerbare voorspelling + meetbaar signaal) verplicht is.

Dit protocol vervangt de eerdere minimale versie. Verdere aanscherping gebeurt alleen via dit protocol zelf.

*Geïntroduceerd als onderdeel van Project DNA 2.0 redesign — 2026-05-29*