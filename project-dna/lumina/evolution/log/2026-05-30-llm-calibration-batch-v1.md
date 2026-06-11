# 2026-05-30 — LLM Review Calibration Batch v1 (eerste data + menselijke evaluatie)

**Doel van deze entry**: Serieuze eerste calibratie van de LLM-review laag in de DNA Guardian, exact zoals geëist in de extreme first-principles plan.

## Data Verzameld (tot nu toe)

### Review 1 (vorige echte run)
- **Bestand**: `current-reality/evolutionary-debt.md`
- **Heuristische score**: 7.0
- **LLM refined score**: 6.0
- **Confidence**: 0.8
- **Kern LLM bevindingen**:
  - Te weinig concrete metrics, evidence en scherpe timelines.
  - Claims vaak aspirational i.p.v. falsifieerbaar.
  - Argumentatie mist harde onderbouwing.
  - Vage beschrijvingen (bijv. “recently introduced” zonder datum).
  - Implicit/complex boundaries kunnen evolvability remmen.

### Review 2 (vandaag)
- **Bestand**: `operating-system/self-improvement-protocol.md`
- **Heuristische score**: 7.9
- **LLM refined score**: 8.5 (hoger dan heuristiek)
- **Confidence**: 0.9
- **Kern LLM bevindingen**:
  - Goed op falsifiability en reasoning.
  - Mist concrete examples / case studies.
  - 'Evolvability Score' wordt genoemd maar niet gedefinieerd of uitgelegd hoe het berekend wordt.
  - Geen duidelijke metrics voor het meten van verbeteringen in evolvability.

## Menselijke Evaluatie van de LLM Output (Brutale waarheid)

**Positief (echte waarde):**
- De LLM is consistent goed in het oppikken van het "aspirational vs falsifiable" patroon. Dit is precies het grootste structurele probleem in veel DNA-documenten.
- Het signaleert het gebrek aan meetbaarheid en concrete voorbeelden — iets waar de keyword-heuristiek bijna blind voor is.
- In Review 2 gaf het een hogere score dan de heuristiek en dat voelt terecht (het protocol is relatief goed gestructureerd, maar mist diepgang op metrics).

**Negatief / Beperkingen (geen suikercoating):**
- De LLM is nog vrij oppervlakkig op het gebied van "wat zou een goed meetbaar signaal zijn?". Het wijst het probleem aan maar geeft zelden een concreet, goed ontwerp voor een metric.
- Het heeft moeite met context over meerdere bestanden (bijv. dat 'Evolvability Score' eigenlijk gedefinieerd hoort te zijn in truth-metrics.md).
- Geen enkele review tot nu toe heeft echt diepe architecturale implicaties benoemd (bijv. hoe een vaag protocol de hele evolutie-snelheid van het project remt).

**Signaal-kwaliteit schatting (eerste ruwe meting)**:
- Unieke high-value bevindingen die de heuristiek miste: ~60-70%
- Bruikbaarheid voor directe actie: 6.5/10
- Risico op ruis/hallucinatie: Laag tot middel (het blijft redelijk conservatief)

## Conclusie van deze eerste calibratie

De LLM-laag voegt **echte, betekenisvolle waarde** toe, vooral op het gebied van falsifiability en meetbaarheid. Het is duidelijk beter dan pure heuristiek op de dimensies waar we het meest last van hebben.

Tegelijkertijd is het nog niet op het niveau van een "world-class reviewer". Het is meer een zeer goede sparringpartner dan een vervanger van menselijk (of sterker model) oordeel.

**Besluit op dit moment**:
We double down op de LLM-laag, maar met duidelijke verwachtingen:
- Het is een krachtige *detector* van bepaalde klassen van problemen.
- Het is nog zwak in het *ontwerpen* van concrete oplossingen/metrics.
- We gaan het agressief verbeteren via betere prompting + chain-of-thought + koppeling aan truth-metrics.md.

Volgende calibratie (binnen 7-10 dagen) moet minstens 5-6 nieuwe reviews bevatten + een expliciete scoring van "actionability" van de bevindingen.

---
*Deze entry is onderdeel van de extreme first-principles acceleratie van de DNA Guardian.*