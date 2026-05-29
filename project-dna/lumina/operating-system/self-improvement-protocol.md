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

### 2. Impact Classificatie
- **Small**: Verduidelijking, kleine toevoeging, of correctie zonder structurele impact.
- **Medium**: Significante wijziging in één DNA-onderdeel of update van meerdere root-instructiebestanden.
- **Large**: Fundamentele verandering in governance, principes, of de structuur van het zelfverbeteringsproces zelf.

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

## Rollback & Superseding

Een meta-wijziging wordt teruggedraaid door:
1. De bestanden terug te zetten of te vervangen.
2. Een nieuwe evolution-log entry toe te voegen die expliciet aangeeft dat de vorige wijziging is gesuperseded, met reden en nieuwe voorspelling.

---

Dit protocol vervangt de eerdere minimale versie. Verdere aanscherping gebeurt alleen via dit protocol zelf.

*Geïntroduceerd als onderdeel van Project DNA 2.0 redesign — 2026-05-29*