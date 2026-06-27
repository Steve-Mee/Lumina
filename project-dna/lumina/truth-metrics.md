# Truth Metrics for Project DNA

Dit document definieert hoe we de kwaliteit en effectiviteit van onze eigen Project DNA meten. Zonder deze metrics blijft zelfverbetering anekdotisch.

## Kern Metrics

### 1. Truth Density (0-10)
Hoeveel bullshit, vage aspiraties en niet-falsifieerbare claims staan in een DNA-onderdeel?

**Scoring**:
- 9-10: Extreem compact, alle claims zijn evidence-based of expliciet als hypothese gelabeld.
- 7-8: Meeste inhoud is scherp, enkele vage passages.
- 5-6: Significante hoeveelheid fluff of onduidelijke claims.
- <5: Te veel aspiratie, te weinig mechanica.

**Toepassing**: Ieder nieuw of aangepast DNA-bestand krijgt bij creatie/ review een Truth Density score + toelichting.

### 2. Evolvability Score (0-10)
Hoe makkelijk maakt dit document het om in de toekomst betere versies te maken?

**Factoren**:
- Modulariteit van de inhoud
- Duidelijkheid van de "waarom"
- Aanwezigheid van expliciete feedback loops
- Mate waarin het toekomstige veranderingen faciliteert of blokkeert

### 3. Decision Impact Tracking
Voor belangrijke beslissingen (vooral meta-beslissingen) registreren we:
- Welk deel van de DNA is gebruikt als input?
- Wat was de voorspelling?
- Wat was het werkelijke resultaat?
- Wat hebben we geleerd voor de DNA?

Dit wordt bijgehouden in `evolution/log/`.

### 4. Protocol Adherence Rate
Percentage van meta-wijzigingen in de afgelopen 90 dagen die correct het Recursive Self-Improvement Protocol hebben gevolgd (inclusief Plan Mode + gedocumenteerde hypothese + evolution-log entry).

Doel: >90% binnen 6 maanden na invoering van DNA 2.0.

---

Deze metrics worden minimaal elke 90 dagen geëvalueerd tijdens een formele DNA review. Resultaten worden vastgelegd in de evolution log.

**Eerste meting**: Uit te voeren tijdens of direct na de DNA 2.0 migratie.